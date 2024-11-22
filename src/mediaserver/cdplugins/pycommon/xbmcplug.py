# Copyright (C) 2016-2021 J.F.Dockes
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the
#   Free Software Foundation, Inc.,
#   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
#

"""Shared code for the plugins which reuse the routing module from the Tidal Kodi plugin."""

import re
import posixpath

from upmplgutils import uplog
import upmplgutils


# Semi-bogus class instanciated as global object for helping with reusing kodi addon code
class XbmcPlugin:
    def __init__(self, idprefix, pid, offset=0, count=0, routeplugin=None):
        self.idprefix = idprefix
        upmplgutils.setidprefix(idprefix)
        self.routeplug = routeplugin
        self.objid = pid
        self.offset = offset
        self.count = count

        self.entries = []
        self.total = 0

    # item_num is the number to be prepended to the title, if different from None
    # this is for the benefit of kodi which always sort entries by name
    def add_directory(self, title, endpoint, arturi=None, item_num=None):
        if callable(endpoint):
            endpoint = self.routeplug.url_for(endpoint)
        if item_num:
            title = f"[{item_num:02}] {title}"
        e = upmplgutils.direntry(
            self.idprefix + endpoint, self.objid, title, arturi=arturi
        )
        self.entries.append(e)

    def urls_from_id(self, view_func, items):
        if not items:
            return []
        uplog("urls_from_id: items: %s" % str([item.id for item in items]), level=5)
        return [
            self.routeplug.url_for(view_func, item.id)
            for item in items
            if str(item.id).find("http") != 0
        ]

    # initial_item_num is the start number to be prepended to the title, if
    # different from None
    # This is for the benefit of kodi which always sort entries by name
    def view(self, data_items, urls, end=True, initial_item_num=None):
        if not data_items or not urls:
            return
        for item, url in zip(data_items, urls):
            title = item.name
            try:
                image = item.image if item.image else None
            except:
                image = None
            try:
                upnpclass = item.upnpclass if item.upnpclass else None
            except:
                upnpclass = None
            try:
                artnm = item.artist.name if item.artist.name else None
            except:
                artnm = None
            try:
                description = item.description if item.description else None
            except:
                description = None

            if initial_item_num:
                title = f"[{initial_item_num:02}] {title}"
                initial_item_num += 1
            self.entries.append(
                upmplgutils.direntry(
                    self.idprefix + url,
                    self.objid,
                    title,
                    arturi=image,
                    artist=artnm,
                    upnpclass=upnpclass,
                    description=description,
                )
            )
