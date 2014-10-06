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
#include "config.h"

#include "log.hxx"

#include <errno.h>                      // for errno

#include <fstream>                      // for operator<<, basic_ostream, etc

using namespace std;

namespace UPnPP {

Logger::Logger(const std::string& fn) 
    : m_tocerr(false), m_loglevel(LLDEB)
{
    if (!fn.empty() && fn.compare("stderr")) {
        m_stream.open(fn, std::fstream::out | std::ofstream::trunc);
        if (!m_stream.is_open()) {
            cerr << "Logger::Logger: log open failed: for [" <<
                fn << "] errno " << errno << endl;
            m_tocerr = true;
        }
    } else {
        m_tocerr = true;
    }
}

static Logger *theLog;

Logger *Logger::getTheLog(const string& fn)
{
    if (theLog == 0)
        theLog = new Logger(fn);
    return theLog;
}

}
