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
 *   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#ifndef _PICOXML_H_INCLUDED_
#define _PICOXML_H_INCLUDED_

/** 
 * PicoXMLParser: a single include file parser for an XML-like, but
 * restricted language, adequate for config files, not for arbitrary
 * externally generated data.
 * 
 *  - The code depends on nothing but the "classical" C++ standard
 *    library (c++11 not necessary).
 *  - The input to the parser is a single c++ string. Does not deal with
 *    input in several pieces or files.
 *  - SAX mode only. You have access to the tag stack. I've always
 *    found DOM mode less usable.
 *  - Checks for proper tag nesting and not much else.
 *  - ! No CDATA
 *  - ! Attributes should really really not contain XML special chars.
 *  - Entity decoding is left as an exercise to the user.
 *
 * A typical input would be like the following (you can add XML
 * declarations, whitespace and newlines to taste).
 *
 * <top>top chrs1<sub attr="attrval">sub chrs</sub>top chrs2 <emptyelt /></top>
 *
 * Usage: subclass PicoXMLParser, overriding the methods in the
 *  "protected:" section (look there for more details), call the
 * constructor with your input, then call parse().
 */

#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <iostream>

class PicoXMLParser {
public:
    PicoXMLParser(const std::string& input)
        : m_in(input), m_pos(0) {
    }
    virtual ~PicoXMLParser() { }

    virtual bool parse() {
        // skip initial whitespace and XML decl. On success, returns with
        // current pos on first tag '<'
        if (!skipDecl()) {
            return false;
        }
        if (nomore()) {
            // empty file
            return true;
        }
        
        for (;;) {
            // Current char is '<' and the next char is not '?'
            //std::cerr<< "m_pos "<< m_pos<<" char "<< m_in[m_pos] << std::endl;
            m_pos++;
            if (nomore()) {
                m_reason << "EOF within tag";
                return false;
            }
            std::string::size_type spos = m_pos;
            int isendtag = m_in[m_pos] == '/' ? 1 : 0;

            skipStr(">");
            if (m_pos == std::string::npos || m_pos <= spos + 1) {
                m_reason << "Empty tag or EOF inside tag. pos " << spos;
                return false;
            }

            int emptyel = m_in[m_pos-2] == '/' ? 1 : 0;
            if (emptyel && isendtag) {
                m_reason << "Bad tag </xx/> at cpos " << spos;
                return false;
            }
                    
            std::string tag =
                m_in.substr(spos + isendtag,
                            m_pos - (spos + 1 + isendtag + emptyel));
            //std::cerr << "TAG NAME [" << tag << "]\n";
            trimtag(tag);
            std::map<std::string, std::string> attrs;
            if (!parseattrs(tag, attrs)) {
                return false;
            }
            if (isendtag) {
                if (m_tagstack.empty() || tag.compare(m_tagstack.back())) {
                    m_reason << "Closing not open tag " << tag <<
                        " at cpos " << m_pos;
                    return false;
                }
                m_tagstack.pop_back();
                endElement(tag);
            } else {
                startElement(tag, attrs);
                m_tagstack.push_back(tag);
                if (emptyel) {
                    m_tagstack.pop_back();
                    endElement(tag);
                }
            }
            spos = m_pos;
            m_pos = m_in.find("<", m_pos);
            if (nomore()) {
                if (!m_tagstack.empty()) {
                    m_reason << "EOF hit inside open element";
                    return false;
                }
                return true;
            }
            if (m_pos != spos) {
                characterData(m_in.substr(spos, m_pos - spos));
            }
        }
        return false;
    }

    virtual std::string getReason() {
        return m_reason.str();
    }
        
protected:

    /* Methods to be overriden */

    /** 
     * Called when seeing an opening tag.
     * @param tagname the tag name 
     * @param attrs a map of attribute name/value pairs
     */
    virtual void startElement(const std::string& /*tagname*/,
                              const std::map<std::string, std::string>&
                              /* attrs */) {
    }

    /**
     * Called when closing a tag. You should probably have been
     * accumulating text and stuff since the tag opening.
     * @param tagname the tag name.
     */
    virtual void endElement(const std::string& /*tagname*/) {}

