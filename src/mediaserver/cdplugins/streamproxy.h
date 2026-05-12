/* Copyright (C) 2017-2026 J.F.Dockes
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

#ifndef _STREAMPROXY_H_INCLUDED_
#define _STREAMPROXY_H_INCLUDED_

#include <memory>
#include <functional>
#include <string>
#include <unordered_map>

class NetFetch;

/// HTTP proxy for UPnP audio transfers
///
/// Uses microhttpd for the server part and libcurl for talking to the real server.
///
class StreamProxy {
public:

    /** Return values from the urltrans callback function. */
    enum UrlTransReturn {Error, Proxy, Redirect, Respond};

    /** The fetch method deciding function
     * @param useragent the user agent string sent by the client.
     * @param[in,out] url The original URL from the client, changed in place. If the return value
     *    is UrlTransReturn::Respond, this holds the response body.
     * @param queryparams The HTTP query parameters (?nm=value;..)
     * @param[out] fetcher if we are proxying, the fetcher object used 
     *   to get the data. Ownership is transferred to us.
     * @return The value tells us how the client request is to be satisfied.
     *   Proxy: fetch and serve the data. Redirect: use the url value with a 302.
     *   Respond: use the response data.
     */
    typedef std::function<UrlTransReturn
                          (const std::string& useragent,
                           std::string& url,
                           const std::unordered_map<std::string, std::string>& queryparams,
                           std::unique_ptr<NetFetch>& fetcher)> UrlTransFunc;

    StreamProxy(int listenport, UrlTransFunc urltrans);
    ~StreamProxy();

    // Debug and experiments: kill connections after ms mS
    void setKillAfterMs(int ms);
    
    class Internal;
private:
    std::unique_ptr<Internal> m;
};

#endif /* _STREAMPROXY_H_INCLUDED_ */
