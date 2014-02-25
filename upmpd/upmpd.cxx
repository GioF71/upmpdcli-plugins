/* Copyright (C) 2014 J.F.Dockes
 *	 This program is free software; you can redistribute it and/or modify
 *	 it under the terms of the GNU General Public License as published by
 *	 the Free Software Foundation; either version 2 of the License, or
 *	 (at your option) any later version.
 *
 *	 This program is distributed in the hope that it will be useful,
 *	 but WITHOUT ANY WARRANTY; without even the implied warranty of
 *	 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *	 GNU General Public License for more details.
 *
 *	 You should have received a copy of the GNU General Public License
 *	 along with this program; if not, write to the
 *	 Free Software Foundation, Inc.,
 *	 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <pwd.h>

#include <string>
#include <iostream>
#include <sstream>
#include <vector>
#include <functional>
#include <set>
using namespace std;
using namespace std::placeholders;

#include "libupnpp/upnpplib.hxx"
#include "libupnpp/soaphelp.hxx"
#include "libupnpp/device.hxx"
#include "libupnpp/log.hxx"

#include "mpdcli.hxx"
#include "upmpdutils.hxx"

static const string dfltFriendlyName("UpMpd");

// The UPnP MPD frontend device with its 3 services
class UpMpd : public UpnpDevice {
public:
	enum Options {
		upmpdNone,
		upmpdOwnQueue, // The MPD belongs to us, we shall clear it as we like
	};
	UpMpd(const string& deviceid, const unordered_map<string, string>& xmlfiles,
		  MPDCli *mpdcli, Options opts = upmpdNone);

	// RenderingControl
	int setMute(const SoapArgs& sc, SoapData& data);
	int getMute(const SoapArgs& sc, SoapData& data);
	int setVolume(const SoapArgs& sc, SoapData& data, bool isDb);
	int getVolume(const SoapArgs& sc, SoapData& data, bool isDb);
	int listPresets(const SoapArgs& sc, SoapData& data);
	int selectPreset(const SoapArgs& sc, SoapData& data);
//	int getVolumeDBRange(const SoapArgs& sc, SoapData& data);
    virtual bool getEventDataRendering(bool all, 
									   std::vector<std::string>& names, 
									   std::vector<std::string>& values);

	// AVTransport
	int setAVTransportURI(const SoapArgs& sc, SoapData& data, bool setnext);
	int getPositionInfo(const SoapArgs& sc, SoapData& data);
	int getTransportInfo(const SoapArgs& sc, SoapData& data);
	int getMediaInfo(const SoapArgs& sc, SoapData& data);
	int getDeviceCapabilities(const SoapArgs& sc, SoapData& data);
	int setPlayMode(const SoapArgs& sc, SoapData& data);
	int getTransportSettings(const SoapArgs& sc, SoapData& data);
	int getCurrentTransportActions(const SoapArgs& sc, SoapData& data);
	int playcontrol(const SoapArgs& sc, SoapData& data, int what);
	int seek(const SoapArgs& sc, SoapData& data);
	int seqcontrol(const SoapArgs& sc, SoapData& data, int what);
    virtual bool getEventDataTransport(bool all, 
									   std::vector<std::string>& names, 
									   std::vector<std::string>& values);

	// Connection Manager
	int getCurrentConnectionIDs(const SoapArgs& sc, SoapData& data);
	int getCurrentConnectionInfo(const SoapArgs& sc, SoapData& data);
	int getProtocolInfo(const SoapArgs& sc, SoapData& data);
	virtual bool getEventDataCM(bool all, std::vector<std::string>& names, 
								std::vector<std::string>& values);

	// Re-implemented from the base class and shared by all services
    virtual bool getEventData(bool all, const string& serviceid, 
							  std::vector<std::string>& names, 
							  std::vector<std::string>& values);

private:
	MPDCli *m_mpdcli;

	string m_curMetadata;
	string m_nextUri;
	string m_nextMetadata;

	// State variable storage
	unordered_map<string, string> m_rdstate;
	unordered_map<string, string> m_tpstate;

	// Translate MPD state to Renderer state variables.
	bool rdstateMToU(unordered_map<string, string>& state);
	// Translate MPD state to AVTransport state variables.
	bool tpstateMToU(unordered_map<string, string>& state);

	// My track identifiers (for cleaning up)
	set<int> m_songids;

	// Desired volume target. We may delay executing small volume
	// changes to avoid saturating with small requests.
	int m_desiredvolume;

	int m_options;
};

static const string serviceIdRender("urn:upnp-org:serviceId:RenderingControl");
static const string serviceIdTransport("urn:upnp-org:serviceId:AVTransport");
static const string serviceIdCM("urn:upnp-org:serviceId:ConnectionManager");

UpMpd::UpMpd(const string& deviceid, 
			 const unordered_map<string, string>& xmlfiles,
			 MPDCli *mpdcli, Options opts)
	: UpnpDevice(deviceid, xmlfiles), m_mpdcli(mpdcli), m_desiredvolume(-1),
	  m_options(opts)
{
	addServiceType(serviceIdRender,
				   "urn:schemas-upnp-org:service:RenderingControl:1");
	{	auto bound = bind(&UpMpd::setMute, this, _1, _2);
		addActionMapping("SetMute", bound);
	}
	{	auto bound = bind(&UpMpd::getMute, this, _1, _2);
		addActionMapping("GetMute", bound);
	}
	{	auto bound = bind(&UpMpd::setVolume, this, _1, _2, false);
		addActionMapping("SetVolume", bound);
	}
//	{	auto bound = bind(&UpMpd::setVolume, this, _1, _2, true);
//		addActionMapping("SetVolumeDB", bound);
//	}
	{	auto bound = bind(&UpMpd::getVolume, this, _1, _2, false);
		addActionMapping("GetVolume", bound);
	}
//	{	auto bound = bind(&UpMpd::getVolume, this, _1, _2, true);
//		addActionMapping("GetVolumeDB", bound);
//	}
	{	auto bound = bind(&UpMpd::listPresets, this, _1, _2);
		addActionMapping("ListPresets", bound);
	}
	{	auto bound = bind(&UpMpd::selectPreset, this, _1, _2);
		addActionMapping("SelectPreset", bound);
	}
//	{	auto bound = bind(&UpMpd::getVolumeDBRange, this, _1, _2);
//		addActionMapping("GetVolumeDBRange", bound);
//	}

	addServiceType(serviceIdTransport,
				   "urn:schemas-upnp-org:service:AVTransport:1");

	{	auto bound = bind(&UpMpd::setAVTransportURI, this, _1, _2, false);
		addActionMapping("SetAVTransportURI", bound);
	}
	{	auto bound = bind(&UpMpd::setAVTransportURI, this, _1, _2, true);
		addActionMapping("SetNextAVTransportURI", bound);
	}
	{	auto bound = bind(&UpMpd::getPositionInfo, this, _1, _2);
		addActionMapping("GetPositionInfo", bound);
	}
	{	auto bound = bind(&UpMpd::getTransportInfo, this, _1, _2);
		addActionMapping("GetTransportInfo", bound);
	}
	{	auto bound = bind(&UpMpd::getMediaInfo, this, _1, _2);
		addActionMapping("GetMediaInfo", bound);
	}
	{	auto bound = bind(&UpMpd::getDeviceCapabilities, this, _1, _2);
		addActionMapping("GetDeviceCapabilities", bound);
	}
	{	auto bound = bind(&UpMpd::setPlayMode, this, _1, _2);
		addActionMapping("SetPlayMode", bound);
	}
	{	auto bound = bind(&UpMpd::getTransportSettings, this, _1, _2);
		addActionMapping("GetTransportSettings", bound);
	}
	{	auto bound = bind(&UpMpd::getCurrentTransportActions, this, _1, _2);
		addActionMapping("GetCurrentTransportActions", bound);
	}
	{	auto bound = bind(&UpMpd::playcontrol, this, _1, _2, 0);
		addActionMapping("Stop", bound);
	}
	{	auto bound = bind(&UpMpd::playcontrol, this, _1, _2, 1);
		addActionMapping("Play", bound);
	}
	{	auto bound = bind(&UpMpd::playcontrol, this, _1, _2, 2);
		addActionMapping("Pause", bound);
	}
	{	auto bound = bind(&UpMpd::seek, this, _1, _2);
		addActionMapping("Seek", bound);
	}
	{	auto bound = bind(&UpMpd::seqcontrol, this, _1, _2, 0);
		addActionMapping("Next", bound);
	}
	{	auto bound = bind(&UpMpd::seqcontrol, this, _1, _2, 1);
		addActionMapping("Previous", bound);
	}

	addServiceType(serviceIdCM,
				   "urn:schemas-upnp-org:service:ConnectionManager:1");
	{	auto bound = bind(&UpMpd::getCurrentConnectionIDs, this, _1, _2);
		addActionMapping("GetCurrentConnectionIDs", bound);
	}
	{	auto bound = bind(&UpMpd::getCurrentConnectionInfo, this, _1, _2);
		addActionMapping("GetCurrentConnectionInfo", bound);
	}
	{	auto bound = bind(&UpMpd::getProtocolInfo, this, _1, _2);
		addActionMapping("GetProtocolInfo", bound);
	}
}

// This is called by the polling loop at regular intervals, or when
// triggered, to retrieve changed state variables for each of the
// services (the list of services was defined in the base class by the
// "addServiceTypes()" calls during construction).
//
// We might add a method for triggering an event from the action
// methods after changing state, which would really act only if the
// interval with the previous event is long enough. But things seem to
// work ok with the systematic delay.
bool UpMpd::getEventData(bool all, const string& serviceid, 
						 std::vector<std::string>& names, 
						 std::vector<std::string>& values)
{
	if (!serviceid.compare(serviceIdRender)) {
		return getEventDataRendering(all, names, values);
	} else if (!serviceid.compare(serviceIdTransport)) {
		return getEventDataTransport(all, names, values);
	} else if (!serviceid.compare(serviceIdCM)) {
		return getEventDataCM(all, names, values);
	} else {
		LOGERR("UpMpd::getEventData: servid? [" << serviceid << "]" << endl);
		return UPNP_E_INVALID_PARAM;
	}
}

////////////////////////////////////////////////////
/// RenderingControl methods

// State variables for the RenderingControl. All evented through LastChange
//  PresetNameList
//  Mute
//  Volume
//  VolumeDB
// LastChange contains all the variables that were changed since the last
// event. For us that's at most Mute, Volume, VolumeDB
// <Event xmlns=”urn:schemas-upnp-org:metadata-1-0/AVT_RCS">
//   <InstanceID val=”0”>
//     <Mute channel=”Master” val=”0”/>
//     <Volume channel=”Master” val=”24”/>
//     <VolumeDB channel=”Master” val=”24”/>
//   </InstanceID>
// </Event>

bool UpMpd::rdstateMToU(unordered_map<string, string>& status)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();

	int volume = m_desiredvolume >= 0 ? m_desiredvolume : mpds.volume;
	if (volume < 0)
		volume = 0;
	char cvalue[30];
	sprintf(cvalue, "%d", volume);
	status["Volume"] = cvalue;
//	sprintf(cvalue, "%d", percentodbvalue(volume));
//	status["VolumeDB"] =  cvalue;
	status["Mute"] =  volume == 0 ? "1" : "0";
	return true;
}

bool UpMpd::getEventDataRendering(bool all, std::vector<std::string>& names, 
								  std::vector<std::string>& values)
{
	//LOGDEB("UpMpd::getEventDataRendering. desiredvolume " << 
	//		   m_desiredvolume << (all?" all " : "") << endl);
	if (m_desiredvolume >= 0) {
		m_mpdcli->setVolume(m_desiredvolume);
		m_desiredvolume = -1;
	}

	unordered_map<string, string> newstate;
	rdstateMToU(newstate);
	if (all)
		m_rdstate.clear();

	string 
		chgdata("<Event xmlns=\"urn:schemas-upnp-org:metadata-1-0/AVT_RCS\">\n"
				"<InstanceID val=\"0\">\n");

	bool changefound = false;
	for (unordered_map<string, string>::const_iterator it = newstate.begin();
		 it != newstate.end(); it++) {

		const string& oldvalue = mapget(m_rdstate, it->first);
		if (!it->second.compare(oldvalue))
			continue;

		changefound = true;

		chgdata += "<";
		chgdata += it->first;
		chgdata += " val=\"";
		chgdata += xmlquote(it->second);
		chgdata += "\"/>\n";
	}
	chgdata += "</InstanceID>\n</Event>\n";

	if (!changefound) {
		return true;
	}

	names.push_back("LastChange");
	values.push_back(chgdata);

	m_rdstate = newstate;

	return true;
}

// Actions:
// Note: we need to return all out arguments defined by the SOAP call even if
// they don't make sense (because there is no song playing). Ref upnp arch p.51:
//
//   argumentName: Required if and only if action has out
//   arguments. Value returned from action. Repeat once for each out
//   argument. If action has an argument marked as retval, this
//   argument must be the first element. (Element name not qualified
//   by a namespace; element nesting context is sufficient.) Case
//   sensitive. Single data type as defined by UPnP service
//   description. Every “out” argument in the definition of the action
//   in the service description must be included, in the same order as
//   specified in the service description (SCPD) available from the
//   device.

#if 0
int UpMpd::getVolumeDBRange(const SoapArgs& sc, SoapData& data)
{
	map<string, string>::const_iterator it;

	it = sc.args.find("Channel");
	if (it == sc.args.end() || it->second.compare("Master")) {
		return UPNP_E_INVALID_PARAM;
	}
	data.addarg("MinValue", "-10240");
	data.addarg("MaxValue", "0");

	return UPNP_E_SUCCESS;
}
#endif
int UpMpd::setMute(const SoapArgs& sc, SoapData& data)
{
	map<string, string>::const_iterator it;

	it = sc.args.find("Channel");
	if (it == sc.args.end() || it->second.compare("Master")) {
		return UPNP_E_INVALID_PARAM;
	}
		
	it = sc.args.find("DesiredMute");
	if (it == sc.args.end() || it->second.empty()) {
		return UPNP_E_INVALID_PARAM;
	}
	if (it->second[0] == 'F' || it->second[0] == '0') {
		// Restore pre-mute
		m_mpdcli->setVolume(1, true);
	} else if (it->second[0] == 'T' || it->second[0] == '1') {
		if (m_desiredvolume >= 0) {
			m_mpdcli->setVolume(m_desiredvolume);
			m_desiredvolume = -1;
		}
		m_mpdcli->setVolume(0, true);
	} else {
		return UPNP_E_INVALID_PARAM;
	}
	loopWakeup();
	return UPNP_E_SUCCESS;
}

int UpMpd::getMute(const SoapArgs& sc, SoapData& data)
{
	map<string, string>::const_iterator it;

	it = sc.args.find("Channel");
	if (it == sc.args.end() || it->second.compare("Master")) {
		return UPNP_E_INVALID_PARAM;
	}
	int volume = m_mpdcli->getVolume();
	data.addarg("CurrentMute", volume == 0 ? "1" : "0");
	return UPNP_E_SUCCESS;
}

int UpMpd::setVolume(const SoapArgs& sc, SoapData& data, bool isDb)
{
	map<string, string>::const_iterator it;

	it = sc.args.find("Channel");
	if (it == sc.args.end() || it->second.compare("Master")) {
		return UPNP_E_INVALID_PARAM;
	}
		
	it = sc.args.find("DesiredVolume");
	if (it == sc.args.end() || it->second.empty()) {
		return UPNP_E_INVALID_PARAM;
	}
	int volume = atoi(it->second.c_str());
	if (isDb) {
		volume = dbvaluetopercent(volume);
	} 
	if (volume < 0 || volume > 100) {
		return UPNP_E_INVALID_PARAM;
	}
	
	int previous_volume = m_mpdcli->getVolume();
	int delta = previous_volume - volume;
	if (delta < 0)
		delta = -delta;
	LOGDEB("UpMpd::setVolume: volume " << volume << " delta " << delta << endl);
	if (delta >= 5) {
		m_mpdcli->setVolume(volume);
		m_desiredvolume = -1;
	} else {
		m_desiredvolume = volume;
	}

	loopWakeup();
	return UPNP_E_SUCCESS;
}

int UpMpd::getVolume(const SoapArgs& sc, SoapData& data, bool isDb)
{
	// LOGDEB("UpMpd::getVolume" << endl);
	map<string, string>::const_iterator it;

	it = sc.args.find("Channel");
	if (it == sc.args.end() || it->second.compare("Master")) {
		return UPNP_E_INVALID_PARAM;
	}
		
	int volume = m_mpdcli->getVolume();
	if (isDb) {
		volume = percentodbvalue(volume);
	}
	char svolume[30];
	sprintf(svolume, "%d", volume);
	data.addarg("CurrentVolume", svolume);
	return UPNP_E_SUCCESS;
}

int UpMpd::listPresets(const SoapArgs& sc, SoapData& data)
{
	// The 2nd arg is a comma-separated list of preset names
	data.addarg("CurrentPresetNameList", "FactoryDefaults");
	return UPNP_E_SUCCESS;
}

int UpMpd::selectPreset(const SoapArgs& sc, SoapData& data)
{
	map<string, string>::const_iterator it;
		
	it = sc.args.find("PresetName");
	if (it == sc.args.end() || it->second.empty()) {
		return UPNP_E_INVALID_PARAM;
	}
	if (it->second.compare("FactoryDefaults")) {
		return UPNP_E_INVALID_PARAM;
	}

	// Well there is only the volume actually...
	int volume = 50;
	m_mpdcli->setVolume(volume);

	return UPNP_E_SUCCESS;
}

///////////////// AVTransport methods

// Translate MPD mode flags to UPnP Play mode
static string mpdsToPlaymode(const MpdStatus& mpds)
{
	string playmode = "NORMAL";
    if (!mpds.rept && mpds.random && !mpds.single)
		playmode = "SHUFFLE";
	else if (mpds.rept && !mpds.random && mpds.single)
		playmode = "REPEAT_ONE";
	else if (mpds.rept && !mpds.random && !mpds.single)
		playmode = "REPEAT_ALL";
	else if (mpds.rept && mpds.random && !mpds.single)
		playmode = "RANDOM";
	else if (!mpds.rept && !mpds.random && mpds.single)
		playmode = "DIRECT_1";
	return playmode;
}

// AVTransport eventing
// 
// Some state variables do not generate events and must be polled by
// the control point: RelativeTimePosition AbsoluteTimePosition
// RelativeCounterPosition AbsoluteCounterPosition.
// This leaves us with:
//    TransportState
//    TransportStatus
//    PlaybackStorageMedium
//    PossiblePlaybackStorageMedia
//    RecordStorageMedium
//    PossibleRecordStorageMedia
//    CurrentPlayMode
//    TransportPlaySpeed
//    RecordMediumWriteStatus
//    CurrentRecordQualityMode
//    PossibleRecordQualityModes
//    NumberOfTracks
//    CurrentTrack
//    CurrentTrackDuration
//    CurrentMediaDuration
//    CurrentTrackMetaData
//    CurrentTrackURI
//    AVTransportURI
//    AVTransportURIMetaData
//    NextAVTransportURI
//    NextAVTransportURIMetaData
//    RelativeTimePosition
//    AbsoluteTimePosition
//    RelativeCounterPosition
//    AbsoluteCounterPosition
//    CurrentTransportActions
//
// To be all bundled inside:    LastChange

// Translate MPD state to UPnP AVTRansport state variables
bool UpMpd::tpstateMToU(unordered_map<string, string>& status)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();
	//DEBOUT << "UpMpd::tpstateMToU: curpos: " << mpds.songpos <<
	//   " qlen " << mpds.qlen << endl;
	bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
		(mpds.state == MpdStatus::MPDS_PAUSE);

	string tstate("STOPPED");
	string tactions("Next,Previous");
	switch(mpds.state) {
	case MpdStatus::MPDS_PLAY: 
		tstate = "PLAYING"; 
		tactions += ",Pause,Stop,Seek";
		break;
	case MpdStatus::MPDS_PAUSE: 
		tstate = "PAUSED_PLAYBACK"; 
		tactions += ",Play,Stop,Seek";
		break;
	default:
		tactions += ",Play";
	}
	status["TransportState"] = tstate;
	status["CurrentTransportActions"] = tactions;
	status["TransportStatus"] = m_mpdcli->ok() ? "OK" : "ERROR_OCCURRED";
	status["TransportPlaySpeed"] = "1";

	const string& uri = mapget(mpds.currentsong, "uri");
	status["CurrentTrack"] = "1";
	status["CurrentTrackURI"] = uri;

	// If we own the queue, just use the metadata from the content directory.
	// else, try to make up something from mpd status.
	if ((m_options & upmpdOwnQueue)) {
		status["CurrentTrackMetaData"] = is_song ? m_curMetadata : "";
	} else {
		status["CurrentTrackMetaData"] = is_song ? didlmake(mpds) : "";
	}

	string playmedium("NONE");
	if (is_song)
		playmedium = uri.find("http://") == 0 ?	"HDD" : "NETWORK";
	status["NumberOfTracks"] = "1";
	status["CurrentMediaDuration"] = is_song?
		upnpduration(mpds.songlenms):"00:00:00";
	status["CurrentTrackDuration"] = is_song?
		upnpduration(mpds.songlenms):"00:00:00";
	status["AVTransportURI"] = uri;
	if ((m_options & upmpdOwnQueue)) {
		status["AVTransportURIMetaData"] = is_song ? m_curMetadata : "";
	} else {
		status["AVTransportURIMetaData"] = is_song ? didlmake(mpds) : "";
	}
	status["RelativeTimePosition"] = is_song?
		upnpduration(mpds.songelapsedms):"0:00:00";
	status["AbsoluteTimePosition"] = is_song?
		upnpduration(mpds.songelapsedms) : "0:00:00";

	status["NextAVTransportURI"] = mapget(mpds.nextsong, "uri");
	if ((m_options & upmpdOwnQueue)) {
		status["NextAVTransportURIMetaData"] = is_song ? m_nextMetadata : "";
	} else {
		status["NextAVTransportURIMetaData"] = is_song?didlmake(mpds, true) :"";
	}

	status["PlaybackStorageMedium"] = playmedium;
	status["PossiblePlaybackStorageMedium"] = "HDD,NETWORK";
	status["RecordStorageMedium"] = "NOT_IMPLEMENTED";
	status["RelativeCounterPosition"] = "0";
	status["AbsoluteCounterPosition"] = "0";
	status["CurrentPlayMode"] = mpdsToPlaymode(mpds);

	status["PossibleRecordStorageMedium"] = "NOT_IMPLEMENTED";
	status["RecordMediumWriteStatus"] = "NOT_IMPLEMENTED";
	status["CurrentRecordQualityMode"] = "NOT_IMPLEMENTED";
	status["PossibleRecordQualityModes"] = "NOT_IMPLEMENTED";
	return true;
}

bool UpMpd::getEventDataTransport(bool all, std::vector<std::string>& names, 
								  std::vector<std::string>& values)
{
	unordered_map<string, string> newtpstate;
	tpstateMToU(newtpstate);
	if (all)
		m_tpstate.clear();

	bool changefound = false;

	string 
		chgdata("<Event xmlns=\"urn:schemas-upnp-org:metadata-1-0/AVT_RCS\">\n"
				"<InstanceID val=\"0\">\n");
	for (unordered_map<string, string>::const_iterator it = newtpstate.begin();
		 it != newtpstate.end(); it++) {

		const string& oldvalue = mapget(m_tpstate, it->first);
		if (!it->second.compare(oldvalue))
			continue;

		if (it->first.compare("RelativeTimePosition") && 
			it->first.compare("AbsoluteTimePosition")) {
			//DEBOUT << "Transport state update for " << it->first << 
			// " oldvalue [" << oldvalue << "] -> [" << it->second << endl;
			changefound = true;
		}

		chgdata += "<";
		chgdata += it->first;
		chgdata += " val=\"";
		chgdata += xmlquote(it->second);
		chgdata += "\"/>\n";
	}
	chgdata += "</InstanceID>\n</Event>\n";

	if (!changefound) {
		// DEBOUT << "UpMpd::getEventDataTransport: no updates" << endl;
		return true;
	}

	names.push_back("LastChange");
	values.push_back(chgdata);

	m_tpstate = newtpstate;
	// DEBOUT << "UpMpd::getEventDataTransport: " << chgdata << endl;
	return true;
}

// http://192.168.4.4:8200/MediaItems/246.mp3
int UpMpd::setAVTransportURI(const SoapArgs& sc, SoapData& data, bool setnext)
{
	map<string, string>::const_iterator it;
		
	it = setnext? sc.args.find("NextURI") : sc.args.find("CurrentURI");
	if (it == sc.args.end() || it->second.empty()) {
		return UPNP_E_INVALID_PARAM;
	}
	string uri = it->second;
	string metadata;
	it = setnext? sc.args.find("NextURIMetaData") : 
		sc.args.find("CurrentURIMetaData");
	if (it != sc.args.end())
		metadata = it->second;
	//cerr << "SetTransport: setnext " << setnext << " metadata[" << metadata <<
	// "]" << endl;

	if ((m_options & upmpdOwnQueue) && !setnext) {
		// If we own the queue, just clear it before setting the
		// track.  Else it's difficult to impossible to prevent it
		// from growing if upmpdcli restarts. If the option is not set, the
		// user prefers to live with the issue.
		m_mpdcli->clearQueue();
	}

	const MpdStatus &mpds = m_mpdcli->getStatus();
	bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
		(mpds.state == MpdStatus::MPDS_PAUSE);
	int curpos = mpds.songpos;
	LOGDEB("UpMpd::set" << (setnext?"Next":"") << 
		   "AVTransportURI: curpos: " <<
		   curpos << " is_song " << is_song << " qlen " << mpds.qlen << endl);

	// curpos == -1 means that the playlist was cleared or we just started. A
	// play will use position 0, so it's actually equivalent to curpos == 0
	if (curpos == -1) {
		curpos = 0;
	}

	if (mpds.qlen == 0 && setnext) {
		LOGDEB("setNextAVTRansportURI invoked but empty queue!" << endl);
		return UPNP_E_INVALID_PARAM;
	}
	int songid;
	if ((songid = m_mpdcli->insert(uri, setnext?curpos+1:curpos)) < 0) {
		return UPNP_E_INTERNAL_ERROR;
	}

	metadata = regsub1("<\\?xml.*\\?>", metadata, "");
	if (setnext) {
		m_nextUri = uri;
		m_nextMetadata = metadata;
	} else {
		m_curMetadata = metadata;
		m_nextUri = "";
		m_nextMetadata = "";
	}

	if (!setnext) {
		MpdStatus::State st = mpds.state;
		// Have to tell mpd which track to play, else it will keep on
		// the previous despite of the insertion. The UPnP docs say
		// that setAVTransportURI should not change the transport
		// state (pause/stop stay pause/stop) but it seems that some clients
		// expect that the track will start playing.
		// Needs to be revisited after seeing more clients. For now try to 
		// preserve state as per standard.
		// Audionet: issues a Play
		// BubbleUpnp: issues a Play
		// MediaHouse: no setnext, Play
		m_mpdcli->play(curpos);
#if 1 || defined(upmpd_do_restore_play_state_after_add)
		switch (st) {
		case MpdStatus::MPDS_PAUSE: m_mpdcli->togglePause(); break;
		case MpdStatus::MPDS_STOP: m_mpdcli->stop(); break;
		default: break;
		}
#endif
		// Clean up old song ids
		if (!(m_options & upmpdOwnQueue)) {
			for (set<int>::iterator it = m_songids.begin();
				 it != m_songids.end(); it++) {
				// Can't just delete here. If the id does not exist, MPD 
				// gets into an apparently permanent error state, where even 
				// get_status does not work
				if (m_mpdcli->statId(*it)) {
					m_mpdcli->deleteId(*it);
				}
			}
			m_songids.clear();
		}
	}

	if (!(m_options & upmpdOwnQueue)) {
		m_songids.insert(songid);
	}

	loopWakeup();
	return UPNP_E_SUCCESS;
}

int UpMpd::getPositionInfo(const SoapArgs& sc, SoapData& data)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();
	//LOGDEB("UpMpd::getPositionInfo. State: " << mpds.state << endl);

	bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
		(mpds.state == MpdStatus::MPDS_PAUSE);

	if (is_song) {
		data.addarg("Track", "1");
	} else {
		data.addarg("Track", "0");
	}

	if (is_song) {
		data.addarg("TrackDuration", upnpduration(mpds.songlenms));
	} else {
		data.addarg("TrackDuration", "00:00:00");
	}

	if (is_song) {
		if ((m_options & upmpdOwnQueue)) {
			data.addarg("TrackMetaData", m_curMetadata);
		} else {
			data.addarg("TrackMetaData", didlmake(mpds));
		}
	} else {
		data.addarg("TrackMetaData", "");
	}

	const string& uri = mapget(mpds.currentsong, "uri");
	if (is_song && !uri.empty()) {
		data.addarg("TrackURI", xmlquote(uri));
	} else {
		data.addarg("TrackURI", "");
	}
	if (is_song) {
		data.addarg("RelTime", upnpduration(mpds.songelapsedms));
	} else {
		data.addarg("RelTime", "0:00:00");
	}

	if (is_song) {
		data.addarg("AbsTime", upnpduration(mpds.songelapsedms));
	} else {
		data.addarg("AbsTime", "0:00:00");
	}

	data.addarg("RelCount", "0");
	data.addarg("AbsCount", "0");
	return UPNP_E_SUCCESS;
}

int UpMpd::getTransportInfo(const SoapArgs& sc, SoapData& data)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();
	//LOGDEB("UpMpd::getTransportInfo. State: " << mpds.state << endl);

	string tstate("STOPPED");
	switch(mpds.state) {
	case MpdStatus::MPDS_PLAY: tstate = "PLAYING"; break;
	case MpdStatus::MPDS_PAUSE: tstate = "PAUSED_PLAYBACK"; break;
	default: break;
	}
	data.addarg("CurrentTransportState", tstate);
	data.addarg("CurrentTransportStatus", m_mpdcli->ok() ? "OK" : 
				"ERROR_OCCURRED");
	data.addarg("CurrentSpeed", "1");
	return UPNP_E_SUCCESS;
}

int UpMpd::getDeviceCapabilities(const SoapArgs& sc, SoapData& data)
{
	data.addarg("PlayMedia", "NETWORK,HDD");
	data.addarg("RecMedia", "NOT_IMPLEMENTED");
	data.addarg("RecQualityModes", "NOT_IMPLEMENTED");
	return UPNP_E_SUCCESS;
}

int UpMpd::getMediaInfo(const SoapArgs& sc, SoapData& data)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();
	LOGDEB("UpMpd::getMediaInfo. State: " << mpds.state << endl);

	bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
		(mpds.state == MpdStatus::MPDS_PAUSE);

	data.addarg("NrTracks", "1");
	if (is_song) {
		data.addarg("MediaDuration", upnpduration(mpds.songlenms));
	} else {
		data.addarg("MediaDuration", "00:00:00");
	}

	const string& thisuri = mapget(mpds.currentsong, "uri");
	if (is_song && !thisuri.empty()) {
		data.addarg("CurrentURI", xmlquote(thisuri));
	} else {
		data.addarg("CurrentURI", "");
	}
	if (is_song) {
		if ((m_options & upmpdOwnQueue)) {
			data.addarg("CurrentURIMetaData", m_curMetadata);
		} else {
			data.addarg("CurrentURIMetaData", didlmake(mpds));
		}
	} else {
		data.addarg("CurrentURIMetaData", "");
	}
	if ((m_options & upmpdOwnQueue)) {
		data.addarg("NextURI", m_nextUri);
		data.addarg("NextURIMetaData", is_song ? m_nextMetadata : "");
	} else {
		data.addarg("NextURI", mapget(mpds.nextsong, "uri"));
		data.addarg("NextURIMetaData", is_song ? didlmake(mpds, true) : "");
	}
	string playmedium("NONE");
	if (is_song)
		playmedium = thisuri.find("http://") == 0 ?	"HDD" : "NETWORK";
	data.addarg("PlayMedium", playmedium);

	data.addarg("RecordMedium", "NOT_IMPLEMENTED");
	data.addarg("WriteStatus", "NOT_IMPLEMENTED");
	return UPNP_E_SUCCESS;
}

int UpMpd::playcontrol(const SoapArgs& sc, SoapData& data, int what)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();
	LOGDEB("UpMpd::playcontrol State: " << mpds.state <<" what "<<what<< endl);

	if ((what & ~0x3)) {
		LOGERR("UpMPd::playcontrol: bad control " << what << endl);
		return UPNP_E_INVALID_PARAM;
	}

	bool ok = true;
	switch (mpds.state) {
	case MpdStatus::MPDS_PLAY: 
		switch (what) {
		case 0:	ok = m_mpdcli->stop(); break;
		case 1: ok = m_mpdcli->play();break;
		case 2: ok = m_mpdcli->togglePause();break;
		}
		break;
	case MpdStatus::MPDS_PAUSE:
		switch (what) {
		case 0:	ok = m_mpdcli->stop(); break;
		case 1: ok = m_mpdcli->togglePause();break;
		case 2: break;
		}
		break;
	case MpdStatus::MPDS_STOP:
	default:
		switch (what) {
		case 0:	break;
		case 1: ok = m_mpdcli->play();break;
		case 2: break;
		}
		break;
	}
	
	loopWakeup();
	return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int UpMpd::seqcontrol(const SoapArgs& sc, SoapData& data, int what)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();
	LOGDEB("UpMpd::seqcontrol State: " << mpds.state << " what "<<what<< endl);

	if ((what & ~0x1)) {
		LOGERR("UpMPd::seqcontrol: bad control " << what << endl);
		return UPNP_E_INVALID_PARAM;
	}

	bool ok = true;
	switch (what) {
	case 0: ok = m_mpdcli->next();break;
	case 1: ok = m_mpdcli->previous();break;
	}

	loopWakeup();
	return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}
	
int UpMpd::setPlayMode(const SoapArgs& sc, SoapData& data)
{
	map<string, string>::const_iterator it;
		
	it = sc.args.find("NewPlayMode");
	if (it == sc.args.end() || it->second.empty()) {
		return UPNP_E_INVALID_PARAM;
	}
	string playmode(it->second);
	bool ok;
	if (!playmode.compare("NORMAL")) {
		ok = m_mpdcli->repeat(false) && m_mpdcli->random(false) &&
			m_mpdcli->single(false);
	} else if (!playmode.compare("SHUFFLE")) {
		ok = m_mpdcli->repeat(false) && m_mpdcli->random(true) &&
			m_mpdcli->single(false);
	} else if (!playmode.compare("REPEAT_ONE")) {
		ok = m_mpdcli->repeat(true) && m_mpdcli->random(false) &&
			m_mpdcli->single(true);
	} else if (!playmode.compare("REPEAT_ALL")) {
		ok = m_mpdcli->repeat(true) && m_mpdcli->random(false) &&
			m_mpdcli->single(false);
	} else if (!playmode.compare("RANDOM")) {
		ok = m_mpdcli->repeat(true) && m_mpdcli->random(true) &&
			m_mpdcli->single(false);
	} else if (!playmode.compare("DIRECT_1")) {
		ok = m_mpdcli->repeat(false) && m_mpdcli->random(false) &&
			m_mpdcli->single(true);
	} else {
		return UPNP_E_INVALID_PARAM;
	}
	loopWakeup();
	return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int UpMpd::getTransportSettings(const SoapArgs& sc, SoapData& data)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();
	string playmode = mpdsToPlaymode(mpds);
	data.addarg("PlayMode", playmode);
	data.addarg("RecQualityMode", "NOT_IMPLEMENTED");
	return UPNP_E_SUCCESS;
}

int UpMpd::getCurrentTransportActions(const SoapArgs& sc, SoapData& data)
{
	const MpdStatus &mpds = m_mpdcli->getStatus();
	string tactions("Next,Previous");
	switch(mpds.state) {
	case MpdStatus::MPDS_PLAY: 
		tactions += ",Pause,Stop,Seek";
		break;
	case MpdStatus::MPDS_PAUSE: 
		tactions += ",Play,Stop,Seek";
		break;
	default:
		tactions += ",Play";
	}
	data.addarg("CurrentTransportActions", tactions);
	return UPNP_E_SUCCESS;
}

int UpMpd::seek(const SoapArgs& sc, SoapData& data)
{
	map<string, string>::const_iterator it;
		
	it = sc.args.find("Unit");
	if (it == sc.args.end() || it->second.empty()) {
		return UPNP_E_INVALID_PARAM;
	}
	string unit(it->second);

	it = sc.args.find("Target");
	if (it == sc.args.end() || it->second.empty()) {
		return UPNP_E_INVALID_PARAM;
	}
	string target(it->second);

	// LOGDEB("UpMpd::seek: unit " << unit << " target " << target);

	const MpdStatus &mpds = m_mpdcli->getStatus();
	int abs_seconds;
	if (!unit.compare("ABS_TIME")) {
		abs_seconds = upnpdurationtos(target);
	} else 	if (!unit.compare("REL_TIME")) {
		abs_seconds = mpds.songelapsedms / 1000;
		abs_seconds += upnpdurationtos(target);
//	} else 	if (!unit.compare("TRACK_NR")) {
	} else {
		return UPNP_E_INVALID_PARAM;
	}

	loopWakeup();
	return m_mpdcli->seek(abs_seconds) ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

///////////////// ConnectionManager methods

// "http-get:*:audio/mpeg:DLNA.ORG_PN=MP3,"
// "http-get:*:audio/L16:DLNA.ORG_PN=LPCM,"
// "http-get:*:audio/x-flac:DLNA.ORG_PN=FLAC"
static const string 
myProtocolInfo(
	"http-get:*:audio/wav:*,"
	"http-get:*:audio/wave:*,"
	"http-get:*:audio/x-wav:*,"
	"http-get:*:audio/mpeg:*,"
	"http-get:*:audio/x-mpeg:*,"
	"http-get:*:audio/mp1:*,"
	"http-get:*:audio/aac:*,"
	"http-get:*:audio/flac:*,"
	"http-get:*:audio/x-flac:*,"
	"http-get:*:audio/m4a:*,"
	"http-get:*:audio/mp4:*,"
	"http-get:*:audio/x-m4a:*,"
	"http-get:*:audio/vorbis:*,"
	"http-get:*:audio/ogg:*,"
	"http-get:*:audio/x-ogg:*,"
	"http-get:*:audio/x-scpls:*,"
	"http-get:*:audio/L16;rate=11025;channels=1:*,"
	"http-get:*:audio/L16;rate=22050;channels=1:*,"
	"http-get:*:audio/L16;rate=44100;channels=1:*,"
	"http-get:*:audio/L16;rate=48000;channels=1:*,"
	"http-get:*:audio/L16;rate=88200;channels=1:*,"
	"http-get:*:audio/L16;rate=96000;channels=1:*,"
	"http-get:*:audio/L16;rate=176400;channels=1:*,"
	"http-get:*:audio/L16;rate=192000;channels=1:*,"
	"http-get:*:audio/L16;rate=11025;channels=2:*,"
	"http-get:*:audio/L16;rate=22050;channels=2:*,"
	"http-get:*:audio/L16;rate=44100;channels=2:*,"
	"http-get:*:audio/L16;rate=48000;channels=2:*,"
	"http-get:*:audio/L16;rate=88200;channels=2:*,"
	"http-get:*:audio/L16;rate=96000;channels=2:*,"
	"http-get:*:audio/L16;rate=176400;channels=2:*,"
	"http-get:*:audio/L16;rate=192000;channels=2:*"
	);

bool UpMpd::getEventDataCM(bool all, std::vector<std::string>& names, 
						   std::vector<std::string>& values)
{
	//LOGDEB("UpMpd:getEventDataCM" << endl);

	// Our data never changes, so if this is not an unconditional request,
	// we return nothing.
	if (all) {
		names.push_back("SinkProtocolInfo");
		values.push_back(myProtocolInfo);
	}
	return true;
}

int UpMpd::getCurrentConnectionIDs(const SoapArgs& sc, SoapData& data)
{
	LOGDEB("UpMpd:getCurrentConnectionIDs" << endl);
	data.addarg("ConnectionIDs", "0");
	return UPNP_E_SUCCESS;
}

int UpMpd::getCurrentConnectionInfo(const SoapArgs& sc, SoapData& data)
{
	LOGDEB("UpMpd:getCurrentConnectionInfo" << endl);
	map<string, string>::const_iterator it;
	it = sc.args.find("ConnectionID");
	if (it == sc.args.end() || it->second.empty()) {
		return UPNP_E_INVALID_PARAM;
	}
	if (it->second.compare("0")) {
		return UPNP_E_INVALID_PARAM;
	}

	data.addarg("RcsID", "0");
	data.addarg("AVTransportID", "0");
	data.addarg("ProtocolInfo", "");
	data.addarg("PeerConnectionManager", "");
	data.addarg("PeerConnectionID", "-1");
	data.addarg("Direction", "Input");
	data.addarg("Status", "Unknown");

	return UPNP_E_SUCCESS;
}

int UpMpd::getProtocolInfo(const SoapArgs& sc, SoapData& data)
{
	LOGDEB("UpMpd:getProtocolInfo" << endl);
	data.addarg("Source", "");
	data.addarg("Sink", myProtocolInfo);

	return UPNP_E_SUCCESS;
}

/////////////////////////////////////////////////////////////////////
// Main program

#include "conftree.hxx"

static char *thisprog;

static int op_flags;
#define OPT_MOINS 0x1
#define OPT_h	  0x2
#define OPT_p	  0x4
#define OPT_d	  0x8
#define OPT_D     0x10
#define OPT_c     0x20
#define OPT_l     0x40
#define OPT_f     0x80
#define OPT_q     0x100

static const char usage[] = 
"-c configfile \t configuration file to use\n"
"-h host    \t specify host MPD is running on\n"
"-p port     \t specify MPD port\n"
"-d logfilename\t debug messages to\n"
"-l loglevel\t  log level (0-6)\n"
"-D          \t run as a daemon\n"
"-f friendlyname\t define device displayed name\n"
"-q 0|1      \t if set, we own the mpd queue, else avoid clearing it whenever we feel like it"
"  \n\n"
			;
static void
Usage(void)
{
	fprintf(stderr, "%s: usage:\n%s", thisprog, usage);
	exit(1);
}

static string myDeviceUUID;

static string datadir(DATADIR "/");
static string configdir(CONFIGDIR "/");

// Our XML description data. !Keep description.xml first!
static const char *xmlfilenames[] = {/* keep first */ "description.xml", 
	 "RenderingControl.xml", "AVTransport.xml", "ConnectionManager.xml"};

