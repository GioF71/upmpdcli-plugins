/* Copyright (C) 2014-2020 J.F.Dockes
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU Lesser General Public License as published by
 *  the Free Software Foundation; either version 2.1 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU Lesser General Public License for more details.
 *
 *  You should have received a copy of the GNU Lesser General Public License
 *  along with this program; if not, write to the
 *  Free Software Foundation, Inc.,
 *  59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#ifndef _OHPLAYLIST_H_X_INCLUDED_
#define _OHPLAYLIST_H_X_INCLUDED_

#include <string>
#include <unordered_map>
#include <vector>

#include "libupnpp/device/device.hxx"
#include "libupnpp/soaphelp.hxx"

#include "mpdcli.hxx"
#include "ohservice.hxx"

using namespace UPnPP;

class UpMpdOpenHome;

class OHPlaylist : public OHService {
public:
    /// @param dev the main upmpdcli renderer object with links to the upnp/av side and helper
    ///  methods.
    /// @param udev the OpenHome upnp device which owns me as a service.
    OHPlaylist(UpMpd *dev, UpMpdOpenHome *udev, unsigned int cachesavesleep);

    // These are used by other services (ohreceiver etc.)
    bool cacheFind(const std::string& uri, std::string& meta);
    bool urlMap(std::unordered_map<int, std::string>& umap);
    int iStop();
    // When changing sources
    void setActive(bool onoff);

protected:
    virtual bool makestate(std::unordered_map<std::string, std::string> &st);

private:
    int play(const SoapIncoming& sc, SoapOutgoing& data);
    int pause(const SoapIncoming& sc, SoapOutgoing& data);
    int stop(const SoapIncoming& sc, SoapOutgoing& data);
    int next(const SoapIncoming& sc, SoapOutgoing& data);
    int previous(const SoapIncoming& sc, SoapOutgoing& data);
    int setRepeat(const SoapIncoming& sc, SoapOutgoing& data);
    int repeat(const SoapIncoming& sc, SoapOutgoing& data);
    int setShuffle(const SoapIncoming& sc, SoapOutgoing& data);
    int shuffle(const SoapIncoming& sc, SoapOutgoing& data);
    int seekSecondAbsolute(const SoapIncoming& sc, SoapOutgoing& data);
    int seekSecondRelative(const SoapIncoming& sc, SoapOutgoing& data);
    int seekId(const SoapIncoming& sc, SoapOutgoing& data);
    int seekIndex(const SoapIncoming& sc, SoapOutgoing& data);
    int transportState(const SoapIncoming& sc, SoapOutgoing& data);
    int id(const SoapIncoming& sc, SoapOutgoing& data);
    int ohread(const SoapIncoming& sc, SoapOutgoing& data);
    int readList(const SoapIncoming& sc, SoapOutgoing& data);
    int insert(const SoapIncoming& sc, SoapOutgoing& data);
    int deleteId(const SoapIncoming& sc, SoapOutgoing& data);
    int deleteAll(const SoapIncoming& sc, SoapOutgoing& data);
    int tracksMax(const SoapIncoming& sc, SoapOutgoing& data);
    int idArray(const SoapIncoming& sc, SoapOutgoing& data);
    int idArrayChanged(const SoapIncoming& sc, SoapOutgoing& data);
    int protocolInfo(const SoapIncoming& sc, SoapOutgoing& data);

    bool cacheSet(const std::string& uri, const std::string& meta);

    // Private internal non-soap versions of some of the interface +
    // utility methods
    bool makeIdArray(std::string&);
    bool insertUri(int afterid, const std::string& uri, 
                   const std::string& metadata, int *newid, bool nocheck);
    bool ireadList(const std::vector<int>&, std::vector<UpSong>&);
    bool iidArray(std::string& idarray, int *token);
    // Search the current mpd queue for a given uri and return the
    // corresponding id. This is used for mapping ids from our
    // previous active phase to the current ones (which changed when
    // the tracks were re-inserted on activation). Of course, this
    // does not work in the case of multiple identical Uris in the
    // playlist.
    int idFromOldId(int oldid);

    bool m_active;
    // Mpd state that we save/restore when becoming inactive/active
    MpdState m_mpdsavedstate;
    // Frozen upnpstate (idarray etc.) which we use when inactive
    // (because we can't read from the mpd playlist which is used by
    // someone else. Could largely be rebuilt from m_mpdsavedstate,
    // but easier this way as we can just/use it in makestate().
    std::unordered_map<std::string, std::string> m_upnpstate;
    
    // Storage for song metadata, indexed by URL.  This used to be
    // indexed by song id, but this does not survive MPD restarts.
    // The data is the DIDL XML string.
    std::unordered_map<std::string, std::string> m_metacache;
    bool m_cachedirty;

    // Avoid re-reading the whole MPD queue every time by using the
    // queue version.
    int m_mpdqvers;
    std::string m_idArrayCached;
    // Last mpdid seen (mpd playing)
    int m_lastplayid{-1}; 
    // Id of first song in queue. For eventing Id before beginning play (0 means queue empty).
    int m_firstqid{0}; 
};

#endif /* _OHPLAYLIST_H_X_INCLUDED_ */
