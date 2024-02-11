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

#ifndef _SPOTIPROXY_H_INCLUDED_
#define _SPOTIPROXY_H_INCLUDED_

#include <string>
#include <memory>
#include <functional>

#include "bufxchange.h"
#include "abuffer.h"
#include "netfetch.h"

   
/** 
 * Represent a Spotify session, and possibly a single active play transaction
 */
class SpotiProxy {
public:

    /** 
     * Create/get reference to the SpotiProxy singleton. Call with
     * actual user/pass the first time. Later calls can either use the
     * same pair or empty values. cachedir and settingsdir can't change either.
     */
    static SpotiProxy *getSpotiProxy(
        const std::string& user = "", const std::string& pass = "",
        const std::string& cachedir="", const std::string& settingsdir=""
        );

    /** Alternatively, the login parameters can be set by a separate call prior
     *  to the above, and independantly from login. All calls to
     *  getSpotiProxy() can then be param-less */
    static void setParams(
        const std::string& user, const std::string& pass,
        const std::string& cachedir, const std::string& settingsdir);

    ~SpotiProxy();

    const std::string& getReason();

    bool loginOk();

    typedef std::function<int (
        const void *frames, int num_frames, int channels, int rate)> AudioSink;

    bool playTrack(const std::string& trackid, AudioSink sink,
                     int seekmsecs = 0);

    bool startPlay(const std::string& trackid, AudioSink sink,
                     int seekmsecs = 0);
    bool waitForEndOfPlay();

    bool isPlaying();
    int durationMs();
    
    void stop();
    
    class Internal;
private:
    SpotiProxy(const std::string&, const std::string&, const std::string&,
               const std::string&);
    std::unique_ptr<Internal> m;
};


//
// NetFetch adapter for libspotify audio streams
class SpotiFetch : public NetFetch {
public:
    SpotiFetch(const std::string& url);
    ~SpotiFetch();

    /// Start the transfer to the output queue.
    bool start(BufXChange<ABuffer*> *queue, uint64_t offset = 0) override;

    // Wait for HTTP headers. This allows, e.g. doing stuff depending
    // on content-type before proceeding with the actual data transfer
    bool waitForHeaders(int maxSecs = 0) override;
    // Retrieve header value (after a successful waitForHeaders).
    bool headerValue(const std::string& nm, std::string& val) override;

    // Check if the fetch operation is done and retrieve the results
    // if it is. This does not wait, it returns false if the transfer
    // is still running.
    bool fetchDone(FetchStatus *code, int *http_code) override;

    /// Reset after transfer done, for retrying for exemple.
    bool reset() override;

    class Internal;
private:
    std::unique_ptr<Internal> m;
};

#endif /* _SPOTIPROXY_H_INCLUDED_ */
