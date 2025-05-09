/* Copyright (C) 2017-2018 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU Lesser General Public License as published by
 *   the Free Software Foundation; either version 2.1 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU Lesser General Public License for more details.
 *
 *   You should have received a copy of the GNU Lesser General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include "streamproxy.h"
#include "netfetch.h"
#ifdef MDU_INCLUDE_LOG
#include MDU_INCLUDE_LOG
#else
#include "log.h"
#endif
#include "smallut.h"
#include "chrono.h"

#include <fcntl.h>

#include <microhttpd.h>

#if MHD_VERSION <= 0x00097000
#define MHD_Result int
#endif

#include <mutex>
#include <condition_variable>
#include <unordered_map>

using namespace std;

class ContentReader {
public:
    ContentReader(std::unique_ptr<NetFetch> ftchr, int cfd)
        : fetcher(std::move(ftchr)), connfd(cfd) {
        
        // Set a timeout on the client side, so that connections can
        // be cleaned-up in a timely fashion if we stop providing
        // data. This is mostly for the versions of mpd which read the
        // top of the file then restart: the first connection would
        // never be cleaned up because it was waiting on the queue
        // which was not sending data (at least in the spotify case)
        // because the proxy was used for the second request.
        queue.set_take_timeout(std::chrono::milliseconds(std::chrono::seconds(10)));
    }

    ~ContentReader() {
        LOGDEB1("ContentReader::~ContentReader\n");
        // This should not be necessary but:  (also see tstcurlfetch code)
        // !! Note !! have to delete the fetcher before returning, else
        // the notify_all in the bufxchange setTerminate() will
        // block. Looks like a libc bug to me ? but easy workaround.
        fetcher = std::unique_ptr<NetFetch>();
    }
    ssize_t contentRead(uint64_t pos, char *buf, size_t max);

    std::unique_ptr<NetFetch> fetcher;
    BufXChange<ABuffer*> queue{"crqueue"};
    bool normalEOS{false};
    // Used for experimentations in killing the connection
    int connfd{-1};
    int killafterms{-1};
    Chrono chron;
};


ssize_t ContentReader::contentRead(uint64_t pos, char *obuf, size_t max)
{
    LOGDEB1("ContentReader::contentRead: pos "<<pos << " max " << max << "\n");
    if (normalEOS) {
        LOGDEB1("ContentReader::contentRead: return EOS\n");
        return MHD_CONTENT_READER_END_OF_STREAM;
    }
    size_t totcnt = 0;
    ABuffer *abuf;
    while (totcnt < max) {
        if (!queue.take(&abuf)) {
            NetFetch::FetchStatus code;
            int httpcode;
            fetcher->fetchDone(&code, &httpcode);
            LOGDEB("Reader: queue take failed code " << code <<
                   " httpcode " << httpcode << "\n");
            if (code == NetFetch::FETCH_RETRYABLE) {
                LOGINF("Reader: retrying at " << pos+totcnt << "\n");
                fetcher->reset();
                fetcher->start(&queue, pos+totcnt);
                return 0;
            }
            LOGDEB("ContentReader::contentRead: return ERROR\n");
            return MHD_CONTENT_READER_END_WITH_ERROR;
        }
        LOGDEB1("ContentReader::contentRead: got buffer with " << abuf->bytes << " bytes\n");
        if (abuf->bytes == 0) {
            normalEOS = true;
            if (totcnt == 0) {
                LOGDEB1("ContentReader::contentRead: return EOS\n");
                return MHD_CONTENT_READER_END_OF_STREAM;
            } else {
                // Copied data, we will return eostream on next call.
                break;
            }
        }
        size_t tocopy = MIN(max-totcnt, abuf->bytes - abuf->curoffs);
        memcpy(obuf + totcnt, abuf->buf + abuf->curoffs, tocopy);
        totcnt += tocopy;
        abuf->curoffs += tocopy;
        if (abuf->curoffs >= abuf->bytes) {
            queue.recycle(abuf);
        } else {
            queue.untake(abuf);
        }
    }
    if (killafterms > 0 && connfd >= 0) {
        if (chron.millis() > killafterms) {
            int fd = open("/dev/null", 0);
            if (fd < 0) {
                abort();
            }
            dup2(fd, connfd);
            close(fd);
            connfd = -1;
        }
    }
    LOGDEB1("ContentReader::contentRead: return " << totcnt << "\n");
    return totcnt;
}

static ssize_t content_reader_cb(void *cls, uint64_t pos, char *buf, size_t max)
{
    ContentReader *reader = static_cast<ContentReader*>(cls);
    if (reader) {
        return reader->contentRead(pos, buf, max);
    } else {
        return -1;
    }
}

static void content_reader_free_callback(void *cls)
{
    if (cls) {
        ContentReader *reader = static_cast<ContentReader*>(cls);
        delete reader;
    }
    LOGDEB0("content_reader_free_callback returning\n");
}

class StreamProxy::Internal {
public:
    Internal(int listenport, UrlTransFunc urlt);
    ~Internal();
    bool startMHD();

    MHD_Result answerConn(
        struct MHD_Connection *connection, const char *url, 
        const char *method, const char *version, 
        const char *upload_data, size_t *upload_data_size,
        void **con_cls);

    void requestCompleted(
        struct MHD_Connection *conn,
        void **con_cls, enum MHD_RequestTerminationCode toe);

    int listenport{-1};
    UrlTransFunc urltrans;
    struct MHD_Daemon *mhd{nullptr};
    int killafterms{-1};
};


StreamProxy::StreamProxy(int listenport, UrlTransFunc urltrans)
    : m(new Internal(listenport, urltrans))
{
}

void StreamProxy::setKillAfterMs(int ms)
{
    m->killafterms = ms;
}

StreamProxy::~StreamProxy()
{
}

StreamProxy::Internal::~Internal()
{
    LOGDEB("StreamProxy::Internal::~Internal()\n");
    if (mhd) {
        MHD_stop_daemon(mhd);
        mhd = nullptr;
    }
}

StreamProxy::Internal::Internal(int _listenport, UrlTransFunc _urltrans)
    : listenport(_listenport), urltrans(_urltrans)
{
    startMHD();
}


static MHD_Result answer_to_connection(
    void *cls, struct MHD_Connection *conn, const char *url, const char *method,
    const char *version, const char *upload_data, size_t *upload_data_size, void **con_cls)
{
    auto internal = static_cast<StreamProxy::Internal*>(cls);
    if (nullptr == internal) {
        return MHD_NO;
    }
    return internal->answerConn(conn, url, method, version, upload_data, upload_data_size, con_cls);
}

#undef PRINT_KEYS
#ifdef PRINT_KEYS
static vector<CharFlags> valueKind {
    {MHD_HEADER_KIND, "HTTP header"},
    {MHD_COOKIE_KIND, "Cookies"},
    {MHD_POSTDATA_KIND, "POST data"},
    {MHD_GET_ARGUMENT_KIND, "GET (URI) arguments"},
    {MHD_FOOTER_KIND, "HTTP footer"},
        };

// We're not supposed to receive a null value because we're called for MHD_HEADER_KIND, but play it
// safe.
static MHD_Result print_out_key (
    void *cls, enum MHD_ValueKind kind, const char *key, const char *_value)
{
    const char *value = _value ? _value : "";
    LOGDEB(valToString(valueKind, kind) << ": " << key << " -> " << value << "\n");
    return MHD_YES;
}
#endif /* PRINT_KEYS */

