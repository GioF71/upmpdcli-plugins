//#define LOGGER_LOCAL_LOGINC 2

#include "curlfetch.h"

#include <string.h>
#include <unistd.h>

#include <string>
#include <mutex>

#include <curl/curl.h>

#include "smallut.h"
#ifdef MDU_INCLUDE_LOG
#include MDU_INCLUDE_LOG
#else
#include "log.h"
#endif

using namespace std;

// Global libcurl initialization.
class CurlInit {
public:
    CurlInit() {
        int opts = CURL_GLOBAL_ALL;
#ifdef CURL_GLOBAL_ACK_EINTR
        opts |= CURL_GLOBAL_ACK_EINTR;
#endif
        curl_global_init(opts);
    }
};
static CurlInit curlglobalinit;


class CurlFetch::Internal {
public:
    Internal(CurlFetch* parent)
        : p(parent) {}
    ~Internal();
    bool curlrunning() {
        return curlworker.joinable();
    }

    void curlWorkerFunc();
    size_t curlHeaderCB(void *contents, size_t size, size_t nmemb);
    size_t curlWriteCB(void *contents, size_t size, size_t nmemb);

    CurlFetch *p{nullptr};
    CURL *curl{nullptr};
    std::thread curlworker;
    bool curldone{false};
    CURLcode  curl_code{CURLE_OK};
    int curl_http_code{200};

    // In destructor: any waiting loop must abort asap
    bool aborting{false}; 
    
    // Count of client threads waiting for headers (normally 0/1)
    int extWaitingThreads{0};

    // Header values if we get them
    bool headers_ok{false};
    map<string, string> headers;

    // We pre-buffer the beginning of the stream so that the first block we actually release is
    // always big enough for possible header forensics.
    ABuffer headbuf{1024};
    
    // Synchronization
    condition_variable curlcv;
    mutex curlmutex;
};

CurlFetch::CurlFetch(const std::string& url)
    : NetFetch(url)
{
    m = std::unique_ptr<Internal>(new Internal(this));
}

CurlFetch::~CurlFetch()
{
}

CurlFetch::Internal::~Internal()
{
    LOGDEB0("CurlFetch::Internal::~Internal\n");
    unique_lock<mutex> lock(curlmutex);
    aborting = true;
    // We would like to abort any waiting on the curl side here (in a select()) or whatever), but it
    // seems that the only way to do this would be to use the multi interface.
    // https://stackoverflow.com/questions/8415976/example-how-to-cancel-a-libcurl-request
    // We used to try and close the socket, but this would frequently end up closing the wrong fd
    // (one from mhd) and crashing.
    if (p->outqueue) {
        p->outqueue->setTerminate();
    }
    curlcv.notify_all();
    while (extWaitingThreads > 0) {
        LOGDEB1("CurlFetch::~CurlFetch: extWaitingThreads: " << extWaitingThreads << endl);
        curlcv.notify_all();
        LOGDEB1("CurlFetch::~CurlFetch: waiting for ext thread wkup\n");
        curlcv.wait(lock);
    }
    if (curlworker.joinable()) {
        curlworker.join();
    }
    if (curl) {
        curl_easy_cleanup(curl);
        curl = nullptr;
    }
    LOGDEB0("CurlFetch::CurlFetch::~Internal: done\n");
}

bool CurlFetch::start(BufXChange<ABuffer*> *queue, uint64_t offset)
{
    LOGDEB0("CurlFetch::start: offset: " << offset << " 0x" << std::hex <<
            offset << std::dec << "\n");
    if (nullptr == queue) {
        LOGERR("CurlFetch::start: called with nullptr\n");
        return false;
    }

    unique_lock<mutex> lock(m->curlmutex);
    LOGDEB1("CurlFetch::start: got lock\n");
    if (m->curlrunning() || m->aborting) {
        LOGERR("CurlFetch::start: called with transfer active or aborted\n");
        return false;
    }
    // We return after the curl thread is actually running
    outqueue = queue;
    startoffset = offset;
    m->curlworker = std::thread(std::bind(&CurlFetch::Internal::curlWorkerFunc, m.get()));
    while (!(m->curlrunning() || m->curldone || m->aborting)) {
        LOGDEB1("Start: waiting: running " << m->curlrunning() << " done " <<
               m->curldone << " aborting " << m->aborting << endl);
        if (m->aborting) {
            return false;
        }
        m->curlcv.wait(lock);
    }
    LOGDEB1("CurlFetch::start: returning\n");
    return true;
}

