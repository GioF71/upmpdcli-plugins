/* Copyright (C) 2018-2020 J.F.Dockes
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

#include "ohcredentials.hxx"

#include <sys/stat.h>

#include <functional>
#include <iostream>
#include <map>
#include <utility>
#include <vector>
#include <sstream>

#include "conftree.h"
#include "main.hxx"
#include "smallut.h"
#include "pathut.h"
#include "execmd.h"
#include "sysvshm.h"
#include "mediaserver/cdplugins/cmdtalk.h"
#include "upmpd.hxx"

#include "libupnpp/log.hxx"
#include "libupnpp/base64.hxx"
#include "libupnpp/soaphelp.hxx"
#include "libupnpp/device/device.hxx"
#include "mediaserver/cdplugins/cdplugin.hxx"
#include "mediaserver/cdplugins/plgwithslave.hxx"

using namespace std;
using namespace std::placeholders;

const size_t ohcreds_segsize{3000};
const int ohcreds_segid{923102018};
const char *ohcreds_segpath = "/etc/upmpdcli.conf";

static const string sTpCredentials("urn:av-openhome-org:service:Credentials:1");
static const string sIdCredentials("urn:av-openhome-org:serviceId:Credentials");

static const string idstring{"tidalhifi.com qobuz.com"};
static const map<string, string> idmap {
    {"tidalhifi.com", "tidal"},
    {"qobuz.com", "qobuz"}
};


// We might want to derive this into ServiceCredsQobuz,
// ServiceCredsTidal, there is a lot in common and a few diffs.
struct ServiceCreds {
    ServiceCreds() {}
    ServiceCreds(const string& inm, const string& u, const string& p,
                 const string& ep)
        : servicename(inm), user(u), password(p), encryptedpass(ep) {

        if (servicename == "qobuz") {
            // The appid used by the Qobuz python module. Has to be
            // consistent with the token obtained by the same, so we
            // return it (by convention, as seen in wiresharking
            // kazoo) in the data field. We could and do obtain the
            // appid from the module, but kazoo apparently wants it
            // before we login, so just hard-code it for now.  The
            // Python code uses the value from XBMC,285473059,
            // ohplayer uses 854233864
            g_config->get("qobuzappid", data);
            if (data.empty()) {
                data = "285473059";
            }
        } else if (servicename == "tidal") {
            g_config->get("tidalapitoken", data);
            if (data.empty()) {
                data = "pl4Vc0hemlAXD0mN";
            }
            // data used to contain the country code, but the change
            // does not appear to affect kazoo
            // data = "FR";
        }
    }

    ~ServiceCreds() {
        delete cmd;
    }

    // We need a Python helper to perform the login. That's the media
    // server gateway module, from which we only use a separate method
    // which logs-in and returns the auth data (token, etc.)
    bool maybeStartCmd() {
        LOGDEB1("ServiceCreds: " << servicename << " maybeStartCmd()\n");
        if (nullptr == cmd) {
            cmd = new CmdTalk(30);
        }
        if (cmd->running()) {
            return true;
        }
        LOGDEB("ServiceCreds: " << servicename << " starting cmd\n");
        // hostport is not needed by this login-only instance.
        return PlgWithSlave::startPluginCmd(
            *cmd, servicename, "bogus", 0,
            CDPluginServices::getpathprefix(servicename));
    }

    string login() {
        LOGDEB("ServiceCreds: " << servicename << " login\n");

        // Check if already logged-in
        if (servicename == "qobuz" || servicename == "tidal") {
            if (!servicedata["token"].empty()) {
                return servicedata["token"];
            }
        } else {
            LOGERR("Unsupported service: " << servicename << endl);
            return string();
        }

        if (!maybeStartCmd()) {
            return string();
        }
        unordered_map<string,string> res;
        if (!cmd->callproc("login", {{"user", user},
                    {"password", password}}, res)) {
            LOGERR("ServiceCreds::login: slave failure. Service " <<
                   servicename << " user " << user << endl);
            return string();
        }

        vector<string> toknames;
        if (servicename == "qobuz") {
            toknames = vector<string>{"token", "appid"};
        } else if (servicename == "tidal") {
            toknames = vector<string>{"token", "country"};
        }
        for (const auto& toknm : toknames) {
            auto it = res.find(toknm);
            if (it == res.end()) {
                LOGERR("ServiceCreds::login: no " << toknm << ". Service " <<
                       servicename << " user " << user << endl);
                return string();
            }
            servicedata[toknm] = it->second;
        }
        // Start a silent/crippled media server process (if not
        // already done) to perform the URL redirections. If the media
        // server was actually enabled by one of the services, this
        // will do nothing.
        startMediaServer(false);
        if (servicename == "qobuz") {
            data = servicedata["appid"];
        } else if (servicename == "tidal") {
            data = servicedata["country"];
        }
        return servicedata["token"];
    }

    void logout() {
        servicedata.clear();
    }

    string str() {
        string s;
        string sdata;
        for (const auto& entry:servicedata) {
            sdata += entry.first + " : " + entry.second + ", ";
        }
        s += "Service: " + servicename + " User: " + user +
            /*" Pass: "+password*/ + " Servicedata: " + sdata +
            /*" EPass: "+encryptedpass*/ + " Enabled: " +
            SoapHelp::i2s(enabled) + " Status: " + status + " Data: " + data;
        return s;
    }

    // Internal name, like "qobuz"
    string servicename;
    string user;
    string password;
    string encryptedpass;
    bool enabled{true};
    CmdTalk *cmd{0};
    // Things we obtain from the module and send to the CP
    unordered_map<string,string> servicedata;

    string status;
    // See comments about 'data' use above.
    string data;
};

