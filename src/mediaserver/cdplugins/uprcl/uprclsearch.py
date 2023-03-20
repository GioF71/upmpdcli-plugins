# Copyright (C) 2017-2023 J.F.Dockes
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

'''Translate an UPnP search string into a Recoll one and run the search. Note that the translation 
is not exact, we are just making a best effort.'''

import sys
import re

from recoll import recoll

from upmplgutils import uplog
from conftree import stringToStrings
import uprclutils
import uprclinit

def _getchar(s, i):
    if i < len(s):
        return i+1,s[i]
    else:
        return i,None


def _readword(s, i):
    '''Extract word from whole string s starting at offset i. Return final position and word.
    The final position will point to whitespace or EOS'''
    #uplog(f"_readword: input: <{s[i:]}>")
    w = ''
    for j in range(i, len(s)):
        if s[j].isspace():
            break
        w += s[j]
    # If we broke at the end of string, increment to indicate eos
    if j == len(s) -1:
        j += 1
    #uplog(f"_readword returning index {j} word <{w}>")
    return j,w


def _parsestring(s, i=0):
    '''Parse double-quoted string looking like ["hello \"one phrase\" world"]
    Called with the first quote already read.
    Upnp search term strings are double quoted, but we should not take them as recoll phrases. 
    We separate parts which are internally (backslash-escaped) quoted, and become phrases, and 
    lists of words which we interpret as an AND search (comma-separated).
    Note that we don't handle possible quotes inside an escape-quoted phrase string.'''

    #uplog(f"parseString: input: <{s[i:]}>")
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
        else: # Not inside internal string
            if escape:
                str += s[j]
                escape = False
                if s[j] == '"':
                    instring = True
            else:
                if s[j] == '\\':
                    escape = True
                elif s[j] == '"':
                    j += 1
                    break
                else:
                    str += s[j]
                
    tokens = stringToStrings(str)
    #uplog(f"parseString: return: j {j} tokens {tokens}")
    return j, tokens


def _separatePhrasesAndWords(v):
    '''Built separate lists for phrases and words from parseString output'''
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


def _searchClauses(out, neg, field, oper, words, phrases):
    '''Build recoll search clauses out of list of words and phrases and given negation, field name 
    and operator, e.g. [title:word, title:"some phrase"] '''
    if words:
        if neg:
            out.append("-")
        out.append(field)
        out.append(oper)
        out.append(words)
    for ph in phrases:
        if neg:
            out.append("-")
        out.append(field)
        out.append(oper)
        out.append('"' + ph + '"')
    return out


def _makeSearchExp(out, v, field, oper, neg):
    '''Process data from an UPnP relExp triplet.
    Build a recoll search expression, given:
    v: terms or phrases out of _parseString.
    field: which we may expand to multiple ORed values (e.g. title -> title or filename)
    oper: :, = etc. "I" for ignore.
    neg: exclusion'''

    #uplog(f"_makeSearchExp: v <{v}> field <{field}> oper <{oper}> neg <{neg}>")

    if oper == "I":
        return

    # Test coming from, e.g. <upnp:class derivedfrom/= object.container.album>
    if (oper == ':' or oper == '=') and len(v) == 1:
        if v[0].startswith("object.container"):
            v = ['inode/directory',]
        elif v[0].startswith("object.item"):
            neg = True
            v = ['inode/directory',]
            
    swords,phrases = _separatePhrasesAndWords(v)

    # Special-case 'title' because we want to also match the file name. Possibly only for
    # directories, but there is no way to do inside a single query (see comment further).
    if field == 'title':
        fields = (field, 'filename')
    else:
        fields = (field,)
        
    if len(fields) > 1:
        out.append(" (")

    for i in range(len(fields)):
        field = fields[i]
        out.append(" (")
        _searchClauses(out, neg, field, oper, swords, phrases)
        # We'd like to do the following to avoid matching regular file names (maybe: what of the
        # untagged files?) but recoll takes all mime: clause as global filters, so can't work
        # anyway:
        #if i == 1: out.append(" AND mime:inode/directory")
        out.append(")")
        if len(fields) == 2 and i == 0:
            if neg:
                out.append(" AND ")
            else:
                out.append(" OR ")

    if len(fields) > 1:
        out.append(") ")

# Some fields are found in searches but not in the upnp2rclfield dict, which would lead to a search
# failure
_fieldaliases = {
    "dc:creator": "upnp:artist",
}