bool CurlFetch::reset()
{
    if (m->curlworker.joinable()) {
        m->curlworker.join();
    }
    m->curldone = false;
    m->curl_code = CURLE_OK;
    m->curl_http_code = 200;
    fetch_data_count = 0;
    outqueue->reset();
    return true;
}

bool CurlFetch::fetchDone(FetchStatus *code, int *http_code)
{
    LOGDEB1("CurlFetch::fetchDone: running: " << m->curlrunning() <<
           " curldone " << m->curldone << endl);
    unique_lock<mutex> lock(m->curlmutex);
    if (!m->curldone) {
        return false;
    }
    LOGDEB0("CurlFetch::fetchDone: curlcode " << m->curl_code << " httpcode " <<
           m->curl_http_code << endl);
    if (code) {
        switch (m->curl_code) {
        case CURLE_PARTIAL_FILE:
        case CURLE_RECV_ERROR:
        case CURLE_SEND_ERROR:
            LOGDEB("CurlFetch::fetchDone: retryable\n");
            *code = NetFetch::FETCH_RETRYABLE;
            break;
        case CURLE_OK:
            *code = NetFetch::FETCH_OK;
            break;
        default:
            *code = NetFetch::FETCH_FATAL;
            break;
        }
    }
    if (http_code) {
        *http_code = m->curl_http_code;
    }
    LOGDEB1("CurlTRans::fetchDone: done\n");
    return true;
}

bool CurlFetch::waitForHeaders(int secs)
{
    LOGDEB1("CurlFetch::waitForHeaders\n");
    unique_lock<mutex> lock(m->curlmutex);
    m->extWaitingThreads++;
    // We wait for the 1st buffer write call. If there is no data,
    // we'll stop on curldone.
    while (m->curlrunning() && !m->aborting && !m->curldone && 
           fetch_data_count + m->headbuf.bytes == 0) {
        LOGDEB1("CurlFetch::waitForHeaders: running " << m->curlrunning() <<
               " aborting " << m->aborting << " datacount " <<
               fetch_data_count + m->headbuf.bytes << "\n");
        if (m->aborting) {
            LOGDEB("CurlFetch::waitForHeaders: return: abort\n");
            m->extWaitingThreads--;
            return false;
        }
        if (secs) {
            if (m->curlcv.wait_for(lock, std::chrono::seconds(secs)) == std::cv_status::timeout) {
                LOGERR("CurlFetch::waitForHeaders: timeout\n");
                break;
            }
        } else {
            m->curlcv.wait(lock);
        }
    }
    m->extWaitingThreads--;
    m->curlcv.notify_all();
    LOGDEB1("CurlFetch::waitForHeaders: returning: headers_ok " <<
            m->headers_ok << " curlrunning " << m->curlrunning() <<
            " aborting " << m->aborting << " datacnt " <<
            fetch_data_count+ m->headbuf.bytes << endl);
    return m->headers_ok;
}

bool CurlFetch::headerValue(const string& hname, string& val)
{
    unique_lock<mutex> lock(m->curlmutex);
    if (!m->headers_ok) {
        LOGERR("CurlFetch::headerValue: called with headers_ok == false\n");
        return false;
    }
    auto it = m->headers.find(hname);
    if (it != m->headers.end()) {
        val = it->second;
    } else {
        LOGERR("CurlFetch::headerValue: header " << hname << " not found\n");
        return false;
    }
    return true;
}

static size_t
curl_header_cb(void *contents, size_t size, size_t nmemb, void *userp)
{
    CurlFetch::Internal *me = (CurlFetch::Internal *)userp;
    return me ? me->curlHeaderCB(contents, size, nmemb) : -1;
}