class OHCredentials::Internal {
public:
    
    Internal(const string& cd) {
        opensslcmd = "openssl";
        g_config->get("opensslcmd", opensslcmd);
        cachedir = path_cat(cd, "ohcreds");
        if (!path_makepath(cachedir, 0700)) {
            LOGERR("OHCredentials: can't create cache dir " << cachedir <<endl);
            return;
        }
        keyfile = path_cat(cachedir, "credkey.pem");
        cmd.putenv("RANDFILE", path_cat(cachedir, "randfile"));

        if (!path_exists(keyfile)) {
            vector<string> acmd{opensslcmd, "genrsa", "-out", keyfile, "4096"};
            int status = cmd.doexec1(acmd);
            chmod(keyfile.c_str(), 0600);
            if (status != 0) {
                LOGERR("OHCredentials: could not create key\n");
                return;
            }
        }

        // It seems that some CPs (e.g. bubble upnp, but not kazoo)
        // expect the key in pkcs#1 format, but the default openssl
        // pkey format is pkcs#12. Explanations about the formats:
        // https://stackoverflow.com/questions/18039401/how-can-i-transform
        //-between-the-two-styles-of-public-key-format-one-begin-rsa#29707204
        //  So use the openssl rsa command with the appropriate option
        //  instead of openssl pkey
        // vector<string> acmd{opensslcmd, "pkey", "-in", keyfile, "-pubout"};
        vector<string> acmd{opensslcmd,"rsa","-in",keyfile, "-RSAPublicKey_out"};
        if (!cmd.backtick(acmd, pubkey)) {
            LOGERR("OHCredentials: could not read public key\n");
            return;
        }
        LOGDEB1("OHCredentials: my public key:\n" << pubkey << endl);
        tryLoad();
    }

    bool decrypt(const string& in, string& out) {
        vector<string> acmd{opensslcmd, "pkeyutl", "-inkey",
                keyfile, "-pkeyopt", "rsa_padding_mode:oaep", "-decrypt"};
        int status = cmd.doexec1(acmd, &in, &out);
        if (status) {
            LOGERR("OHCredentials: decrypt failed\n");
            return false;
        }
        //LOGDEB1("decrypt: [" << out << "]\n");
        return true;
    }

    bool setEnabled(const string& id, bool enabled) {
        auto it = creds.find(id);
        if (it == creds.end()) {
            return false;
        }
        it->second.enabled = enabled;
        return true;
    }

