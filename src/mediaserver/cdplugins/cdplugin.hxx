/* Copyright (C) 2016 J.F.Dockes
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
#ifndef _CDPLUGIN_H_INCLUDED_
#define _CDPLUGIN_H_INCLUDED_

#include <string>
#include "upmpdutils.hxx"
#include "libupnpp/device/vdir.hxx"

class CDPluginServices;

/// Interface to Content Directory plugins
///
/// The main operations, Browse and Search, return content as UpSong
/// structures. At the very minimum, id, parentid, iscontainer and
/// title should be properly set for each entry. Id is very important for
/// directories (containers), because this is the main parameter to
/// the browse call. title is what gets displayed in lists by the
/// control point.
///
/// The rest of the UpSong fields are only meaningful for items
/// (tracks), and only one is mandatory: uri.
///
/// The item uri will be used by the renderer for fetching the data to
/// be played. All current implementations set URIs which point either
/// to themselves (uprcl, the implementation for local files, uses a
/// Python server to stream the files), or to a microhttpd instance
/// running inside upmpdcli, with code responsible for either
/// redirecting the client or proxying the data.
class CDPlugin {
public:
    CDPlugin(const std::string& name, CDPluginServices *services)
        : m_name(name), m_services(services) {
    }
    virtual ~CDPlugin() {
    }

    /// List children or return metadata for target object. You can
    /// probably get by without implementing BFMeta in most cases.
    enum BrowseFlag {BFChildren, BFMeta};

    /// Browse object at objid, which should be a container, and
    /// return its content. 
    ///
    /// This reflects an UPnP Browse action. Refer to UPnP documentation.
    /// 
    /// @param objid the object to browse. The top directory for a plugin will
    //     be '0$plugin_name$', e.g. '0$qobuz$'
    /// @param stidx first entry to return.
    /// @param cnt number of entries.
    /// @param[output] entries output content.
    /// @param sortcrits csv list of sort criteria.
    /// @param flg browse flag
    /// @return total number of matched entries in container
    virtual int browse(
    const std::string& objid, int stidx, int cnt,
    std::vector<UpSong>& entries,
    const std::vector<std::string>& sortcrits = std::vector<std::string>(),
    BrowseFlag flg = BFChildren) = 0;

    /// Search under object at objid.
    ///
    /// This reflects an UPnP Search action, refer to UPnP
    /// documentation. Most plugins won't be able to actually perform
    /// the search under container operation. Plain search should be
    /// good enough.
    /// 
    /// @param objid the object to search
    /// @param stidx first entry to return.
    /// @param cnt number of entries.
    /// @param[output] entries output content.
    /// @param sortcrits csv list of sort criteria.
    /// @return total number of matched entries in container
    virtual int search(
    const std::string& ctid, int stidx, int cnt,
    const std::string& searchstr,
    std::vector<UpSong>& entries,
    const std::vector<std::string>& sortcrits = std::vector<std::string>())
    = 0;

    const std::string& getname() {
        return m_name;
    }

    virtual bool startInit() = 0;

    std::string m_name;
    CDPluginServices *m_services;
};

/// Service/Environment interface for media server modules. This is
/// implemented by the ContentDirectory class.
class CDPluginServices {
public:
    /// Returns the plugin to which belongs the parameter path, based
    /// on the path prefix above.
    virtual CDPlugin *getpluginforpath(const std::string& path) = 0;

    /// Retrieve the "friendly name" for the media server, for display
    /// purposes.
    virtual std::string getfname() = 0;
    
    /// IP address and port used by the libupnp HTTP server.
    ///
    /// This is the host address / network interface and port used by
    /// libupnp, which only supports one. URLs intended to be served
    /// by the libupnp miniserver (by adding a vdir) should should use
    /// this address as this is the only one guaranteed to be
    /// accessible from clients (in case this server has several
    /// interfaces). These calls are unused at present because no
    /// plugin uses the libupnp miniserver (tidal/qobuz/spotify/google
    /// use the microhttpd started by plgwithslave and uprcl uses a
    /// python server).
    virtual std::string getupnpaddr(CDPlugin *) = 0;
    virtual int getupnpport(CDPlugin *) = 0;

    /// Port on which the microhttp server listens on. Static because
    /// needed to start a proxy in conjunction with ohcredentials.
    /// Port 49149 is used by default. The value can be changed with
    /// the "plgmicrohttpport" configuration variable.
    ///
    /// Note: The local mediaserver (uprcl) uses neither the libupnp
    /// HTTP server nor microhttpd, but an internal Python server
    /// instance, on port 9090 by default (can be changed with the
    /// "uprclhostport" configuration variable).
    static int microhttpport();

    /// microhttp server IP host. The default is to use the same
    /// address as the UPnP device. This can be changed with
    /// "plgmicrohttphost". The only use would be to set it to
    /// 127.0.0.1, restricting the use of the media server to a
    /// (typically upmpcli) renderer running on the same host, but
    /// allowing playlists to be portable to another network.
    virtual std::string microhttphost() = 0;
    
    /// For modules which use the common microhttpd server
    /// (tidal/qobuz/gmusic). Returns something like "/tidal" (no end
    /// slash), which must be inserted at the top of the track URLs
    /// paths so that an HTTP request can be processed-for /
    /// dispatched-to the right plugin.
    static std::string getpathprefix(CDPlugin *plg) {
        return getpathprefix(plg->getname());
    }
    static std::string getpathprefix(const std::string& name) {
        return std::string("/") + name;
    }
};

#endif /* _CDPLUGIN_H_INCLUDED_ */
