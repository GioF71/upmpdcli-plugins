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
#ifndef _PLGWITHSLAVE_H_INCLUDED_
#define _PLGWITHSLAVE_H_INCLUDED_

#include <vector>

#include "cdplugin.hxx"
#include "libupnpp/device/vdir.hxx"

class CmdTalk;

// Interface to a content plugin implemented through a Python subprocess,
// e.g. the Tidal, Qobuz and Gmusic interfaces.
//
// Note that we may have to subclass this for different services one
// day. For now, all services use compatible cmdtalk methods
// (esp. get_media_url()), so that all the customisation is on the
// Python side.
class PlgWithSlave : public CDPlugin {
public:
    PlgWithSlave(const std::string& name, CDPluginServices *services);
    virtual ~PlgWithSlave();

    // Proxy the streams if return is true, else redirect
    virtual bool doproxy();
    
    // Returns totalmatches
    virtual int browse(
    const std::string& objid, int stidx, int cnt,
    std::vector<UpSong>& entries,
    const std::vector<std::string>& sortcrits = std::vector<std::string>(),
    BrowseFlag flg = BFChildren);

    virtual int search(
    const std::string& ctid, int stidx, int cnt,
    const std::string& searchstr,
    std::vector<UpSong>& entries,
    const std::vector<std::string>& sortcrits = std::vector<std::string>());

    // This is for internal use only, but moving it to Internal would
    // make things quite more complicated for a number of reasons.
    virtual std::string get_media_url(const std::string& path);

    // used for plugins which should start initialization asap
    bool startInit();

    // Used by ohcredentials to start a plugin instance
    static bool startPluginCmd(CmdTalk& cmd, const std::string& appname,
                               const std::string& host, unsigned int port,
                               const std::string& pathprefix);
    static bool maybeStartProxy(CDPluginServices *cdsrv);

    class Internal;
private:
    Internal *m;
};

#endif /* _PLGWITHSLAVE_H_INCLUDED_ */
