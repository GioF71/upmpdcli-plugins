/* Copyright (C) 2024 J.F.Dockes
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

#ifndef _XMLTOCONFGUI_H_INCLUDED_
#define _XMLTOCONFGUI_H_INCLUDED_

#include "confgui.h"

/**
 * Interpret an XML string and create a configuration interface. XML sample:
 *
 * <confcomments>
 *   <filetitle>Configuration file parameters for upmpdcli</filetitle>
 *   <grouptitle>MPD parameters</grouptitle>
 *   <var name="mpdhost" type="string">
 *     <brief>Host MPD runs on.</brief>
 *     <descr>Defaults to localhost. This can also be specified as -h</descr>
 *   </var>
 *   mpdhost = default-host
 *   <var name="mpdport" type="int" values="0 65635 6600">
 *     <brief>IP port used by MPD</brief>. 
 *     <descr>Can also be specified as -p port. Defaults to the...</descr>
 *   </var>
 *   mpdport = defport
 *   <var name="ownqueue" type="bool" values="1">
 *     <brief>Set if we own the MPD queue.</brief>
 *     <descr>If this is set (on by default), we own the MPD...</descr>
 *   </var>
 *   ownqueue = 
 * </confcomments>
 *
 * <grouptitle> creates a panel in which the following <var> are set.
 * The <var> attributes should be self-explanatory. "values"
 * is used for different things depending on the var type
 * (min/max, default, str list). Check the code about this. 
 * type values: "bool" "int" "string" "cstr" "cstrl" "fn" "dfn" "strl" "dnl"
 *
 * The XML would typically be the result of a ConfSimple::commentsAsXML() call on a properly
 * formatted reference configuration.
 *
 * This allows the reference configuration file to generate both the documentation and the GUI.
 * 
 * @param xml the input xml
 * @param[output] toptxt the extracted top level XML text (text not inside <var>),
 *   usually mostly commented variable assignments, but also includes uncommented conftree lines
 *   like section definitions and actual assignments (which would usually be used to override the
 *   compiled in defaults documented by the comment). This should be evaluated as a config for
 *   default values.
 * @lnkf factory to create the objects which link the GUI to the storage mechanism.
 */
namespace confgui {
extern ConfTabsW *xmlToConfGUI(
    const std::string& xml, std::string& toptxt, ConfLinkFact* lnkf, QWidget *parent);

} // namespace confgui

#endif /* _XMLTOCONFGUI_H_INCLUDED_ */