static const int xmlfilenamescnt = sizeof(xmlfilenames) / sizeof(char *);

int main(int argc, char *argv[])
{
	string mpdhost("localhost");
	int mpdport = 6600;
	// string upnplogfilename("/tmp/upmpd_libupnp.log");
	string logfilename;
	int loglevel(upnppdebug::Logger::LLINF);
	string configfile;
	string friendlyname(dfltFriendlyName);
	bool ownqueue = true;
	string upmpdcliuser("upmpdcli");
	string pidfilename("/var/run/upmpdcli.pid");

	const char *cp;
	if ((cp = getenv("UPMPD_HOST")))
		mpdhost = cp;
	if ((cp = getenv("UPMPD_PORT")))
		mpdport = atoi(cp);
	if ((cp = getenv("UPMPD_FRIENDLYNAME")))
		friendlyname = atoi(cp);
	if ((cp = getenv("UPMPD_CONFIG")))
		configfile = cp;

	thisprog = argv[0];
	argc--; argv++;
	while (argc > 0 && **argv == '-') {
		(*argv)++;
		if (!(**argv))
			Usage();
		while (**argv)
			switch (*(*argv)++) {
			case 'D':	op_flags |= OPT_D; break;
			case 'c':	op_flags |= OPT_c; if (argc < 2)  Usage();
				configfile = *(++argv); argc--; goto b1;
			case 'f':	op_flags |= OPT_f; if (argc < 2)  Usage();
				friendlyname = *(++argv); argc--; goto b1;
			case 'd':	op_flags |= OPT_d; if (argc < 2)  Usage();
				logfilename = *(++argv); argc--; goto b1;
			case 'h':	op_flags |= OPT_h; if (argc < 2)  Usage();
				mpdhost = *(++argv); argc--; goto b1;
			case 'l':	op_flags |= OPT_l; if (argc < 2)  Usage();
				loglevel = atoi(*(++argv)); argc--; goto b1;
			case 'p':	op_flags |= OPT_p; if (argc < 2)  Usage();
				mpdport = atoi(*(++argv)); argc--; goto b1;
			case 'q':	op_flags |= OPT_q; if (argc < 2)  Usage();
				ownqueue = atoi(*(++argv)) != 0; argc--; goto b1;
			default: Usage();	break;
			}
	b1: argc--; argv++;
	}

	if (argc != 0)
		Usage();

	if (!configfile.empty()) {
		ConfSimple config(configfile.c_str(), 1, true);
		if (!config.ok()) {
			cerr << "Could not open config: " << configfile << endl;
			return 1;
		}
		string value;
		if (!(op_flags & OPT_d))
			config.get("logfilename", logfilename);
		if (!(op_flags & OPT_f))
			config.get("friendlyname", friendlyname);
		if (!(op_flags & OPT_l) && config.get("loglevel", value))
			loglevel = atoi(value.c_str());
		if (!(op_flags & OPT_h))
			config.get("mpdhost", mpdhost);
		if (!(op_flags & OPT_p) && config.get("mpdport", value)) {
			mpdport = atoi(value.c_str());
		}
		if (!(op_flags & OPT_q) && config.get("ownqueue", value)) {
			ownqueue = atoi(value.c_str()) != 0;
		}
	}

	if (upnppdebug::Logger::getTheLog(logfilename) == 0) {
		cerr << "Can't initialize log" << endl;
		return 1;
	}
	upnppdebug::Logger::getTheLog("")->setLogLevel(upnppdebug::Logger::LogLevel(loglevel));

    Pidfile pidfile(pidfilename);

	// If started by root, do the pidfile + change uid thing
	uid_t runas(0);
	if (geteuid() == 0) {
		struct passwd *pass = getpwnam(upmpdcliuser.c_str());
		if (pass == 0) {
			LOGFAT("upmpdcli won't run as root and user " << upmpdcliuser << 
				   " does not exist " << endl);
			return 1;
		}
		runas = pass->pw_uid;

		pid_t pid;
		if ((pid = pidfile.open()) != 0) {
			LOGFAT("Can't open pidfile: " << pidfile.getreason() << 
				   ". Return (other pid?): " << pid << endl);
			return 1;
		}
		if (pidfile.write_pid() != 0) {
			LOGFAT("Can't write pidfile: " << pidfile.getreason() << endl);
			return 1;
		}
	}

	if ((op_flags & OPT_D)) {
		if (daemon(1, 0)) {
			LOGFAT("Daemon failed: errno " << errno << endl);
			return 1;
		}
	}

	if (geteuid() == 0) {
		// Need to rewrite pid, it may have changed with the daemon call
		pidfile.write_pid();
		setuid(runas);
	}

	// Initialize libupnpp, and check health
	LibUPnP *mylib = LibUPnP::getLibUPnP(true);
	if (!mylib) {
		LOGFAT("Can't get LibUPnP" << endl);
		return 1;
	}
	if (!mylib->ok()) {
		LOGFAT("Lib init failed: " <<
			   mylib->errAsString("main", mylib->getInitError()) << endl);
		return 1;
	}
	// mylib->setLogFileName(upnplogfilename, LibUPnP::LogLevelDebug);

	// Initialize MPD client module
	MPDCli mpdcli(mpdhost, mpdport);
	if (!mpdcli.ok()) {
		LOGFAT("MPD connection failed" << endl);
		return 1;
	}
	
	// Create unique ID
	string UUID = LibUPnP::makeDevUUID(friendlyname);

	// Read our XML data to make it available from the virtual directory
	string reason;
	unordered_map<string, string> xmlfiles;
	for (int i = 0; i < xmlfilenamescnt; i++) {
		string filename = path_cat(datadir, xmlfilenames[i]);
		string data;
		if (!file_to_string(filename, data, &reason)) {
			LOGFAT("Failed reading " << filename << " : " << reason << endl);
			return 1;
		}
		if (i == 0) {
			// Special for description: set UUID and friendlyname
			data = regsub1("@UUID@", data, UUID);
			data = regsub1("@FRIENDLYNAME@", data, friendlyname);
		}
		xmlfiles[xmlfilenames[i]] = data;
	}

	// Initialize the UPnP device object.
	UpMpd device(string("uuid:") + UUID, xmlfiles, &mpdcli,
				 ownqueue ? UpMpd::upmpdOwnQueue : UpMpd::upmpdNone);

	// And forever generate state change events.
	LOGDEB("Entering event loop" << endl);
	device.eventloop();

	return 0;
}

/* Local Variables: */
/* mode: c++ */
/* c-basic-offset: 4 */
/* tab-width: 4 */
/* indent-tabs-mode: t */
/* End: */