    bool save() {
        bool saveohcredentials = doingsavetofile();
        // The media server process needs the credentials for
        // translating the permanent URL into the actual media stream
        // ones. We can use either a shared memory segment or a file
        // for this purpose.
        //
        // Using a file offers less security (the creds are available
        // to anyone with physical access to the device), but they can
        // then also be used by the regular Media Server plugin,
        // allowing access by a non-ohcredentials CP (e.g. upplay)
        // without having to set them in upmpdcli.conf. In other
        // words, the Credentials service utility is extended to
        // regular CPs.
        // 
        // The choice between shmem/file is decided by the
        // saveohcredentials configuration variable
        if (saveohcredentials) {
            string credsfile = path_cat(cachedir, "screds");
            ConfSimple credsconf(credsfile.c_str());
            if (!credsconf.ok()) {
                LOGERR("OHCredentials: error opening " << credsfile <<
                       " errno " << errno << endl);
                return false;
            }
            saveToConfTree(credsconf);
            chmod(credsfile.c_str(), 0600);
        } else {
            string data;
            ConfSimple credsconf(data);
            saveToConfTree(credsconf);
            LockableShmSeg seg(ohcreds_segpath, ohcreds_segid, ohcreds_segsize,
                               true);
            if (!seg.ok()) {
                LOGERR("OHCredentials: shared memory segment allocate/attach "
                       "failed\n");
                return false;
            }
            LockableShmSeg::Accessor access(seg);
            char *cp = (char *)(access.getseg());
            ostringstream strm;
            credsconf.write(strm);
            if (strm.str().size() >= ohcreds_segsize - 1) {
                LOGERR("OHCredentials: creds size " << strm.str().size() <<
                       "won't fit in SHM segment\n");
                return false;
            }
            strncpy(cp, strm.str().c_str(), ohcreds_segsize);
            LOGDEB1("OHCredentials: shm seg content: [" << cp << "]\n");
        }
        return true;
    }

    //// This could be a private part if we were not all friends here /////
    
    bool doingsavetofile() {
        return g_config->getBool("saveohcredentials", true);
    }        

    void saveToConfTree(ConfSimple& credsconf) {
        credsconf.clear();
        for (const auto& cred : creds) {
            const string& shortid = cred.second.servicename;
            credsconf.set(shortid + "user", cred.second.user);
            credsconf.set(shortid + "pass", cred.second.password);
            // Saving the encrypted version is redundant, but it
            // avoids having to run encrypt on load.
            credsconf.set(shortid + "epass", cred.second.encryptedpass);
        }
    }

    // Try to load from configuration file at startup. Avoids having
    // to enter the password on the CP if it was previously saved.
    void tryLoad() {
        if (!doingsavetofile()) {
            return;
        }
        string credsfile = path_cat(cachedir, "screds");
        ConfSimple credsconf(credsfile.c_str(), 1);
        if (!credsconf.ok()) {
            LOGDEB("OHCredentials: error opening for read (probably not an "
                   "error)" << credsfile << " errno " << errno << endl);
            return;
        }
        for (const auto& service : idmap) {
            const string& id = service.first;
            const string& shortid = service.second;
            string user, pass, epass;
            if (credsconf.get(shortid + "user", user) && 
                credsconf.get(shortid + "pass", pass) && 
                credsconf.get(shortid + "epass", epass)) {
                LOGDEB("OHCreds: using saved creds for " << id << endl);
                creds[id] = ServiceCreds(shortid, user, pass, epass);
            }
        }
    }
    string opensslcmd;
    ExecCmd cmd;
    string cachedir;
    string keyfile;
    string pubkey;
    int seq{1};
    map<string, ServiceCreds> creds;
};


OHCredentials::OHCredentials(UpMpd *dev, UpMpdOpenHome *udev,
                             const string& cachedir)
    : OHService(sTpCredentials, sIdCredentials, "OHCredentials.xml", dev, udev),
      m(new Internal(cachedir))
{
    udev->addActionMapping(
        this, "Set",
        bind(&OHCredentials::actSet, this, _1, _2));
    udev->addActionMapping(
        this, "Clear",
        bind(&OHCredentials::actClear, this, _1, _2));
    udev->addActionMapping(
        this, "SetEnabled",
        bind(&OHCredentials::actSetEnabled, this, _1, _2));
    udev->addActionMapping(
        this, "Get",
        bind(&OHCredentials::actGet, this, _1, _2));
    udev->addActionMapping(
        this, "Login",
        bind(&OHCredentials::actLogin, this, _1, _2));
    udev->addActionMapping(
        this, "ReLogin",
        bind(&OHCredentials::actReLogin, this, _1, _2));
    udev->addActionMapping(
        this, "GetIds",
        bind(&OHCredentials::actGetIds, this, _1, _2));
    udev->addActionMapping(
        this, "GetPublicKey",
        bind(&OHCredentials::actGetPublicKey, this, _1, _2));
    udev->addActionMapping(
        this, "GetSequenceNumber",
        bind(&OHCredentials::actGetSequenceNumber, this, _1, _2));
}

