/* Copyright (C) 2013 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#ifndef _IXMLWRAP_H_INCLUDED_
#define _IXMLWRAP_H_INCLUDED_

#include <upnp/ixml.h>                  // for IXML_Document

#include <string>                       // for string

namespace UPnPP {

#if notUsedAnyMore
    /** Retrieve the text content for the first element of given name.
     * Returns an empty string if the element does not contain a text node */
    std::string getFirstElementValue(IXML_Document *doc, 
                                     const std::string& name); *
#endif

    /** Return the result of ixmlPrintDocument as a string and take
     * care of freeing the memory. This is inefficient of course (one
     * more alloc+copy), and destined to debug statements */
    std::string ixmlwPrintDoc(IXML_Document*);

}

#endif /* _IXMLWRAP_H_INCLUDED_ */
