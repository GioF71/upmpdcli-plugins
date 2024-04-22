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
#ifndef _OHPRODUCT_H_X_INCLUDED_
#define _OHPRODUCT_H_X_INCLUDED_

#include <string>
#include <vector>

#include "libupnpp/device/device.hxx"
#include "libupnpp/soaphelp.hxx"

#include "upmpd.hxx"
#include "ohservice.hxx"

class UpMpd;
class UpMpdOpenHome;
using namespace UPnPP;

class OHProduct : public OHService {
public:
    OHProduct(UpMpd *dev, UpMpdOpenHome *udev, ohProductDesc_t& ohProductDesc, int version);
    virtual ~OHProduct() = default;
    
    int iSetSourceIndex(int index);
    int iSetSourceIndexByName(const std::string& nm);

protected:
    virtual bool makestate(std::unordered_map<std::string, std::string> &st);

private:
    int manufacturer(const SoapIncoming& sc, SoapOutgoing& data);
    int model(const SoapIncoming& sc, SoapOutgoing& data);
    int product(const SoapIncoming& sc, SoapOutgoing& data);
    int standby(const SoapIncoming& sc, SoapOutgoing& data);
    int setStandby(const SoapIncoming& sc, SoapOutgoing& data);
    int sourceCount(const SoapIncoming& sc, SoapOutgoing& data);
    int sourceXML(const SoapIncoming& sc, SoapOutgoing& data);
    int sourceIndex(const SoapIncoming& sc, SoapOutgoing& data);
    int setSourceIndex(const SoapIncoming& sc, SoapOutgoing& data);
    int setSourceIndexByName(const SoapIncoming& sc, SoapOutgoing& data);
    int setSourceBySystemName(const SoapIncoming& sc, SoapOutgoing& data);
    int source(const SoapIncoming& sc, SoapOutgoing& data);
    int attributes(const SoapIncoming& sc, SoapOutgoing& data);
    int sourceXMLChangeCount(const SoapIncoming& sc, SoapOutgoing& data);

    int iSrcNameToIndex(const std::string& nm);
    void listScripts(std::vector<std::pair<std::string, std::string>>& sources);
    
    ohProductDesc_t& m_ohProductDesc;
    int m_sourceIndex;
    bool m_standby;
    std::string m_standbycmd;
    // (Type, Name) list
    std::vector<std::pair<std::string, std::string>> m_sources;
    // This will be replaced by config data or default in listScripts(). Init anyway just in case.
    std::string m_scripts_dir{DATADIR "/src_scripts"};
    // Data for the "attributes" action. This lists the service available from this renderer (we add
    // other available services during initialization).
    std::string m_csattrs{"Info Time Volume"};
    // The XML returned by the SourceXML action. Built during init.
    std::string m_csxml;
};

#endif /* _OHPRODUCT_H_X_INCLUDED_ */