OHCredentials::~OHCredentials()
{
    delete m;
}

bool OHCredentials::makestate(unordered_map<string, string> &st)
{
    st.clear();
    if (nullptr == m) {
        return false;
    }
    st["Ids"] = idstring;
    st["PublicKey"] = m->pubkey;
    st["SequenceNumber"] = SoapHelp::i2s(m->seq);
    return true;
}

int OHCredentials::actSet(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool ok = false;
    std::string in_Id;
    ok = sc.get("Id", &in_Id);
    if (!ok) {
        LOGERR("OHCredentials::actSet: no Id in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    std::string in_UserName;
    ok = sc.get("UserName", &in_UserName);
    if (!ok) {
        LOGERR("OHCredentials::actSet: no UserName in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    string in_Password;
    ok = sc.get("Password", &in_Password);
    if (!ok) {
        LOGERR("OHCredentials::actSet: no Password in params\n");
        return UPNP_E_INVALID_PARAM;
    }

    LOGDEB("OHCredentials::actSet: " << " Id " << in_Id << " UserName " <<
           in_UserName << " Password " << in_Password << endl);

    const auto it1 = idmap.find(in_Id);
    if (it1 == idmap.end()) {
        LOGERR("OHCredentials::actSet: bad service id [" << in_Id <<"]\n");
        return 800;
    }
    string servicename = it1->second;
    string cpass = base64_decode(in_Password);
    string plainpass;
    if (!m->decrypt(cpass, plainpass)) {
        LOGERR("OHCredentials::actSet: could not decrypt\n");
        return UPNP_E_INVALID_PARAM;
    }
    auto it = m->creds.find(in_Id);
    if (it == m->creds.end() || it->second.user != in_UserName ||
        it->second.password != plainpass ||
        it->second.encryptedpass != in_Password) {
        m->creds[in_Id] = ServiceCreds(servicename, in_UserName, plainpass,
                                       in_Password);
    }
    m->seq++;
    m->save();
    onEvent(nullptr);
    if (m->setEnabled(in_Id, true)) {
        return UPNP_E_SUCCESS;
    } else {
        return 800;
    }
}

int OHCredentials::actLogin(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool ok = false;
    std::string in_Id;
    ok = sc.get("Id", &in_Id);
    if (!ok) {
        LOGERR("OHCredentials::actLogin: no Id in params\n");
        return UPNP_E_INVALID_PARAM;
    }

    LOGDEB("OHCredentials::actLogin: " << " Id " << in_Id << endl);
    auto it = m->creds.find(in_Id);
    if (it == m->creds.end()) {
        LOGERR("OHCredentials::Login: Id " << in_Id << " not found\n");
        return 800;
    }
    string token = it->second.login();
    LOGDEB("OHCredentials::Login: got token " << token << endl);
    data.addarg("Token", token);

    // If login failed, erase the probably incorrect data from memory
    // and disk.
    if (token.empty()) {
        m->creds.erase(in_Id);
        m->save();
    }

    m->seq++;
    return token.empty() ? 801 : UPNP_E_SUCCESS;
}

int OHCredentials::actReLogin(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool ok = false;
    std::string in_Id;
    ok = sc.get("Id", &in_Id);
    if (!ok) {
        LOGERR("OHCredentials::actReLogin: no Id in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    std::string in_CurrentToken;
    ok = sc.get("CurrentToken", &in_CurrentToken);
    if (!ok) {
        LOGERR("OHCredentials::actReLogin: no CurrentToken in params\n");
        return UPNP_E_INVALID_PARAM;
    }

    LOGDEB("OHCredentials::actReLogin: " << " Id " << in_Id << " CurrentToken "
           << in_CurrentToken << endl);

    auto it = m->creds.find(in_Id);
    if (it == m->creds.end()) {
        LOGERR("OHCredentials::Login: Id " << in_Id << " not found\n");
        return 800;
    }
    it->second.logout();
    string token = it->second.login();
    if (token.empty()) {
        return 801;
    }
    data.addarg("NewToken", token);
    m->seq++;
    return UPNP_E_SUCCESS;
}

int OHCredentials::actClear(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool ok = false;
    std::string in_Id;
    ok = sc.get("Id", &in_Id);
    if (!ok) {
        LOGERR("OHCredentials::actClear: no Id in params\n");
        return UPNP_E_INVALID_PARAM;
    }

    LOGDEB("OHCredentials::actClear: " << " Id " << in_Id << endl);
    if (idmap.find(in_Id) == idmap.end()) {
        LOGERR("OHCredentials::actClear: bad service id [" << in_Id <<"]\n");
        return 800;
    }
    m->creds.erase(in_Id);
    m->save();
    return UPNP_E_SUCCESS;
}

int OHCredentials::actSetEnabled(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool ok = false;
    std::string in_Id;
    ok = sc.get("Id", &in_Id);
    if (!ok) {
        LOGERR("OHCredentials::actSetEnabled: no Id in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    bool in_Enabled;
    ok = sc.get("Enabled", &in_Enabled);
    if (!ok) {
        LOGERR("OHCredentials::actSetEnabled: no Enabled in params\n");
        return UPNP_E_INVALID_PARAM;
    }

    LOGDEB("OHCredentials::actSetEnabled: " << " Id " << in_Id << " Enabled " <<
           in_Enabled << endl);
    if (m->setEnabled(in_Id, in_Enabled)) {
        m->seq++;
        onEvent(nullptr);
        return UPNP_E_SUCCESS;
    } else {
        return 800;
    }
}

int OHCredentials::actGet(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool ok = false;
    std::string in_Id;
    ok = sc.get("Id", &in_Id);
    if (!ok) {
        LOGERR("OHCredentials::actGet: no Id in params\n");
        return UPNP_E_INVALID_PARAM;
    }

    LOGDEB("OHCredentials::actGet: " << " Id " << in_Id << endl);

    auto it = m->creds.find(in_Id);
    ServiceCreds emptycreds;
    ServiceCreds *credsp(&emptycreds);
    if (it != m->creds.end()) {
        credsp = &(it->second);
    } else {
        if (in_Id == "qobuz") {
            g_config->get("qobuzappid", emptycreds.data);
            if (emptycreds.data.empty()) {
                emptycreds.data = "285473059";
            }
        } else if (in_Id == "tidal") {
            g_config->get("tidalapitoken", emptycreds.data);
            if (emptycreds.data.empty()) {
                emptycreds.data = "pl4Vc0hemlAXD0mN";
            }
        }
        LOGDEB("OHCredentials::actGet: nothing found for " << in_Id << endl);
    }
    LOGDEB("OHCredentials::actGet: data for " << in_Id << " " <<
           credsp->str() << endl);
    data.addarg("UserName", credsp->user);
    // Encrypted password !
    data.addarg("Password", credsp->encryptedpass);
    // In theory enabled is set in response to setEnabled() or
    // set(). In practise, if it is not set, we don't get to the qobuz
    // settings screen in kazoo.
    data.addarg("Enabled", credsp->enabled ? "1" : "1");
    data.addarg("Status", credsp->status);
    data.addarg("Data", credsp->data);
    return UPNP_E_SUCCESS;
}

int OHCredentials::actGetIds(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHCredentials::actGetIds: " << endl);
    data.addarg("Ids", idstring);
    return UPNP_E_SUCCESS;
}

int OHCredentials::actGetPublicKey(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHCredentials::actGetPublicKey: pubkey: " << m->pubkey << endl);
    data.addarg("PublicKey", m->pubkey);
    return m->pubkey.empty() ? UPNP_E_INTERNAL_ERROR : UPNP_E_SUCCESS;
}

int OHCredentials::actGetSequenceNumber(const SoapIncoming& sc,
                                        SoapOutgoing& data)
{
    LOGDEB("OHCredentials::actGetSequenceNumber: " << endl);
    data.addarg("SequenceNumber", SoapHelp::i2s(m->seq));
    onEvent(nullptr);
    return UPNP_E_SUCCESS;
}
