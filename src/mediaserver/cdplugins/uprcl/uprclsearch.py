# Copyright (C) 2017 J.F.Dockes
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import print_function

import sys

import re
from recoll import recoll

from upmplgutils import uplog
from conftree import stringToStrings
import uprclutils

def _getchar(s, i):
    if i < len(s):
        return i+1,s[i]
    else:
        return i,None

def _readword(s, i):
    w = ''
    for j in range(i, len(s)):
        if s[j].isspace():
            return j,w
        w += s[j]
    return j,w

# Called with '"' already read.
# Upnp search term strings are double quoted, but we should not take
# them as recoll phrases. We separate parts which are internally
# quoted, and become phrases, and lists of words which we interpret as
# an AND search (comma-separated). Internal quotes come backslash-escaped
def _parsestring(s, i=0):
    #uplog("parseString: input: <%s>" % s[i:])
    # First change '''"hello \"one phrase\"''' world" into
    #  '''hello "one phrase" world'''
    # Note that we can't handle quoted dquotes inside string
    str = ''
    escape = False
    instring = False
    for j in range(i, len(s)):
        if instring:
            if escape:
                if s[j] == '"':
                    str += '"'
                    instring = False
                else:
                    str += '\\' + s[j]
                escape = False
            else:
                if s[j] == '\\':
                    escape = True
                else:
                    str += s[j]

        else:
            if escape:
                str += s[j]
                escape = False
                if s[j] == '"':
                    instring = True
            else:
                if s[j] == '\\':
                    escape = True
                elif s[j] == '"':
                    j += 2
                    break
                else:
                    str += s[j]
                
    tokens = stringToStrings(str)
    return j, tokens


def _searchClauses(out, field, oper, words, phrases):
    if words:
        out.append(field)
        out.append(oper)
        out.append(words)
    for ph in phrases:
        out.append(field)
        out.append(oper)
        out.append('"' + ph + '"')
    return out


def _separatePhrasesAndWords(v):
    swords = ""
    phrases = []
    for w in v:
        if len(w.split()) == 1:
            if swords:
                swords += ","
            swords += w
        else:
            phrases.append(w)
    return (swords, phrases)

# the v list contains terms and phrases. Fields maybe several space
# separated field specs, which we should OR (ex: for search title or
# filename).
def _makeSearchExp(out, v, field, oper, neg):
    uplog("_makeSearchExp: v <%s> field <%s> oper <%s> neg <%s>" %
          (v, field, oper, neg))

    if oper == 'I':
        return

    swords,phrases = _separatePhrasesAndWords(v)

    if neg:
        out.append(" -")

    # Special-case 'title' because we want to also match directory names
    # ((title:keyword) OR (filename:keyword AND mime:inode/directory))
    if field == 'title':
        fields = (field, 'filename')
    else:
        fields = (field,)
        
    if len(fields) > 1:
        out.append(" (")

    for i in range(len(fields)):
        field = fields[i]
        out.append(" (")
        _searchClauses(out, field, oper, swords, phrases)
        # We'd like to do the following to avoid matching reg file names but
        # recoll takes all mime: clause as global filters, so can't work
        # if i == 1: out.append(" AND mime:inode/directory")
        out.append(")")
        if len(fields) == 2 and i == 0:
            out.append(" OR ")

    if len(fields) > 1:
        out.append(") ")
        

def _upnpsearchtorecoll(s):
    uplog("_upnpsearchtorecoll:in: <%s>" % s)

    s = re.sub('[\t\n\r\f ]+', ' ', s)

    out = []
    field = ""
    oper = ""
    neg = False
    i = 0
    while True:
        i,c = _getchar(s, i)
        if not c:
            break
        #uplog("_upnpsearchtorecoll: nextchar: <%s>" % c)

        if c.isspace():
            continue

        if c == "*":
            if (len(out) > 1 or (len(out) == 1 and not out[-1].isspace())) or \
                   (len(s[i:]) and not s[i:].isspace()):
                raise Exception("If * is used it must be the only input")
            out = ["mime:*"]
            break

        if c == '(' or c == ')': 
            out.append(c)
        elif c == '>' or c == '<' or c == '=':
            oper += c
        else:
            if c == '"':
                i,v = _parsestring(s, i)
                _makeSearchExp(out, v, field, oper, neg)
                field = ""
                oper = ""
                neg = False
                continue
            else:
                i -= 1
                i,w = _readword(s, i)
                #uplog("_readword returned <%s>" % w)

            if w == 'contains':
                oper = ':'
            elif w == 'doesNotContain':
                neg = True
                oper = ':'
            elif w == 'derivedFrom' or w == 'exists':
                # upnp:class derivedfrom "object.container.album"
                # exists??
                # can't use this, will be ignored
                oper = 'I'
            elif w == 'true' or w == 'false':
                # Don't know what to do with this. Just ignore it,
                # by not calling makeSearchExp.
                pass
            elif w == 'and':
                # Recoll has implied AND, but see next
                pass
            elif w == 'or':
                # Does not work because OR/AND priorities are reversed
                # between recoll and upnp. This would be very
                # difficult to correct, let's hope that the callers
                # use parentheses
                out.append('OR')
            else:
                try:
                    field = uprclutils.upnp2rclfields[w]
                except Exception as ex:
                    #uplog("Field translation error: %s"%ex)
                    field = (w,)

    return " ".join(out)


def search(foldersobj, rclconfdir, objid, upnps, idprefix, httphp, pathprefix):
    rcls = _upnpsearchtorecoll(upnps)

    filterdir = foldersobj.dirpath(objid)
    if filterdir and filterdir != "/":
        rcls += " dir:\"" + filterdir + "\""
    
    uplog("Search: recoll search: <%s>" % rcls)

    rcldb = recoll.connect(confdir=rclconfdir)
    try:
        rclq = rcldb.query()
        rclq.execute(rcls)
    except Exception as e:
        uplog("Search: recoll query raised: %s" % e)
        return []
    
    uplog("Estimated query results: %d" % (rclq.rowcount))
    if rclq.rowcount == 0:
        return []
    
    entries = []
    maxcnt = 0
    while True:
        docs = rclq.fetchmany()
        for doc in docs:
            id = foldersobj.objidfordoc(doc)
            e = uprclutils.rcldoctoentry(id, objid, httphp, pathprefix, doc)
            if e:
                entries.append(e)
        if (maxcnt > 0 and len(entries) >= maxcnt) or \
               len(docs) != rclq.arraysize:
            break
    uplog("Search retrieved %d docs" % (len(entries),))

    entries.sort(key=uprclutils.cmpentries)
    return entries

if __name__ == '__main__':
    s = '(upnp:artist derivedFrom  "abc\\"def\\g") or (dc:title:xxx) '
    print("INPUT: %s" % s)
    o = upnpsearchtorecoll(s)
    print("OUTPUT: %s" % o)