# Upnp searches are made of relExps which are always (selector, operator, value), there are no unary
# operators. The relExp-s can be joined with and/or and grouped with parentheses, but they are
# always triplets, which make things reasonably easy to translate into a recoll search, just
# translating the relExps into field clauses and forwarding the booleans and parentheses.
#
# Also the set of unquoted keywords or operators is unambiguous and all un-reserved values are
# quoted, so that we don't even use a state machine, but rely of comparing token values for
# determining our syntactic state.
#
# This is all quite approximative though, but simpler than a formal parser, and mostly works in
# practise because we rely on recoll to deal with logical operators and parentheses.
def _upnpsearchtorecoll(s):
    uplog(f"_upnpsearchtorecoll:in: <{s}>")

    # Simplify: turn all whitespace sequences into single spaces
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
        #uplog(f"_upnpsearchtorecoll: nextchar: <{c}>")

        if c.isspace():
            continue

        if c == "*":
            if (len(out) > 1 or (len(out) == 1 and not out[-1].isspace())) or \
                   (len(s[i:]) and not s[i:].isspace()):
                raise Exception("If * is used it must be the only input")
            out = ["mime:*"]
            break

        if c == '(' or c == ')':
            #uplog(f"Appending <{c}>")
            out.append(c)
        elif c == '>' or c == '<' or c == '=':
            oper += c
        else:
            if c == '"':
                # Quoted strings are always values (3rd triplet elements) and values are always
                # quoted. Read it, then generate and append one or several recoll search clauses,
                # according to the already read 1st and 2nd triplet elements.
                i,v = _parsestring(s, i)
                _makeSearchExp(out, v, field, oper, neg)
                field = ""
                oper = ""
                neg = False
                continue

            # Unquoted word.
            i -= 1
            i,w = _readword(s, i)

            w = w.lower()
            if w == 'contains':
                oper = ':'
            elif w == 'doesnotcontain':
                neg = True
                oper = ':'
            elif w == 'derivedfrom':
                oper = ':'
            elif w == 'exists':
                # somefield exists true
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
                # Does not work because OR/AND priorities are reversed between recoll and upnp. This
                # would be very difficult to correct, let's hope that the callers use parentheses
                out.append('OR')
            else:
                if w == 'upnp:class':
                    field = 'mime'
                else:
                    try:
                        if w in _fieldaliases:
                            w = _fieldaliases[w]
                        field = uprclutils.upnp2rclfields[w]
                    except Exception as ex:
                        uplog(f"Field translation error for <{w}>: {ex}. Ignoring search.")
                        # Recoll would just ignore an unknown field spec and search the main
                        # text. We don't want to do this, it yields confusing results (happens for
                        # example with someting like: upnp:artist[@role="composer"] from kazoo
                        return None

    return " ".join(out)


def search(foldersobj, rclconfdir, inobjid, upnps, idprefix, httphp, pathprefix):
    '''Run UPnP search operation. inobjid is for the container this search is run from.'''

    tags = uprclinit.getTree('tags')

    # Translate UPnP search string to recoll one
    rcls = _upnpsearchtorecoll(upnps)

    if not rcls:
        uplog(f"Upnp search string parse failed or ignored for [{upnps}]. Recoll search is empty")
        return []
    uplog(f"Search: recoll search: <{rcls}>")

    filterdir = foldersobj.dirpath(inobjid)
    if filterdir and filterdir != "/":
        #uplog(f"filterdir: <{filterdir}>")
        rcls += " dir:\"" + filterdir + "\""
        
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
            # The doc is either an actual recollindex product from the
            # FS or a synthetic one from uprcltags creating album
            # entries. Different processing for either
            e = None
            if doc["rcludi"].find("albid") == 0:
                albid = doc["rcludi"][5:]
                #uplog(f"Search: album: {doc['rcludi']} albid {albid}")
                e = tags.direntryforalbid(albid)
            elif doc["rcludi"].find("artid") == 0:
                artid = doc["rcludi"][5:]
                #uplog(f"Search: artist: {doc['rcludi']} albid {albid}")
                e = tags.direntryforartid(artid)
            else:
                # Objidfordoc uses the path from the url to walk the _dirvec and determine the right
                # entry if doc is a container. If doc is an item, the returned id is not usable but
                # still unique (based on the xdocid). We used to return
                # (0$uprcl$folders$seeyoulater), but this ennoys bubble to no end.  This still
                # breaks the recommendation for the objids to be consistent and unchanging
                id = foldersobj.objidfordoc(doc)
                #uplog("Search: id [%s] for doc udi [%s]\n" % (id, doc["rcludi"]))
                e = uprclutils.rcldoctoentry(id, inobjid, httphp, pathprefix, doc)
            #uplog(f"Search: entry: {e}")
            if e:
                entries.append(e)
        if (maxcnt > 0 and len(entries) >= maxcnt) or len(docs) != rclq.arraysize:
            break
    uplog("Search retrieved %d docs" % (len(entries),))

    entries.sort(key=uprclutils.cmpentries)
    return entries

if __name__ == '__main__':
    s = '(upnp:artist derivedFrom  "abc\\"def\\g") or (dc:title:xxx) '
    s = 'upnp:class derivedfrom "object.container.album" and dc:title contains "n"'
    if len(sys.argv) > 1:
        s = sys.argv[1]
    print("INPUT: %s" % s)
    o = _upnpsearchtorecoll(s)
    print("OUTPUT: %s" % o)
