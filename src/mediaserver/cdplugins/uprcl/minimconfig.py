# Copyright (C) 2019-2020 J.F.Dockes
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

import conftree
from uprclutils import uplog

class MinimConfig(object):
    def __init__(self, fn = ''):
        if fn:
            self.conf = conftree.ConfSimple(fn)
            uplog("Minim config read: contentDir: %s" %
                  self.conf.get("minimserver.contentDir"))
        else:
            self.conf = conftree.ConfSimple('/dev/null')
        self.quotes = "\"'"
        self.escape = ''
        self.whitespace = ', '


    def getsimplevalue(self, nm):
        s = self.conf.get(nm)
        if s:
            return s.strip()
        else:
            return s


    def getboolvalue(self, nm, dflt):
        val = self.getsimplevalue(nm)
        if val is None or val == '':
            return dflt
        if val == '0' or val.lower()[0] == 'f' or val.lower()[0] == 'n':
            return False
        else:
            return True

        
    # Split on commas and colons, a common minim format and return as
    # list of pairs
    def minimsplitsplit(self, str):
        out = []
        if not str:
            return out
        # For some reason, the active colons are backslash-escaped in
        # the file
        lst = str.replace('\\:', ':').split(',')
        for e in lst:
            l = e.split(':')
            if len(l) == 0:
                a = ''
                b = ''
            elif len(l) == 1:
                a = l[0]
                b = ''
            else:
                a = l[0]
                b = l[1]
            out.append((a.strip(),b.strip()))
        return out


    # Comma-separated list. Each element maybe a simple tagname.option
    # value or an \= assignement, with a comma-separated list of values in
    # braces. Returns a list of quadruplet: (tag, neg, optname, values)
    def minimsplitbraceslist(self, value):
        # Split everything on commas
        l1 = value.split(',')
        # Re-join parts inside braces, creating list of options
        inbraces=False
        accum = ''
        l2 = []
        for e in l1:
            if inbraces:
                accum += ', ' + e
                if e.find('}'):
                    inbraces = False
                    l2.append(accum)
                    accum=''
                continue
            if e.find('{') != -1 and e.find('}') == -1:
                inbraces = True
                accum = e
                continue
            l2.append(e)
        # Parse each option [-]tag.option={tag1,tag2} or [-]tag.option
        alloptions = []
        for e in l2:
            lhsrhs=e.split('''\=''')
            if len(lhsrhs) == 2:
                values = [v.strip().lower() for v in lhsrhs[1].lstrip('{').rstrip('}').split(',')]
            else:
                values = []
            tagopt = lhsrhs[0].split('.')
            tag = tagopt[0].strip()
            if tag.startswith('-'):
                neg = True
                tag = tag[1:]
            else:
                neg = False
            opt = '.'.join(tagopt[1:])
            alloptions.append((tag, neg, opt, values))
        return alloptions


    def getexcludepatterns(self):
        spats = self.conf.get("minimserver.excludePattern")
        if spats:
            lpats = conftree.stringToStrings(spats,
                                             quotes = self.quotes,
                                             escape = self.escape,
                                             whitespace = self.whitespace)
            spats = conftree.stringsToString(lpats)
        uplog("skippedNames from Minim excludePattern: %s" % spats)
        return spats


    def gettagvalue(self):
        stagv = self.conf.get("minimserver.tagValue")
        tagvalue = None
        if stagv:
            tagvalue = self.minimsplitbraceslist(stagv)
        return tagvalue
    

    def getaliastags(self):
        aliases = []
        saliases = self.conf.get("minimserver.aliasTags")
        #uplog("Minim:getaliastags:in: [%s]" % saliases)
        lst = self.minimsplitsplit(saliases)
        for orig,target in lst:
            orig = orig.lower()
            target = target.lower()
            rep = False
            if target.startswith('-'):
                rep = True
                target = target[1:]
            aliases.append((orig, target, rep))
        #uplog("Minim:getaliastags:out: %s" % aliases)
        return aliases

        
    def getindextags(self):
        indextags = []
        sit = self.conf.get("minimserver.indexTags")
        uplog("Minim:getindextags:in: [%s]" % sit)
        if sit:
            indextags = self.minimsplitsplit(sit)
        uplog("Minim:getindextags:out: %s" % indextags)
        return indextags


    def getitemtags(self):
        itemtags = []
        sit = self.conf.get("minimserver.itemTags")
        uplog("Minim:getitemtags:in: [%s]" % sit)
        if sit:
            itemtags = [i.strip() for i in sit.split(',')]
        uplog("Minim:getitemtags:out: %s" % itemtags)
        return itemtags


    def getcontentdirs(self):
        # minim uses '\\n' as a separator for directories (actual
        # backslash then n), not newline. Weird...
        cdirs = []
        s = self.conf.get("minimserver.contentDir")
        if s:
            cdirs = s.replace("\\n", "\n").split("\n")
        return cdirs

    
    def gettranscodingspec(self):
        s = self.conf.get("stream.transcode")
        if not s:
            return None

        specs = self.minimsplitsplit(s)
        # each spec is a pair of (input,output)
        # TBD
        pass
    
