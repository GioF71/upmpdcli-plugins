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
#ifndef _MAIN_H_X_INCLUDED_
#define _MAIN_H_X_INCLUDED_

#include <string>
#include <unordered_set>

extern const std::string g_upmpdcli_package_version;
extern std::string g_configfilename;
extern std::string g_datadir;
extern std::string g_cachedir;
extern bool g_enableL16;
extern bool g_lumincompat;
class ConfSimple;
// The global static configuration data
extern ConfSimple *g_config;
// A scratchpad for modules to record state information across restart
// (e.g. Source, Radio channel).
extern ConfSimple *g_state;

// Start media server upmpdcli process (-m 2). This can be called
// either from main() if some streaming services plugins are active
// (have a defined user), or from ohcredentials when a service is
// activated (it may not be configured locally). Uses static data and
// only does anything if the process is not already started.
extern bool startMsOnlyProcess();

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