// Note: the value argument can be null with kind == MHD_ARGUMENT_KIND for a query like
// http://foo/bar?key (no equal sign). It would be an empty string for http://foo/bar?key= We treat
// both cases in the same way at the moment.
static MHD_Result mapvalues_cb(
    void *cls, enum MHD_ValueKind kind, const char *key, const char *_value)
{
    const char *value = _value ? _value : "";
    auto mp = static_cast<unordered_map<string,string> *>(cls);
    if (mp) {
        (*mp)[key] = value;
    }
    return MHD_YES;
}

static bool processRange(struct MHD_Connection *mhdconn, uint64_t& offset)
{
    const char* rangeh = MHD_lookup_connection_value(mhdconn, MHD_HEADER_KIND, "range");
    if (!rangeh) {
        LOGDEB1("NO RANGE\n");
        return true;
    }
    LOGDEB1("StreamProxy: got range header: " << rangeh << "\n");
    vector<pair<int64_t, int64_t> > ranges;
    if (parseHTTPRanges(rangeh, ranges) && ranges.size()) {
        // For now we only accept requests from positive offset to end, not "last n bytes" requests
        // nor actual intervals nor multiple ranges. A better solution would be to just refuse
        // multiple ranges, compute the size for the others (needed for mhd_create_response), pass
        // the whole range data to curl and just forward the resulting content-length and
        // content-range headers (like we do currently).
        if (ranges[0].first == -1 || ranges[0].second != -1 || ranges.size() > 1) {
            LOGERR("AProxy::mhdAnswerConn: unsupported range: " << rangeh << "\n");
            struct MHD_Response *response = 
                MHD_create_response_from_buffer(0,0,MHD_RESPMEM_PERSISTENT);
            MHD_queue_response(mhdconn, 416, response);
            MHD_destroy_response(response);
            return false;
        } else {
            offset = (uint64_t)ranges[0].first;
            LOGDEB0("StreamProxy:processRange " << rangeh << " offset " << offset << "\n");
        }
    }
    return true;
}