    /*
     * Called when we see non-tag data.
     * @param data the data.
     */
    virtual void characterData(const std::string& /*data*/) {}

    /*
     * Gives access to the current path in the tree. Attributes are
     * not kept in there though, you'll have to do this yourself.
     * @return a const ref to a vector of tag names.
     */
    virtual const std::vector<std::string>& tagStack() {
        return m_tagstack;
    }


private:

    const std::string& m_in;
    std::string::size_type m_pos;
    std::stringstream m_reason;
    std::vector<std::string> m_tagstack;
    
    bool nomore() const {
        return m_pos == std::string::npos || m_pos == m_in.size();
    }
    bool skipWS(const std::string& in, std::string::size_type& pos) {
        if (pos == std::string::npos)
            return false;
        pos = in.find_first_not_of(" \t\n\r", pos);
        return pos != std::string::npos;
    }
    bool skipStr(const std::string& str) {
        if (m_pos == std::string::npos)
            return false;
        m_pos = m_in.find(str, m_pos);
        if (m_pos != std::string::npos)
            m_pos += str.size();
        return m_pos != std::string::npos;
    }
    int peek() const {
        if (nomore())
            return -1;
        return m_in[m_pos + 1];
    }
    void trimtag(std::string& tagname) {
        std::string::size_type trimpos = tagname.find_last_not_of(" \t\n\r");
        if (trimpos != std::string::npos) {
            tagname = tagname.substr(0, trimpos+1);
        }
    }

    bool skipDecl() {
        for (;;) {
            if (!skipWS(m_in, m_pos)) {
                m_reason << "EOF during initial ws skip";
                return true;
            }
            if (m_in[m_pos] != '<') {
                m_reason << "EOF file does not begin with decl/tag";
                return false;
            }
            if (peek() == '?') {
                if (!skipStr("?>")) {
                    m_reason << "EOF while looking for end of xml decl";
                    return false;
                }
            } else {
                break;
            }
        }
        return true;
    }
    
    bool parseattrs(std::string& tag,
                    std::map<std::string, std::string>& attrs) {
        //std::cerr << "parseattrs: [" << tag << "]\n";
        attrs.clear();
        std::string::size_type spos = tag.find_first_of(" \t\n\r");
        if (spos == std::string::npos)
            return true;
        std::string tagname = tag.substr(0, spos);
        //std::cerr << "tag name [" << tagname << "] pos " << spos << "\n";
        skipWS(tag, spos);

        for (;;) {
            //std::cerr << "top of loop [" << tag.substr(spos) << "]\n";
            std::string::size_type epos = tag.find_first_of(" \t\n\r=", spos);
            if (epos == std::string::npos) {
                m_reason << "Bad attributes syntax at cpos " << m_pos + epos;
                return false;
            }
            std::string attrnm = tag.substr(spos, epos - spos);
            if (attrnm.empty()) {
                m_reason << "Empty attribute name ?? at cpos " << m_pos + epos;
                return false;
            }
            //std::cerr << "attr name [" << attrnm << "]\n";
            skipWS(tag, epos);
            if (epos == std::string::npos || epos == tag.size() - 1 ||
                tag[epos] != '=') {
                m_reason <<"Missing equal sign or value at cpos " << m_pos+epos;
                return false;
            }
            epos++;
            skipWS(tag, epos);
            if (tag[epos] != '"' || epos == tag.size() - 1) {
                m_reason << "Missing dquote or value at cpos " << m_pos+epos;
                return false;
            }
            spos = epos + 1;
            epos = tag.find_first_of("\"", spos);
            if (epos == std::string::npos) {
                m_reason << "Missing closing dquote at cpos " << m_pos+spos;
                return false;
            }
            attrs[attrnm] = tag.substr(spos, epos - spos);
            //std::cerr << "attr value [" << attrs[attrnm] << "]\n";
            if (epos == tag.size() - 1) {
                break;
            }
            epos++;
            skipWS(tag, epos);
            if (epos == tag.size() - 1) {
                break;
            }
            spos = epos;
        }
        tag = tagname;
        return true;
    }
};
#endif /* _PICOXML_H_INCLUDED_ */