size_t
CurlFetch::Internal::curlHeaderCB(void *contents, size_t size, size_t cnt)
{
    size_t bcnt = size * cnt;
    string header((char *)contents, bcnt);
    trimstring(header, " \t\r\n");
    LOGDEB1("CurlFetch::curlHeaderCB: header: [" << header << "]\n");
    unique_lock<mutex> lock(curlmutex);
    if (header.empty()) {
        // End of headers
        LOGDEB1("CurlFetch::curlHeaderCB: wake them up\n");
        headers_ok = true;
        curlcv.notify_all();
    } else {
        LOGDEB1("curlHeaderCB: got " << header << endl);
        string::size_type colon = header.find(":");
        if (string::npos != colon) {
            string hname = header.substr(0, colon);
            stringtolower(hname);
            string val = header.substr(colon+1);
            trimstring(val);
            headers[hname] = val;
        }
    }
    return bcnt;
}

static size_t
curl_write_cb(void *contents, size_t size, size_t nmemb, void *userp)
{
    CurlFetch::Internal *me = (CurlFetch::Internal *)userp;
    return me ? me->curlWriteCB(contents, size, nmemb) : -1;
}

#undef DUMP_CONTENTS
#ifdef DUMP_CONTENTS
#include "listmem.h"
#endif

size_t CurlFetch::Internal::curlWriteCB(void *contents, size_t size, size_t cnt)
{
    size_t bcnt = size * cnt;

#ifdef DUMP_CONTENTS
    LOGDEB("CurlWriteCB: bcnt " << bcnt << " headbuf.bytes " << headbuf.bytes << endl);
    listmem(cerr, contents, MIN(bcnt, 128));
#endif

    unique_lock<mutex> lock(curlmutex);

    if (p->datacount() == 0 && headbuf.bytes < 1024) {
        // Buffering into the stream header buffer
        if (!headbuf.append((const char *)contents, bcnt)) {
            LOGERR("CurlFetch::curlWriteCB: buf append failed\n");
            curlcv.notify_all();
            return -1;
        } else {
            curlcv.notify_all();
            return bcnt;
        }
    }
    // Done with header buffering

    if (p->datacount() == 0 && p->buf1cb) {
        // Head of stream: give the user a chance to prepend something (returned sbuf
        // contents) to the stream. The headbuf is passed only to possibly be looked at.
        string sbuf;
        if (!p->buf1cb(sbuf, headbuf.buf, headbuf.bytes)) {
            return -1;
        }
        if (sbuf.size()) {
            curlcv.notify_all();
            if (p->databufToQ(sbuf.c_str(), sbuf.size()) < 0) {
                return -1;
            }
        }
    }

    // Send out the header buffer then any additional data from this call
    if (headbuf.bytes) {
        if (p->datacount() == 0) {
            curlcv.notify_all();
        }
        p->databufToQ(headbuf.buf, headbuf.bytes);
        headbuf.bytes = 0;
    }
    if (p->datacount() == 0) {
        curlcv.notify_all();
    }
    return p->databufToQ(contents, bcnt);
}

static int debug_callback(CURL *curl,
                          curl_infotype type,
                          char *data,
                          size_t size,
                          void *userptr)
{
    string dt(data, size);
    string tt;
    switch (type) {
    case CURLINFO_TEXT: tt = "== Info"; break;
    default: tt = " ??? "; break;
    case CURLINFO_HEADER_OUT: tt = "=> Send header"; break;
    case CURLINFO_DATA_OUT: tt = "=> Send data"; break;
    case CURLINFO_SSL_DATA_OUT: tt = "=> Send SSL data"; break;
    case CURLINFO_HEADER_IN: tt = "<= Recv header"; break;
    case CURLINFO_DATA_IN:
        //LOGDEB("CURL: <= Recv data. cnt: " << size << endl);
        //listmem(cerr, data, 16);
        return 0;
    }
    LOGDEB("---CURL: " << tt << " " << dt);
    return 0; 
}