MHD_Result StreamProxy::Internal::answerConn(
    struct MHD_Connection *mhdconn, const char *_url, const char *method, const char *version,
    const char *upload_data, size_t *upload_data_size, void **con_cls)
{
    LOGDEB0("StreamProxy::answerConn: method " << method << " vers " << version <<
            " con_cls " << *con_cls << " url " << _url << "\n");
    NetFetch::FetchStatus fetchcode;
    int httpcode;

    if (nullptr == *con_cls) {
        uint64_t offset = 0;
        // First call, look at headers, method etc.
#ifdef PRINT_KEYS
        MHD_get_connection_values(mhdconn, MHD_HEADER_KIND, &print_out_key, 0);
#endif
        if (strcmp("GET", method) && strcmp("HEAD", method)) {
            LOGERR("StreamProxy::answerConn: method is not GET or HEAD\n");
            return MHD_NO;
        }
        if (!processRange(mhdconn, offset)) {
            return MHD_NO;
        }

        // Compute destination url
        unordered_map<string,string> querydata;
        MHD_get_connection_values(mhdconn, MHD_GET_ARGUMENT_KIND, &mapvalues_cb, &querydata);
        std::string useragent;
        const char *ua = MHD_lookup_connection_value(mhdconn,MHD_HEADER_KIND, "user-agent");
        if (ua)
            useragent = ua;

        // Request the method (redirect or proxy), and the fetcher if we are proxying.
        string url(_url);
        std::unique_ptr<NetFetch> fetcher;
        UrlTransReturn ret = urltrans(useragent, url, querydata, fetcher);
        
        if (ret == Error) {
            return MHD_NO;
        } else if (ret == Redirect) {
            struct MHD_Response *response =
                MHD_create_response_from_buffer(0, 0, MHD_RESPMEM_PERSISTENT);
            if (nullptr == response ) {
                LOGERR("StreamProxy::answerConn: can't create redirect\n");
                return MHD_NO;
            }
            MHD_add_response_header(response, "Location", url.c_str());
            MHD_Result ret = MHD_queue_response(mhdconn, 302, response);
            MHD_destroy_response(response);
            return ret;
        }

        // The connection fd thing is strictly for debug/diag: faking
        // a connection loss so that the client side can exercise the
        // retry code.
        int cfd{-1};
        const union MHD_ConnectionInfo *cinf =
            MHD_get_connection_info(mhdconn, MHD_CONNECTION_INFO_CONNECTION_FD);
        if (nullptr == cinf) {
            LOGERR("StreamProxy::answerConn: can't get connection fd\n");
        } else {
            cfd = cinf->connect_fd;
        }

        // Create/Start the fetch transaction.
        LOGDEB0("StreamProxy::answerConn: starting fetch for " << url << "\n");
        auto reader = new ContentReader(std::move(fetcher), cfd);
        if (killafterms > 0) {
            reader->killafterms = killafterms;
            killafterms = -1;
        }
        reader->fetcher->start(&reader->queue, offset);
        *con_cls = reader;

        LOGDEB1("StreamProxy::answerConn: returning after 1st call\n");
        return MHD_YES;
        // End first call
    }

    // Second call for this request (*con_cls is set)
    ContentReader *reader = (ContentReader*)*con_cls;
    
    if (!reader->fetcher->waitForHeaders()) {
        LOGDEB("StreamProxy::answerConn: waitForHeaders error\n");
        reader->fetcher->fetchDone(&fetchcode, &httpcode);
        int code = httpcode ? httpcode : MHD_HTTP_INTERNAL_SERVER_ERROR;
        struct MHD_Response *response =
            MHD_create_response_from_buffer(0, 0, MHD_RESPMEM_PERSISTENT);
        MHD_Result ret = MHD_queue_response(mhdconn, code, response);
        MHD_destroy_response(response);
        LOGINF("StreamProxy::answerConn (1): error return with http code: " << code << "\n");
        return ret;
    }
    LOGDEB1("StreamProxy::answerConn: waitForHeaders done\n");

    string cl;
    uint64_t size = MHD_SIZE_UNKNOWN;
    if (reader->fetcher->headerValue("content-length", cl) && !cl.empty()) {
        LOGDEB1("mhdAnswerConn: header content-length: " << cl << "\n");
        size = (uint64_t)atoll(cl.c_str());
    }
    // Build a data response.
    // the block size seems to be flatly ignored by libmicrohttpd
    // Any random value would probably work the same
    struct MHD_Response *response = MHD_create_response_from_callback(
        size, 4096, content_reader_cb, reader, content_reader_free_callback);
    if (nullptr == response) {
        LOGERR("mhdAnswerConn: answer: could not create response" << "\n");
        return MHD_NO;
    }

    int code = MHD_HTTP_OK;
    std::string cr;
    if (reader->fetcher->headerValue("content-range", cr) && !cr.empty()) {
        LOGDEB0("mhdAnswerConn: setting Content-Range " << cr << "\n");
        MHD_add_response_header(response, "Content-Range" , cr.c_str());
        code = 206;
    }
    MHD_add_response_header (response, "Accept-Ranges", "bytes");
    if (!cl.empty()) {
        LOGDEB0("mhdAnswerConn: setting Content-Length " << cl << "\n");
        MHD_add_response_header(response, "Content-Length", cl.c_str());
    }
    std::string ct;
    if (reader->fetcher->headerValue("content-type", ct) && !ct.empty()) {
        LOGDEB0("mhdAnswerConn: setting Content-Type: " << ct << "\n");
        MHD_add_response_header(response, "Content-Type", ct.c_str());
    }
    MHD_add_response_header (response, "Connection", "close");

    LOGDEB1("StreamProxy::answerConn: calling fetchDone to check for early end\n");
    if (reader->fetcher->fetchDone(&fetchcode, &httpcode)) {
        code = httpcode ? httpcode : MHD_HTTP_INTERNAL_SERVER_ERROR;
    }
    MHD_Result ret = MHD_queue_response(mhdconn, code, response);
    MHD_destroy_response(response);
    return ret;
}

