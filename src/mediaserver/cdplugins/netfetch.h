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
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#ifndef _MEDIAFETCH_H_INCLUDED_
#define _MEDIAFETCH_H_INCLUDED_

#include <functional>

#include "bufxchange.h"
#include "abuffer.h"

//
// Wrapper for a network fetch
//
// The transfer is aborted when the object is deleted, with proper
// cleanup.
//
// The end of transfer is marked by pushing an empty buffer on the queue
//
// All methods are supposedly thread-safe
class NetFetch {
public:
    NetFetch(const std::string& u)
        : _url(u) {
    }
    virtual ~NetFetch() {}

    virtual const std::string& url() {
        return _url;
    }
    
    virtual void setTimeout(int secs) {
        timeoutsecs = secs;
    }
    
    /// Start the transfer to the output queue.
    virtual bool start(BufXChange<ABuffer*> *queue, uint64_t offset = 0) = 0;

    // Wait for headers. This allows, e.g. doing stuff depending on
    // content-type before proceeding with the actual data
    // transfer. May not work exactly the same depending on the
    // underlaying implementation.
    virtual bool waitForHeaders(int maxSecs = 0) = 0;
    // Retrieve header value (after a successful waitForHeaders).
    virtual bool headerValue(const std::string& nm, std::string& val) = 0;

    // Check if the fetch is done and retrieve the results if it
    // is. This does not wait, it returns false if the transfer is
    // still running.
    // The pointers can be set to zero if no value should be retrieved
    enum FetchStatus {FETCH_OK=0, FETCH_RETRYABLE, FETCH_FATAL};
    virtual bool fetchDone(FetchStatus *code, int *http_code) = 0;

    /// Reset after transfer done, for retrying for exemple.
    virtual bool reset() = 0;

    uint64_t datacount() {
        return fetch_data_count;
    }

    // Callbacks

    // A function to create the first buffer (typically for prepending
    // a wav header to a raw pcm stream. If set this is called from
    // the first curl write callback, before processing the curl data,
    // so this happens at a point where the client may have had a look
    // at the headers).
    virtual void setBuf1GenCB(std::function<bool(
                                  std::string& buf, void*, int)> f) {
        buf1cb = f;
    }
    // Called when the network transfer is done
    void setEOFetchCB(std::function<void(bool ok, uint64_t count)> f) {
        eofcb = f;
    }
    // Called every time we get new data from the remote
    void setFetchBytesCB(std::function<void(uint64_t count)> f) {
        fbcb = f;
    }

protected:
    size_t databufToQ(const void *contents, size_t bcnt);
        
    std::string _url;
    uint64_t startoffset;
    int timeoutsecs{0};
    uint64_t fetch_data_count{0};
    BufXChange<ABuffer*> *outqueue{nullptr};
    std::function<bool(std::string&, void *, int)> buf1cb;
    std::function<void(uint64_t)> fbcb;
    std::function<void(bool, uint64_t)> eofcb;
};

#endif /* _MEDIAFETCH_H_INCLUDED_ */
