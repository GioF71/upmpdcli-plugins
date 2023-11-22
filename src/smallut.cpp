/* Copyright (C) 2006-2022 J.F.Dockes
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
 *   02110-1301 USA
 */
#include "smallut.h"

#include <algorithm>
#include <cctype>
#include <cerrno>
#include <cinttypes>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <iostream>
#include <list>
#include <numeric>
#include <set>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <functional>

// Older compilers don't support stdc++ regex, but Windows does not have the Linux one. Have a
// simple class to solve the simple cases.
#if defined(_WIN32)
#define USE_STD_REGEX
#define strncasecmp _strnicmp
#define strcasecmp _stricmp
#define localtime_r(a,b) localtime_s(b,a)
#else
#define USE_LINUX_REGEX
#endif

#ifdef USE_STD_REGEX
#include <regex>
#else
#include <regex.h>
#endif

using namespace std::placeholders;

namespace MedocUtils {

int stringicmp(const std::string& s1, const std::string& s2)
{
    return strcasecmp(s1.c_str(), s2.c_str());
}

void stringtolower(std::string& io)
{
    std::transform(io.begin(), io.end(), io.begin(), [](unsigned char c) {return std::tolower(c);});
}

std::string stringtolower(const std::string& i)
{
    std::string o = i;
    stringtolower(o);
    return o;
}

void stringtoupper(std::string& io)
{
    std::transform(io.begin(), io.end(), io.begin(), [](unsigned char c) { return std::toupper(c); });
}

std::string stringtoupper(const std::string& i)
{
    std::string o = i;
    stringtoupper(o);
    return o;
}

//  s1 is already lowercase
int stringlowercmp(const std::string& s1, const std::string& s2)
{
    std::string::const_iterator it1 = s1.begin();
    std::string::const_iterator it2 = s2.begin();
    std::string::size_type size1 = s1.length(), size2 = s2.length();
    char c2;

    if (size1 < size2) {
        while (it1 != s1.end()) {
            c2 = ::tolower(*it2);
            if (*it1 != c2) {
                return *it1 > c2 ? 1 : -1;
            }
            ++it1;
            ++it2;
        }
        return size1 == size2 ? 0 : -1;
    }

    while (it2 != s2.end()) {
        c2 = ::tolower(*it2);
        if (*it1 != c2) {
            return *it1 > c2 ? 1 : -1;
        }
        ++it1;
        ++it2;
    }
    return size1 == size2 ? 0 : 1;
}

//  s1 is already uppercase
int stringuppercmp(const std::string& s1, const std::string& s2)
{
    std::string::const_iterator it1 = s1.begin();
    std::string::const_iterator it2 = s2.begin();
    std::string::size_type size1 = s1.length(), size2 = s2.length();
    char c2;

    if (size1 < size2) {
        while (it1 != s1.end()) {
            c2 = ::toupper(*it2);
            if (*it1 != c2) {
                return *it1 > c2 ? 1 : -1;
            }
            ++it1;
            ++it2;
        }
        return size1 == size2 ? 0 : -1;
    }

    while (it2 != s2.end()) {
        c2 = ::toupper(*it2);
        if (*it1 != c2) {
            return *it1 > c2 ? 1 : -1;
        }
        ++it1;
        ++it2;
    }
    return size1 == size2 ? 0 : 1;
}

bool beginswith(const std::string& big, const std::string& small)
{
    return big.compare(0, small.size(), small) == 0;
}

template <class T> bool stringToStrings(const std::string& s, T& tokens, const std::string& addseps)
{
    std::string current;
    tokens.clear();
    enum states {SPACE, TOKEN, INQUOTE, ESCAPE};
    states state = SPACE;
    for (char i : s) {
        switch (i) {
        case '"':
            switch (state) {
            case SPACE:
                state = INQUOTE;
                continue;
            case TOKEN:
                current += '"';
                continue;
            case INQUOTE:
                tokens.insert(tokens.end(), current);
                current.clear();
                state = SPACE;
                continue;
            case ESCAPE:
                current += '"';
                state = INQUOTE;
                continue;
            }
            break;
        case '\\':
            switch (state) {
            case SPACE:
            case TOKEN:
                current += '\\';
                state = TOKEN;
                continue;
            case INQUOTE:
                state = ESCAPE;
                continue;
            case ESCAPE:
                current += '\\';
                state = INQUOTE;
                continue;
            }
            break;

        case ' ':
        case '\t':
        case '\n':
        case '\r':
            switch (state) {
            case SPACE:
                continue;
            case TOKEN:
                tokens.insert(tokens.end(), current);
                current.clear();
                state = SPACE;
                continue;
            case INQUOTE:
            case ESCAPE:
                current += i;
                continue;
            }
            break;

        default:
            if (!addseps.empty() && addseps.find(i) != std::string::npos) {
                switch (state) {
                case ESCAPE:
                    state = INQUOTE;
                    break;
                case INQUOTE:
                    break;
                case SPACE:
                    tokens.insert(tokens.end(), std::string(1, i));
                    continue;
                case TOKEN:
                    tokens.insert(tokens.end(), current);
                    current.erase();
                    tokens.insert(tokens.end(), std::string(1, i));
                    state = SPACE;
                    continue;
                }
            } else switch (state) {
                case ESCAPE:
                    state = INQUOTE;
                    break;
                case SPACE:
                    state = TOKEN;
                    break;
                case TOKEN:
                case INQUOTE:
                    break;
                }
            current += i;
        }
    }
    switch (state) {
    case SPACE:
        break;
    case TOKEN:
        tokens.insert(tokens.end(), current);
        break;
    case INQUOTE:
    case ESCAPE:
        return false;
    }
    return true;
}

template <class T> void stringsToString(const T& tokens, std::string& s)
{
    if (tokens.empty())
        return;
    for (const auto& tok : tokens) {
        if (tok.empty()) {
            s.append("\"\" ");
            continue;
        }
        bool hasblanks = tok.find_first_of(" \t\n") != std::string::npos;
        if (hasblanks) {
            s.append(1, '"');
        }
        for (auto car : tok) {
            if (car == '"') {
                s.append(1, '\\');
                s.append(1, car);
            } else {
                s.append(1, car);
            }
        }
        if (hasblanks) {
            s.append(1, '"');
        }
        s.append(1, ' ');
    }
    s.resize(s.size()-1);
}

template <class T> std::string stringsToString(const T& tokens)
{
    std::string out;
    stringsToString<T>(tokens, out);
    return out;
}

template <class T> void stringsToCSV(const T& tokens, std::string& s, char sep)
{
    s.erase();
    for (const auto& tok : tokens) {
        bool needquotes = false;
        if (tok.empty() || tok.find_first_of(std::string(1, sep) + "\"\n") != std::string::npos) {
            needquotes = true;
        }
        if (needquotes) {
            s.append(1, '"');
        }
        for (auto&& car : tok) {
            if (car == '"') {
                s.append(2, '"');
            } else {
                s.append(1, car);
            }
        }
        if (needquotes) {
            s.append(1, '"');
        }
        s.append(1, sep);
    }
    // Remove last separator.
    if (!s.empty())
        s.pop_back();
}

template <class T> std::string commonprefix(const T& values)
{
    if (values.empty())
        return {};
    if (values.size() == 1)
        return *values.begin();
    unsigned int i = 0;
    for (;;i++) {
        auto it = values.begin();
        if (it->size() <= i) {
            goto out;
        }
        auto val = (*it)[i];
        it++;
        for (;it < values.end(); it++) {
            if (it->size() <= i || (*it)[i] != val) {
                goto out;
            }
        }
    }
out:
    return values.begin()->substr(0, i);
}

#ifdef SMALLUT_EXTERNAL_INSTANTIATIONS
#include "smallut_instantiate.h"
#else
template bool stringToStrings<std::list<std::string>>(
    const std::string&, std::list<std::string>&, const std::string&);
template bool stringToStrings<std::vector<std::string>>(const std::string&,
                                               std::vector<std::string>&, const std::string&);
template bool stringToStrings<std::set<std::string>>(const std::string&,
                                                     std::set<std::string>&, const std::string&);
template bool stringToStrings<std::unordered_set<std::string>>
(const std::string&, std::unordered_set<std::string>&, const std::string&);
template void stringsToString<std::list<std::string>>(const std::list<std::string>&, std::string&);
template void stringsToString<std::vector<std::string>>(
    const std::vector<std::string>&, std::string&);
template void stringsToString<std::set<std::string>>(const std::set<std::string>&, std::string&);
template void stringsToString<std::unordered_set<std::string>>(
    const std::unordered_set<std::string>&, std::string&);
template std::string stringsToString<std::list<std::string>>(const std::list<std::string>&);
template std::string stringsToString<std::vector<std::string>>(const std::vector<std::string>&);
template std::string stringsToString<std::set<std::string>>(const std::set<std::string>&);
template std::string stringsToString<std::unordered_set<std::string>>(
    const std::unordered_set<std::string>&);
template void stringsToCSV<std::list<std::string>>(
    const std::list<std::string>&, std::string&, char);
template void stringsToCSV<std::vector<std::string>>(
    const std::vector<std::string>&, std::string&, char);
template std::string commonprefix<std::vector<std::string>>(const std::vector<std::string>&values);
#endif

void stringToTokens(const std::string& str, std::vector<std::string>& tokens,
                    const std::string& delims, bool skipinit, bool allowempty)
{
    std::string::size_type startPos = 0, pos;

    // Skip initial delims, return empty if this eats all.
    if (skipinit &&
        (startPos = str.find_first_not_of(delims, 0)) == std::string::npos) {
        return;
    }
    while (startPos < str.size()) {
        // Find next delimiter or end of string (end of token)
        pos = str.find_first_of(delims, startPos);

        // Add token to the vector and adjust start
        if (pos == std::string::npos) {
            tokens.push_back(str.substr(startPos));
            break;
        }
        if (pos == startPos) {
            // Dont' push empty tokens after first
            if (allowempty || tokens.empty()) {
                tokens.emplace_back();
            }
            startPos = ++pos;
        } else {
            tokens.push_back(str.substr(startPos, pos - startPos));
            startPos = ++pos;
        }
    }
}

void stringSplitString(const std::string& str, std::vector<std::string>& tokens,
                       const std::string& sep)
{
    if (str.empty() || sep.empty())
        return;

    std::string::size_type startPos = 0, pos;

    while (startPos < str.size()) {
        // Find next delimiter or end of string (end of token)
        pos = str.find(sep, startPos);
        // Add token to the vector and adjust start
        if (pos == std::string::npos) {
            tokens.push_back(str.substr(startPos));
            break;
        }
        if (pos == startPos) {
            // Initial or consecutive separators
            tokens.emplace_back();
        } else {
            tokens.push_back(str.substr(startPos, pos - startPos));
        }
        startPos = pos + sep.size();
    }
}

bool stringToBool(const std::string& s)
{
    if (s.empty()) {
        return false;
    }
    if (isdigit(s[0])) {
        int val = atoi(s.c_str());
        return val != 0;
    }
    return s.find_first_of("yYtT") == 0;
}

std::string& trimstring(std::string& s, const char *ws)
{
    rtrimstring(s, ws);
    ltrimstring(s, ws);
    return s;
}

std::string& rtrimstring(std::string& s, const char *ws)
{
    std::string::size_type pos = s.find_last_not_of(ws);
    if (pos == std::string::npos) {
        s.clear();
    } else if (pos != s.length() - 1) {
        s.erase(pos + 1);
    }
    return s;
}

std::string& ltrimstring(std::string& s, const char *ws)
{
    std::string::size_type pos = s.find_first_not_of(ws);
    s.erase(0, pos);
    return s;
}

// Remove some chars and replace them with spaces
std::string neutchars(const std::string& str, const std::string& chars, char rep)
{
    std::string out;
    neutchars(str, out, chars, rep);
    return out;
}
void neutchars(const std::string& str, std::string& out, const std::string& chars, char rep)
{
    std::string::size_type startPos, pos;

    for (pos = 0;;) {
        // Skip initial chars, break if this eats all.
        if ((startPos = str.find_first_not_of(chars, pos)) == std::string::npos) {
            break;
        }
        // Find next delimiter or end of string (end of token)
        pos = str.find_first_of(chars, startPos);
        // Add token to the output. Note: token cant be empty here
        if (pos == std::string::npos) {
            out += str.substr(startPos);
        } else {
            out += str.substr(startPos, pos - startPos) + rep;
        }
    }
}


/* Truncate a string to a given maxlength, avoiding cutting off midword
 * if reasonably possible. Note: we could also use textsplit, stopping when
 * we have enough, this would be cleanly utf8-aware but would remove
 * punctuation */
static const std::string cstr_SEPAR = " \t\n\r-:.;,/[]{}";
std::string truncate_to_word(const std::string& input, std::string::size_type maxlen)
{
    std::string output;
    if (input.length() <= maxlen) {
        output = input;
    } else {
        output = input.substr(0, maxlen);
        std::string::size_type space = output.find_last_of(cstr_SEPAR);
        // Original version only truncated at space if space was found after
        // maxlen/2. But we HAVE to truncate at space, else we'd need to do
        // utf8 stuff to avoid truncating at multibyte char. In any case,
        // not finding space means that the text probably has no value.
        // Except probably for Asian languages, so we may want to fix this
        // one day
        if (space == std::string::npos) {
            output.erase();
        } else {
            output.erase(space);
        }
    }
    return output;
}

// Escape things that would look like markup
std::string escapeHtml(const std::string& in)
{
    std::string out;
    for (char pos : in) {
        switch(pos) {
        case '<': out += "&lt;"; break;
        case '>': out += "&gt;"; break;
        case '&': out += "&amp;"; break;
        case '"': out += "&quot;"; break;
        default: out += pos; break;
        }
    }
    return out;
}

std::string escapeShell(const std::string& in)
{
    std::string out;
    out += "\"";
    for (char pos : in) {
        switch (pos) {
        case '$':
            out += "\\$";
            break;
        case '`':
            out += "\\`";
            break;
        case '"':
            out += "\\\"";
            break;
        case '\n':
            out += "\\\n";
            break;
        case '\\':
            out += "\\\\";
            break;
        default:
            out += pos;
        }
    }
    out += "\"";
    return out;
}

// Escape value to be suitable as C++ source double-quoted string (for
// generating a c++ program
std::string makeCString(const std::string& in)
{
    std::string out;
    out += "\"";
    for (char pos : in) {
        switch (pos) {
        case '"':
            out += "\\\"";
            break;
        case '\n':
            out += "\\n";
            break;
        case '\r':
            out += "\\r";
            break;
        case '\\':
            out += "\\\\";
            break;
        default:
            out += pos;
        }
    }
    out += "\"";
    return out;
}

// Substitute printf-like percent cmds inside a string
bool pcSubst(const std::string& in, std::string& out, const std::map<char, std::string>& subs)
{
    std::string::const_iterator it;
    for (it = in.begin(); it != in.end(); it++) {
        if (*it == '%') {
            if (++it == in.end()) {
                out += '%';
                break;
            }
            if (*it == '%') {
                out += '%';
                continue;
            }
            auto tr = subs.find(*it);
            if (tr != subs.end()) {
                out += tr->second;
            } else {
                out += std::string("%") + *it;
            }
        } else {
            out += *it;
        }
    }
    return true;
}

bool pcSubst(const std::string& in, std::string& out,
             const std::function<std::string(const std::string&)>& mapper)
{
    out.erase();
    std::string::size_type i;
    for (i = 0; i < in.size(); i++) {
        if (in[i] == '%') {
            if (++i == in.size()) {
                out += '%';
                break;
            }
            if (in[i] == '%') {
                out += '%';
                continue;
            }
            std::string key;
            if (in[i] == '(') {
                if (++i == in.size()) {
                    out += std::string("%(");
                    break;
                }
                std::string::size_type j = in.find_first_of(')', i);
                if (j == std::string::npos) {
                    // ??concatenate remaining part and stop
                    out += in.substr(i - 2);
                    break;
                }
                key = in.substr(i, j - i);
                i = j;
            } else {
                key = in[i];
            }
            out += mapper(key);
        } else {
            out += in[i];
        }
    }
    return true;
}

class PcSubstMapMapper {
public:
    explicit PcSubstMapMapper(const std::map<std::string, std::string>& subs)
        : m_subs(subs) {}
    std::string domap(const std::string& key) {
        auto it = m_subs.find(key);
        if (it != m_subs.end())
            return it->second;
        return std::string("%") +(key.size() == 1 ? key : std::string("(") + key + std::string(")"));
    }
    const std::map<std::string, std::string>& m_subs;
};

bool pcSubst(const std::string& in, std::string& out,
             const std::map<std::string, std::string>& subs)
{
    PcSubstMapMapper mapper(subs);
    return pcSubst(in, out, std::bind(&PcSubstMapMapper::domap, &mapper, _1));
}

void ulltodecstr(uint64_t val, std::string& buf)
{
    buf.clear();
    if (val == 0) {
        buf = "0";
        return;
    }

    char rbuf[30];
    int idx=29;
    rbuf[idx--] = 0;
    do {
        rbuf[idx--] = '0' + val % 10;
        val /= 10;
    } while (val);

    buf.assign(&rbuf[idx+1]);
}

void lltodecstr(int64_t val, std::string& buf)
{
    buf.clear();
    if (val == 0) {
        buf = "0";
        return;
    }

    bool neg = val < 0;
    if (neg) {
        val = -val;
    }

    char rbuf[30];
    int idx=29;
    rbuf[idx--] = 0;
    do {
        rbuf[idx--] = '0' + val % 10;
        val /= 10;
    } while (val);
    if (neg) {
        rbuf[idx--] = '-';
    }
    buf.assign(&rbuf[idx+1]);
}

std::string lltodecstr(int64_t val)
{
    std::string buf;
    lltodecstr(val, buf);
    return buf;
}

std::string ulltodecstr(uint64_t val)
{
    std::string buf;
    ulltodecstr(val, buf);
    return buf;
}

// Convert byte count into unit (KB/MB...) appropriate for display
std::string displayableBytes(int64_t size)
{
    const char *unit;

    double roundable = 0;
    if (size < 1000) {
        unit = " B ";
        roundable = double(size);
    } else if (size < 1E6) {
        unit = " KB ";
        roundable = double(size) / 1E3;
    } else if (size < 1E9) {
        unit = " MB ";
        roundable = double(size) / 1E6;
    } else {
        unit = " GB ";
        roundable = double(size) / 1E9;
    }
    size = int64_t(std::round(roundable));
    return lltodecstr(size).append(unit);
}

std::string breakIntoLines(const std::string& in, unsigned int ll, unsigned int maxlines)
{
    std::string query = in;
    std::string oq;
    unsigned int nlines = 0;
    while (query.length() > 0) {
        std::string ss = query.substr(0, ll);
        if (ss.length() == ll) {
            std::string::size_type pos = ss.find_last_of(' ');
            if (pos == std::string::npos) {
                pos = query.find_first_of(' ');
                if (pos != std::string::npos) {
                    ss = query.substr(0, pos + 1);
                } else {
                    ss = query;
                }
            } else {
                ss = ss.substr(0, pos + 1);
            }
        }
        // This cant happen, but anyway. Be very sure to avoid an infinite loop
        if (ss.length() == 0) {
            oq = query;
            break;
        }
        oq += ss + "\n";
        if (nlines++ >= maxlines) {
            oq += " ... \n";
            break;
        }
        query = query.substr(ss.length());
    }
    return oq;
}

// Date is Y[-M[-D]]
static bool parsedate(std::vector<std::string>::const_iterator& it,
                      std::vector<std::string>::const_iterator end, DateInterval *dip)
{
    dip->y1 = dip->m1 = dip->d1 = dip->y2 = dip->m2 = dip->d2 = 0;
    if (it->length() > 4 || !it->length() ||
        it->find_first_not_of("0123456789") != std::string::npos) {
        return false;
    }
    if (it == end || sscanf(it++->c_str(), "%d", &dip->y1) != 1) {
        return false;
    }
    if (it == end || *it == "/") {
        return true;
    }
    if (*it++ != "-") {
        return false;
    }

    if (it->length() > 2 || !it->length() ||
        it->find_first_not_of("0123456789") != std::string::npos) {
        return false;
    }
    if (it == end || sscanf(it++->c_str(), "%d", &dip->m1) != 1) {
        return false;
    }
    if (it == end || *it == "/") {
        return true;
    }
    if (*it++ != "-") {
        return false;
    }

    if (it->length() > 2 || !it->length() ||
        it->find_first_not_of("0123456789") != std::string::npos) {
        return false;
    }
    if (it == end || sscanf(it++->c_str(), "%d", &dip->d1) != 1) {
        return false;
    }

    return true;
}

// Called with the 'P' already processed. Period ends at end of string
// or at '/'. We dont' do a lot effort at validation and will happily
// accept 10Y1Y4Y (the last wins)
static bool parseperiod(std::vector<std::string>::const_iterator& it,
                        std::vector<std::string>::const_iterator end, DateInterval *dip)
{
    dip->y1 = dip->m1 = dip->d1 = dip->y2 = dip->m2 = dip->d2 = 0;
    while (it != end) {
        int value;
        if (it->find_first_not_of("0123456789") != std::string::npos) {
            return false;
        }
        if (sscanf(it++->c_str(), "%d", &value) != 1) {
            return false;
        }
        if (it == end || it->empty()) {
            return false;
        }
        switch (it->at(0)) {
        case 'Y':
        case 'y':
            dip->y1 = value;
            break;
        case 'M':
        case 'm':
            dip->m1 = value;
            break;
        case 'D':
        case 'd':
            dip->d1 = value;
            break;
        default:
            return false;
        }
        it++;
        if (it == end) {
            return true;
        }
        if (*it == "/") {
            return true;
        }
    }
    return true;
}

#ifdef _WIN32
static int setenv(const char* name, const char* value, int overwrite)
{
    if (!overwrite) {
        const char *cp = getenv(name);
        if (cp) {
            return -1;
        }
    }
    return _putenv_s(name, value);
}
static void unsetenv(const char* name)
{
    _putenv_s(name, "");
}
#endif

time_t portable_timegm(struct tm *tm)
{
    time_t ret;
    char *tz;

    tz = getenv("TZ");
    setenv("TZ", "", 1);
    tzset();
    ret = mktime(tm);
    if (tz) {
        setenv("TZ", tz, 1);
    } else {
        unsetenv("TZ");
    }
    tzset();
    return ret;
}

#if 0
static void cerrdip(const std::string& s, DateInterval *dip)
{
    cerr << s << dip->y1 << "-" << dip->m1 << "-" << dip->d1 << "/"
         << dip->y2 << "-" << dip->m2 << "-" << dip->d2
         << endl;
}
#endif

// Compute date + period. Won't work out of the unix era.
// or pre-1970 dates. Just convert everything to unixtime and
// seconds (with average durations for months/years), add and convert
// back
static bool addperiod(DateInterval *dp, DateInterval *pp)
{
    // Create a struct tm with possibly non normalized fields and let
    // timegm sort it out
    struct tm tm = {};
    tm.tm_year = dp->y1 - 1900 + pp->y1;
    tm.tm_mon = dp->m1 + pp->m1 - 1;
    tm.tm_mday = dp->d1 + pp->d1;
    time_t tres = mktime(&tm);
    localtime_r(&tres, &tm);
    dp->y1 = tm.tm_year + 1900;
    dp->m1 = tm.tm_mon + 1;
    dp->d1 = tm.tm_mday;
    //cerrdip("Addperiod return", dp);
    return true;
}
int monthdays(int mon, int year)
{
    switch (mon) {
        // We are returning a few too many 29 days februaries, no problem
    case 2:
        return (year % 4) == 0 ? 29 : 28;
    case 1:
    case 3:
    case 5:
    case 7:
    case 8:
    case 10:
    case 12:
        return 31;
    default:
        return 30;
    }
}
bool parsedateinterval(const std::string& s, DateInterval *dip)
{
    std::vector<std::string> vs;
    dip->y1 = dip->m1 = dip->d1 = dip->y2 = dip->m2 = dip->d2 = 0;
    DateInterval p1, p2, d1, d2;
    p1 = p2 = d1 = d2 = *dip;
    bool hasp1 = false, hasp2 = false, hasd1 = false, hasd2 = false,
        hasslash = false;

    if (!stringToStrings(s, vs, "PYMDpymd-/")) {
        return false;
    }
    if (vs.empty()) {
        return false;
    }

    auto it = vs.cbegin();
    if (*it == "P" || *it == "p") {
        it++;
        if (!parseperiod(it, vs.end(), &p1)) {
            return false;
        }
        hasp1 = true;
        //cerrdip("p1", &p1);
        p1.y1 = -p1.y1;
        p1.m1 = -p1.m1;
        p1.d1 = -p1.d1;
    } else if (*it == "/") {
        hasslash = true;
        goto secondelt;
    } else {
        if (!parsedate(it, vs.end(), &d1)) {
            return false;
        }
        hasd1 = true;
    }

    // Got one element and/or /
secondelt:
    if (it != vs.end()) {
        if (*it != "/") {
            return false;
        }
        hasslash = true;
        it++;
        if (it == vs.end()) {
            // ok
        } else if (*it == "P" || *it == "p") {
            it++;
            if (!parseperiod(it, vs.end(), &p2)) {
                return false;
            }
            hasp2 = true;
        } else {
            if (!parsedate(it, vs.end(), &d2)) {
                return false;
            }
            hasd2 = true;
        }
    }

    // 2 periods dont' make sense
    if (hasp1 && hasp2) {
        return false;
    }
    // Nothing at all doesn't either
    if (!hasp1 && !hasd1 && !hasp2 && !hasd2) {
        return false;
    }

    // Empty part means today IF other part is period, else means
    // forever (stays at 0)
    time_t now = time(nullptr);
    struct tm *tmnow = gmtime(&now);
    if ((!hasp1 && !hasd1) && hasp2) {
        d1.y1 = 1900 + tmnow->tm_year;
        d1.m1 = tmnow->tm_mon + 1;
        d1.d1 = tmnow->tm_mday;
        hasd1 = true;
    } else if ((!hasp2 && !hasd2) && hasp1) {
        d2.y1 = 1900 + tmnow->tm_year;
        d2.m1 = tmnow->tm_mon + 1;
        d2.d1 = tmnow->tm_mday;
        hasd2 = true;
    }

    // Incomplete dates have different meanings depending if there is
    // a period or not (actual or infinite indicated by a / + empty)
    //
    // If there is no explicit period, an incomplete date indicates a
    // period of the size of the uncompleted elements. Ex: 1999
    // actually means 1999/P12M
    //
    // If there is a period, the incomplete date should be extended
    // to the beginning or end of the unspecified portion. Ex: 1999/
    // means 1999-01-01/ and /1999 means /1999-12-31
    if (hasd1) {
        if (!(hasslash || hasp2)) {
            if (d1.m1 == 0) {
                p2.m1 = 12;
                d1.m1 = 1;
                d1.d1 = 1;
            } else if (d1.d1 == 0) {
                d1.d1 = 1;
                p2.d1 = monthdays(d1.m1, d1.y1);
            }
            hasp2 = true;
        } else {
            if (d1.m1 == 0) {
                d1.m1 = 1;
                d1.d1 = 1;
            } else if (d1.d1 == 0) {
                d1.d1 = 1;
            }
        }
    }
    // if hasd2 is true we had a /
    if (hasd2) {
        if (d2.m1 == 0) {
            d2.m1 = 12;
            d2.d1 = 31;
        } else if (d2.d1 == 0) {
            d2.d1 = monthdays(d2.m1, d2.y1);
        }
    }
    if (hasp1) {
        // Compute d1
        d1 = d2;
        if (!addperiod(&d1, &p1)) {
            return false;
        }
    } else if (hasp2) {
        // Compute d2
        d2 = d1;
        if (!addperiod(&d2, &p2)) {
            return false;
        }
    }

    dip->y1 = d1.y1;
    dip->m1 = d1.m1;
    dip->d1 = d1.d1;
    dip->y2 = d2.y1;
    dip->m2 = d2.m1;
    dip->d2 = d2.d1;
    return true;
}

std::string hexprint(const std::string& in, char separ)
{
    std::string out;
    out.reserve(separ ? (3 *in.size()) : (2 * in.size()));
    static const char hex[]="0123456789abcdef";
    auto cp = reinterpret_cast<const unsigned char*>(in.c_str());
    for (unsigned int i = 0; i < in.size(); i++) {
        out.append(1, hex[cp[i] >> 4]);
        out.append(1, hex[cp[i] & 0x0f]);
        if (separ && i != in.size() - 1)
            out.append(1, separ);
    }
    return out;
}

[[maybe_unused]] static char* _check_strerror_r(int, char* errbuf)
{
    return errbuf;
}
[[maybe_unused]] static char* _check_strerror_r(char* cp, char*)
{
    return cp;
}

void catstrerror(std::string *reason, const char *what, int _errno)
{
    if (!reason) {
        return;
    }
    if (what) {
        reason->append(what);
    }

    reason->append(": errno: ");

    char nbuf[20];
    sprintf(nbuf, "%d", _errno);
    reason->append(nbuf);

    reason->append(" : ");

#if defined(sun) || defined(_WIN32)
    // Note: sun strerror is noted mt-safe ??
    reason->append(strerror(_errno));
#else
    // There are 2 versions of strerror_r.
    // - The GNU one returns a pointer to the message (maybe
    //   static storage or supplied buffer).
    // - The POSIX one always stores in supplied buffer and
    //   returns 0 on success. As the possibility of error and
    //   error code are not specified, we're basically doomed
    //   cause we can't use a test on the 0 value to know if we
    //   were returned a pointer...
    // Also couldn't find an easy way to disable the gnu version without
    // changing the cxxflags globally, so forget it. Recent gnu lib versions
    // normally default to the posix version. (not !)
    // The feature defines tests are too complicated and seem unreliable.
    // In short it's a mess, but thanks to c++ function overloading and smart 
    // people, we have a solution:
    // https://www.zverovich.net/2015/03/13/reliable-detection-of-strerror-variants.html
    char errbuf[200];
    errbuf[0] = 0;
    reason->append(_check_strerror_r(
                       strerror_r(_errno, errbuf, sizeof(errbuf)), errbuf));
#endif
}

#ifndef SMALLUT_NO_REGEX
#ifdef USE_STD_REGEX

class SimpleRegexp::Internal {
public:
    Internal(const std::string& exp, int flags, int nm)
        : expr(exp,
               std::basic_regex<char>::flag_type(
                   std::regex_constants::extended |
                   ((flags&SRE_ICASE) ? int(std::regex_constants::icase) : 0) |
                   ((flags&SRE_NOSUB) ? int(std::regex_constants::nosubs) : 0)
                   )), ok(true), nmatch(nm) {
    }
    std::regex expr;
    std::smatch res;
    bool ok;
    int nmatch;
};

bool SimpleRegexp::simpleMatch(const std::string& val) const
{
    if (!ok())
        return false;
    return regex_search(val, m->res, m->expr);
}

// Substitute one instance of regular expression
std::string SimpleRegexp::simpleSub(
    const std::string& in, const std::string& repl)
{
    if (!ok()) {
        return std::string();
    }
    return regex_replace(in, m->expr, repl, std::regex_constants::format_first_only);
}

std::string SimpleRegexp::getMatch(const std::string&, int i) const
{
    return m->res.str(i);
}

#else // -> !WIN32

class SimpleRegexp::Internal {
public:
    Internal(const std::string& exp, int flags, int nm) : nmatch(nm) {
        ok = regcomp(&expr, exp.c_str(), REG_EXTENDED |

                     ((flags & SRE_ICASE) ? REG_ICASE : 0) |

                     ((flags & SRE_NOSUB) ? REG_NOSUB : 0)) == 0;
        matches.resize(nmatch+1);
    }
    ~Internal() {
        regfree(&expr);
    }
    bool ok;
    regex_t expr;
    int nmatch;
    std::vector<regmatch_t> matches;
};

// Substitute one instance of regular expression
std::string SimpleRegexp::simpleSub(
    const std::string& in, const std::string& repl)
{
    if (!ok()) {
        return {};
    }

    int err;
    if ((err = regexec(&m->expr, in.c_str(),
                       m->nmatch + 1, &m->matches[0], 0))) {
#if SIMPLESUB_DBG
        const int ERRSIZE = 200;
        char errbuf[ERRSIZE + 1];
        regerror(err, &expr, errbuf, ERRSIZE);
        std::cerr << "simpleSub: regexec(" << sexp << ") failed: "
                  <<  errbuf << "\n";
#endif
        return in;
    }
    if (m->matches[0].rm_so == -1) {
        // No match
        return in;
    }
    std::string out = in.substr(0, m->matches[0].rm_so);
    out += repl;
    out += in.substr(m->matches[0].rm_eo);
    return out;
}

bool SimpleRegexp::simpleMatch(const std::string& val) const
{
    if (!ok())
        return false;
    return regexec(&m->expr, val.c_str(), m->nmatch + 1, &m->matches[0], 0) == 0;
}

std::string SimpleRegexp::getMatch(const std::string& val, int i) const
{
    if (i > m->nmatch) {
        return {};
    }
    return val.substr(m->matches[i].rm_so,
                      m->matches[i].rm_eo - m->matches[i].rm_so);
}

#endif // !windows, using C regexps

SimpleRegexp::SimpleRegexp(const std::string& exp, int flags, int nmatch)
    : m(std::make_unique<Internal>(exp, flags, nmatch))
{
}

SimpleRegexp::~SimpleRegexp() = default;

bool SimpleRegexp::ok() const
{
    return m->ok;
}

bool SimpleRegexp::operator() (const std::string& val) const
{
    return simpleMatch(val);
}
#endif // SMALLUT_NO_REGEX

std::string flagsToString(const std::vector<CharFlags>& flags, unsigned int val)
{
    const char *s;
    std::string out;
    for (const auto& flag : flags) {
        if ((val & flag.value) == flag.value) {
            s = flag.yesname;
        } else {
            s = flag.noname;
        }
        if (s && *s) {
            /* We have something to write */
            if (out.length()) {
                // If not first, add '|' separator
                out.append("|");
            }
            out.append(s);
        }
    }
    return out;
}

std::string valToString(const std::vector<CharFlags>& flags, unsigned int val)
{
    std::string out;
    for (const auto& flag : flags) {
        if (flag.value == val) {
            out = flag.yesname;
            return out;
        }
    }
    {
        char mybuf[100];
        sprintf(mybuf, "Unknown Value 0x%x", val);
        out = mybuf;
    }
    return out;
}

// Decode %-encoded URL. No encoding method is defined here because the problem is too complex and
// ambiguous (at least 3 RFCs + comments). Decoding however is unambiguous.
static inline int h2d(int c) {
    if ('0' <= c && c <= '9')
        return c - '0';
    else if ('A' <= c && c <= 'F')
        return 10 + c - 'A';
    else if ('a' <= c && c <= 'f')
        return 10 + c - 'a';
    else 
        return -1;
}



std::string url_decode(const std::string &in)
{
    if (in.size() <= 2)
        return in;
    std::string out;
    out.reserve(in.size());
    const char *cp = in.c_str();
    std::string::size_type i = 0;
    for (; i < in.size() - 2; i++) {
        if (cp[i] == '%') {
            int d1 = h2d(cp[i+1]);
            int d2 = h2d(cp[i+2]);
            if (d1 != -1 && d2 != -1) {
                out += (d1 << 4) + d2;
            } else {
                out += '%';
                out += cp[i+1];
                out += cp[i+2];
            }
            i += 2;
        } else {
            out += cp[i];
        }
    }
    while (i < in.size()) {
        out += cp[i++];
    }
    return out;
}

bool parseHTTPRanges(const std::string& ranges, std::vector<std::pair<int64_t, int64_t>>& oranges)
{
    oranges.clear();
    std::string::size_type pos = ranges.find("bytes=");
    if (pos == std::string::npos) {
        return false;
    }
    pos += 6;
    bool done = false;
    while(!done) {
        std::string::size_type dash = ranges.find('-', pos);
        if (dash == std::string::npos) {
            return false;
        }
        std::string::size_type comma = ranges.find(',', pos);
        std::string firstPart = ranges.substr(pos, dash-pos);
        trimstring(firstPart);
        int64_t start = firstPart.empty() ? -1 : atoll(firstPart.c_str());
        std::string secondPart = ranges.substr(
            dash+1, comma != std::string::npos ?
            comma-dash-1 : std::string::npos);
        trimstring(secondPart);
        int64_t fin = secondPart.empty() ? -1 : atoll(secondPart.c_str());
        if (start == -1 && fin == -1) {
            return false;
        }
        std::pair<int64_t, int64_t> nrange(start,fin);
        oranges.push_back(nrange);
        if (comma != std::string::npos) {
            pos = comma + 1;
        }
        done = comma == std::string::npos;
    }
    return true;
}

// Initialization for static stuff to be called from main thread before going
// multiple
void smallut_init_mt()
{
}

} // End namespace MedocUtils