void CurlFetch::Internal::curlWorkerFunc()
{
    LOGDEB1("CurlFetch::curlWorkerFunc\n");
    (void)debug_callback;
    
    {unique_lock<mutex> lock(curlmutex);
        // Tell the world we're active (start is waiting for this).
        curlcv.notify_all();
    }
    
    if (!curl) {
        curl = curl_easy_init();
        if(!curl) {
            LOGERR("CurlFetch::curlWorkerFunc: curl_easy_init failed" << endl);
            {unique_lock<mutex> lock(curlmutex);
                curldone = true;
            }
            if (p->outqueue) {
                p->outqueue->setTerminate();
            }
            curlcv.notify_all();
            return;
        }
        curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, this);
        curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, curl_header_cb);
        curl_easy_setopt(curl, CURLOPT_HEADERDATA, this);

        curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 5);
        // Speedlimit is in bytes/S. 32Kbits/S
        curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 4L);
        curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 60);

        //curl_easy_setopt(curl, CURLOPT_VERBOSE, 1L);
        //curl_easy_setopt(curl, CURLOPT_DEBUGFUNCTION, debug_callback);

        // Chunk decoding: this is the default
        //curl_easy_setopt(curl, CURLOPT_HTTP_TRANSFER_DECODING, 1L);
    }
    
    LOGDEB0("CurlFetch::curlWorker: fetching " << p->_url << " timeout " <<
            p->timeoutsecs << " seconds\n");
    curl_easy_setopt(curl, CURLOPT_URL, p->_url.c_str());
    if (p->startoffset) {
        char range[32];
        sprintf(range, "%llu-", (unsigned long long)p->startoffset);
        curl_easy_setopt(curl, CURLOPT_RANGE, range);
    }
    if (p->timeoutsecs) {
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, p->timeoutsecs);
    }

    curl_code = curl_easy_perform(curl);
    LOGDEB1("CurlFetch::curlWorker: curl_easy_perform returned\n");

    bool http_ok = false;
    if (curl_code == CURLE_OK) {
        curl_easy_getinfo (curl, CURLINFO_RESPONSE_CODE, &curl_http_code);
        http_ok = curl_http_code >= 200 && curl_http_code < 300;
    }

    // Log/Debug
    if (curl_code != CURLE_OK || !http_ok) {
        if (curl_code != CURLE_OK) {
            LOGERR("CurlFetch::curlWorkerFunc: curl_easy_perform(): " <<
                   curl_easy_strerror(curl_code) << endl);
        } else {
            LOGDEB("CurlFetch::curlWorkerFunc: curl_easy_perform(): http code: "
                   << curl_http_code << endl);
        }
    }

    LOGDEB1("CurlFetch::curlWorker: locking\n");
    {unique_lock<mutex> lock(curlmutex);
        LOGDEB1("CurlFetch::curlWorker: locked\n");
        if (aborting) {
            return;
        }
        if (headbuf.bytes) {
            LOGDEB1("CurlFetch::curlWorker: flushing headbuf: " << headbuf.bytes << " bytes\n");
            curlcv.notify_all();
            p->databufToQ(headbuf.buf, headbuf.bytes);
            headbuf.bytes = 0;
        }
        curldone = true;
        curlcv.notify_all();
    }

    // Normal eos
    if (curl_code == CURLE_OK) {
        // Wake up other side with empty buffer (eof)
        LOGDEB1("CurlFetch::curlWorkerFunc: request done ok: q empty buffer\n");
        ABuffer *buf = new ABuffer(0);
        if (!p->outqueue || !p->outqueue->put(buf)) {
            delete buf;
        }
        if (p->outqueue) {
            // Wait for our zero buffer to be acknowledged before
            // killing the queue
            LOGDEB1("CurlFetch::curlworker: waitidle\n");
            p->outqueue->waitIdle();
        }
    }
    p->outqueue->setTerminate();
    if (p->eofcb) {
        p->eofcb(curl_code == CURLE_OK, p->datacount());
    }
    LOGDEB1("CurlFetch::curlworker: done\n");
    return;
}
