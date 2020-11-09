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

#include "mediaserver.hxx"

#include "main.hxx"
#include "conman.hxx"
#include "contentdirectory.hxx"

using namespace std;

bool MediaServer::readLibFile(const string& name, string& contents)
{
    if (name.empty()) {
        if (!::readLibFile("MS-description.xml", contents)) {
            return false;
        }
        contents = regsub1("@UUIDMEDIA@", contents, getDeviceId());
        contents = regsub1("@FRIENDLYNAMEMEDIA@", contents, m_fname);
        return true;
    } else {
        return ::readLibFile(name, contents);
    }
}

MediaServer::MediaServer(UpnpDevice *root, const string& deviceid,
                         const string& friendlyname, bool enabled)
    : UpnpDevice(root, deviceid), m_UDN(deviceid), m_fname(friendlyname)
{
    m_cd = new ContentDirectory(this, enabled);
    m_cm = new UpMpdConMan(this);
}


MediaServer::~MediaServer()
{
    delete m_cd;
    delete m_cm;
}