static void
request_completed_callback(
    void *cls, struct MHD_Connection *conn,
    void **con_cls, enum MHD_RequestTerminationCode toe)
{
    // We get this even if the answer callback returned MHD_NO
    // (e.g. for a second connection). check con_cls and do nothing if
    // it's not set.
    if (cls && *con_cls) {
        StreamProxy::Internal *internal = static_cast<StreamProxy::Internal*>(cls);
        internal->requestCompleted(conn, con_cls, toe);
    }
}

static vector<CharFlags> completionStatus {
    {MHD_REQUEST_TERMINATED_COMPLETED_OK,
            "MHD_REQUEST_TERMINATED_COMPLETED_OK", ""},
    {MHD_REQUEST_TERMINATED_WITH_ERROR,
            "MHD_REQUEST_TERMINATED_WITH_ERROR", ""},
    {MHD_REQUEST_TERMINATED_TIMEOUT_REACHED,
            "MHD_REQUEST_TERMINATED_TIMEOUT_REACHED", ""},
    {MHD_REQUEST_TERMINATED_DAEMON_SHUTDOWN,
            "MHD_REQUEST_TERMINATED_DAEMON_SHUTDOWN", ""},
    {MHD_REQUEST_TERMINATED_READ_ERROR,
            "MHD_REQUEST_TERMINATED_READ_ERROR", ""},
    {MHD_REQUEST_TERMINATED_CLIENT_ABORT,
            "MHD_REQUEST_TERMINATED_CLIENT_ABORT", ""},
        };

void StreamProxy::Internal::requestCompleted(
    struct MHD_Connection *conn,
    void **con_cls, enum MHD_RequestTerminationCode toe)
{
    LOGDEB("StreamProxy::requestCompleted: status " <<
           valToString(completionStatus, toe) << " *con_cls "<< *con_cls << "\n");
    // The content reader will supposedly be deleted by the content_reader_free
    // callback which is called right after us
}

bool StreamProxy::Internal::startMHD()
{
    mhd = MHD_start_daemon(
        MHD_USE_THREAD_PER_CONNECTION|MHD_USE_SELECT_INTERNALLY|MHD_USE_DEBUG,
        listenport, 
        /* Accept policy callback and arg */
        nullptr, nullptr, 
        /* handler and arg */
        &answer_to_connection, this,
        MHD_OPTION_NOTIFY_COMPLETED, request_completed_callback, this,
        MHD_OPTION_END);

    if (nullptr == mhd) {
        LOGERR("Aproxy: MHD_start_daemon failed\n");
        return false;
    }

    return true;
}
