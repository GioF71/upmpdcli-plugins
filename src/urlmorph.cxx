/* Copyright (C) 2018-2021 J.F.Dockes
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the
 * Free Software Foundation, Inc.,
 * 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include "config.h"

#include "urlmorph.hxx"

#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"
#include "mediaserver/cdplugins/cdplugin.hxx"
#include "pathut.h"

#include <regex>

using namespace std;

static const string protoescape{"http://upmpdprotoescape/"};

// http://wiki.openhome.org/wiki/Av:Developer:Eriskay:StreamingServices
// Tidal and qobuz tracks added by Kazoo / Lumin: 
//   tidal://track?version=1&trackId=[tidal_track_id]
//   qobuz://track?version=2&trackId=[qobuz_track_id]
static const string tidqob_restr{
    "(tidal|qobuz)://track\\?version=([[:digit:]]+)&trackId=([[:digit:]]+)"};
static std::regex tidqob_re(tidqob_restr);

bool morphSpecialUrl(string& url, bool& forcenocheck, const std::string& upnphost)
{
    forcenocheck = false;

    // We accept special cloaked cdda URLs and translate them because
    // some control points can't grok cdda:///1 and forbid cd-based
    // playlists
    if (url.find(protoescape) == 0) {
        auto protoend = url.find('/', protoescape.size());
        if (protoend != string::npos) {
            auto protoname = url.substr(protoescape.size(), protoend-protoescape.size());
            url.replace(0, protoescape.size() + protoname.size(), protoname + "://");
        }
        forcenocheck = true;
        return true;
    }

    if (url.find("http://") == 0 || url.find("https://") == 0) {
        return true;
    }

    // Possibly retrieve the IP port used by our proxy server
    static string sport;
    if (sport.empty()) {
        sport = UPnPP::SoapHelp::i2s(CDPluginServices::microhttpport());
    }

    // Is this a qobuz/tidal track added from e.g. OHCredentials-using Kazoo ? Then morph it to
    // something the plugin can use.
    std::smatch mr;
    bool found = std::regex_match(url, mr, tidqob_re);
    if (found) {
        string pathprefix = CDPluginServices::getpathprefix(mr[1]);
        // The microhttpd code actually only cares about getting a trackId parameter. Make it look
        // what the plugins normally generate anyway:
        string path = path_cat(pathprefix, "track?version=1&trackId=" + mr[3].str());
        url = string("http://") + upnphost + ":" + sport + path;
        forcenocheck = true;
    }
    return true;
}
