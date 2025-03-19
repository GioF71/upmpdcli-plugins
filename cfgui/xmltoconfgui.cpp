/* Copyright (C) 2025 J.F.Dockes
 *
 * License: GPL 2.1
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
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
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include "xmltoconfgui.h"

#include <QString>
#include <QDebug>

#include <map>
#include <string>

#include "confgui.h"
#include "smallut.h"
#include "picoxml.h"

namespace confgui {

static QString u8s2qs(const std::string& us)
{
    return QString::fromUtf8(us.c_str());
}

static const std::string& mapfind(
    const std::string& nm, const std::map<std::string, std::string>& mp)
{
    static std::string strnull;
    auto it = mp.find(nm);
    if (it == mp.end()) {
        return strnull;
    }
    return it->second;
}

static std::string looksLikeAssign(const std::string& _data)
{
    std::string data(_data);
    trimstring(data, "\r\n");
    // qDebug() << "looksLikeAssign. data: [" << data << "]";
    auto eq = data.find('=');
    auto nl = data.find_first_of("\r\n");
    if (eq != std::string::npos && (nl == std::string::npos || nl > eq)) {
        auto nm = data.substr(0, eq);
        trimstring(nm);
        // qDebug() << "looksLikeAssign. returning: [" << nm << "]";
        return nm;
    }
    return std::string();
}

ConfTabsW *xmlToConfGUI(const std::string& xml, std::string& toptext,
                        ConfLinkFact* lnkf, QWidget *parent)
{
    //qDebug() << "xmlToConfGUI: [" << xml << "]";

    class XMLToConfGUI : public PicoXMLParser {
    public:
        XMLToConfGUI(const std::string& x, ConfLinkFact *lnkf, QWidget *parent)
            : PicoXMLParser(x), m_lnkfact(lnkf), m_parent(parent),
              m_idx(0), m_hadTitle(false), m_hadGroup(false) {
        }
        virtual ~XMLToConfGUI() {}

        virtual void startElement(const std::string& tagname,
                                  const std::map<std::string, std::string>& attrs) {
            if (tagname == "var") {
                m_curvar = mapfind("name", attrs);
                m_curvartp = mapfind("type", attrs);
                m_curvarvals = mapfind("values", attrs);
                //qDebug() << "Curvar: " << m_curvar;
                if (m_curvar.empty() || m_curvartp.empty()) {
                    throw std::runtime_error(
                        "<var> with no name attribute or no type ! nm [" +
                        m_curvar + "] tp [" + m_curvartp + "]");
                } else {
                    m_brief.clear();
                    m_descr.clear();
                }
            } else if (tagname == "filetitle" || tagname == "grouptitle") {
                m_other.clear();
            }
        }

        virtual void endElement(const std::string& tagname) {
            if (tagname == "var") {
                if (!m_hadTitle) {
                    m_w = new ConfTabsW(m_parent, "Teh title", m_lnkfact);
                    m_hadTitle = true;
                }
                if (!m_hadGroup) {
                    m_idx = m_w->addPanel("Group title");
                    m_hadGroup = true;
                }
                auto tooltip = u8s2qs(std::string("(") + m_curvar + ") " + m_descr);
                ConfTabsW::ParamType paramtype;
                if (m_curvartp == "bool") {
                    paramtype = ConfTabsW::CFPT_BOOL;
                } else if (m_curvartp == "int") {
                    paramtype = ConfTabsW::CFPT_INT;
                } else if (m_curvartp == "string") {
                    paramtype = ConfTabsW::CFPT_STR;
                } else if (m_curvartp == "cstr") {
                    paramtype = ConfTabsW::CFPT_CSTR;
                } else if (m_curvartp == "cstrl") {
                    paramtype = ConfTabsW::CFPT_CSTRL;
                } else if (m_curvartp == "fn") {
                    paramtype = ConfTabsW::CFPT_FN;
                } else if (m_curvartp == "dfn") {
                    paramtype = ConfTabsW::CFPT_FN;
                } else if (m_curvartp == "strl") {
                    paramtype = ConfTabsW::CFPT_STRL;
                } else if (m_curvartp == "dnl") {
                    paramtype = ConfTabsW::CFPT_DNL;
                } else {
                    throw std::runtime_error("Bad type " + m_curvartp + " for " + m_curvar);
                }
                rtrimstring(m_brief, " .");
                switch (paramtype) {
                case ConfTabsW::CFPT_BOOL: {
                    int def = atoi(m_curvarvals.c_str());
                    m_w->addParam(m_idx, paramtype, u8s2qs(m_curvar), u8s2qs(m_brief), tooltip, def);
                    break;
                }
                case ConfTabsW::CFPT_INT: {
                    std::vector<std::string> vals;
                    stringToTokens(m_curvarvals, vals);
                    int min = 0, max = 0, def = 0;
                    if (vals.size() >= 3) {
                        min = atoi(vals[0].c_str());
                        max = atoi(vals[1].c_str());
                        def = atoi(vals[2].c_str());
                    } else {
                        std::cerr << "NO MIN/MAX/DEF values for " << m_curvar << '\n';
                        exit(1);
                    }
                    m_w->addParam(m_idx, paramtype, u8s2qs(m_curvar), u8s2qs(m_brief), tooltip,
                                  min, max, (QStringList*)((char*)0+def));
                    break;
                }
                case  ConfTabsW::CFPT_CSTR:
                case ConfTabsW::CFPT_CSTRL: {
                    std::vector<std::string> cstrl;
                    stringToTokens(neutchars(m_curvarvals, "\n\r"), cstrl);
                    QStringList qstrl;
                    for (unsigned int i = 0; i < cstrl.size(); i++) {
                        qstrl.push_back(u8s2qs(cstrl[i]));
                    }
                    m_w->addParam(m_idx, paramtype, u8s2qs(m_curvar),
                                  u8s2qs(m_brief), tooltip, 0, 0, &qstrl);
                    break;
                }
                default:
                    m_w->addParam(m_idx, paramtype, u8s2qs(m_curvar), u8s2qs(m_brief), tooltip);
                }
            } else if (tagname == "filetitle") {
                m_w = new ConfTabsW(m_parent, u8s2qs(m_other), m_lnkfact);
                m_hadTitle = true;
                m_other.clear();
            } else if (tagname == "grouptitle") {
                if (!m_hadTitle) {
                    m_w = new ConfTabsW(m_parent, "Teh title", m_lnkfact);
                    m_hadTitle = true;
                }
                // Get rid of "parameters" in the title, it's not interesting
                // and this makes our tab headers smaller.
                std::string ps{"parameters"};
                std::string::size_type pos = m_other.find(ps);
                if (pos != std::string::npos) {
                    m_other = m_other.replace(pos, ps.size(), "");
                }
                m_idx = m_w->addPanel(u8s2qs(m_other));
                m_hadGroup = true;
                m_other.clear();
            } else if (tagname == "descr") {
            } else if (tagname == "brief") {
                m_brief = neutchars(m_brief, "\n\r");
            }
        }

        virtual void characterData(const std::string& data) {
            const std::string& curtag = tagStack().back();
            if (curtag == "brief") {
                m_brief += data;
            } else if (curtag == "descr") {
                m_descr += data;
            } else if (curtag == "filetitle" || curtag == "grouptitle") {
                // We don't want \n in there
                m_other += neutchars(data, "\n\r");
                m_other += " ";
            } else if (curtag == "subkey" || curtag == "varsetting") {
                // Actual config statements go to the extracted text.
                m_toptext += data;
            } else if (curtag ==  "confcomments") {
                std::string nvarname = looksLikeAssign(data);
                if (!nvarname.empty() && nvarname != m_curvar) {
                    std::cerr << "Var assigned [" << nvarname << "] mismatch "
                        "with current variable [" << m_curvar << "]\n";
                }
                m_toptext += data;
            }
        }

        ConfTabsW *m_w;

        ConfLinkFact *m_lnkfact;
        QWidget *m_parent;
        int m_idx;
        std::string m_curvar;
        std::string m_curvartp;
        std::string m_curvarvals;
        std::string m_brief;
        std::string m_descr;
        std::string m_other;
        std::string m_toptext;
        bool m_hadTitle;
        bool m_hadGroup;
    };

    XMLToConfGUI parser(xml, lnkf, parent);
    try {
        if (!parser.parse()) {
            std::cerr << "Parse failed: " << parser.getLastErrorMessage() << "\n";
            return 0;
        }
    } catch (const std::runtime_error& e) {
        std::cerr << e.what() << "\n";
        return 0;
    }
    toptext = parser.m_toptext;
    return parser.m_w;
}

} // namespace confgui

