/* Copyright (C) 2016-2020 J.F.Dockes
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
#ifndef _MAIN_H_X_INCLUDED_
#define _MAIN_H_X_INCLUDED_

#include <string>

extern const std::string g_upmpdcli_package_version;
extern std::string g_configfilename;
extern std::string g_datadir;
extern std::string g_cachedir;
// If enabled by the configuration this is the document root for the libnpupnp Web server, possibly
// used by mediaserver plugins to serve misc local files
// Note that this is not a direct read of the configuration variable which has special values:
//   0: web server is disabled
//   1: determine an appropriate location depending on who we are running as
//   absolute path: use it
// 0 results into an empty value here.
// 1 into typically /var/cache/upmpdcli/www or $HOME/.cache/upmpdcli/www
extern std::string g_npupnpwebdocroot;

extern bool g_enableL16;
extern bool g_lumincompat;
class ConfSimple;
// A scratchpad for modules to record state information across restart
// (e.g. Source, Radio channel).
extern ConfSimple *g_state;

extern bool getOptionValue(const std::string& nm, std::string& value,
                           const std::string& dflt = std::string());
extern bool getBoolOptionValue(const std::string& nm, bool dflt);
extern int getIntOptionValue(const std::string& nm, int dflt);

// Start media server. This can be called either from main() if some
// streaming services plugins are active (have a defined user), or
// from ohcredentials when a service is activated (it may not be
// configured locally). Uses static data and only does anything if the
// device is not already started.
extern bool startMediaServer(bool enable);

// Read file from datadir
bool readLibFile(const std::string& name, std::string& contents);

typedef struct ohInfoDesc {
    std::string name;
    std::string info;
    std::string url;
    std::string imageUri;
} ohInfoDesc_t;

typedef struct ohProductDesc {
    ohInfoDesc_t manufacturer;
    ohInfoDesc_t model;
    ohInfoDesc_t product;
    std::string room;
} ohProductDesc_t;


extern const size_t ohcreds_segsize;
extern const char *ohcreds_segpath;
extern const int ohcreds_segid;

#endif /* _MAIN_H_X_INCLUDED_ */
