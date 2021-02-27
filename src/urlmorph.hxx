/* Copyright (C) 2016-2021 J.F.Dockes
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
#ifndef _URLMORPH_H_INCLUDED_
#define _URLMORPH_H_INCLUDED_

// Translating special form URLs.
//
// OHCredentials:
//   Called from OHPlaylist. The CP (Kazoo/Lumin mostly) will send URIs
//   like qobuz:// tidal:// and expect the renderer to know what to do
//   with them. We transform them so that they point to our media server
//   gateway (which should be running of course for this to work).
//   The URLs from kazoo look like:
//     <service>://track?version=2&trackId=<trkid>
//   We translate them to something which points to our proxy server, and
//   that MPD will accept/use:
//     http://<upnphost>:<sport>/<servicename>/track?version=1&trackId=<trkid>
//   Where upnphost is the host used by libupnp, and sport the port on
//   which the microhttpd listens.
//   We retrieve upnphost from the upnp device during init, and sport by a
//   call to the CDPluginServices.
// 
// CDDA:
//   Some control points don't like urls like cdda:///dev/sr0, they
//   want everything to be http. We get these through with
//       http://_protoescape/proto/path
//   which we transform into
//       proto:///path


#include <string>


bool morphSpecialUrl(std::string& url, bool& forcenocheck,
                     const std::string& upnphost = std::string());

#endif // _URLMORPH_H_INCLUDED

