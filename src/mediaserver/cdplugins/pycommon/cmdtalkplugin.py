# Copyright (C) 2016 J.F.Dockes
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the
# Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

from __future__ import print_function

import sys
import cmdtalk

prcnmkey = "cmdtalk:proc"

class Dispatch:
    def __init__(self):
        self.map = {}
        
    def record(self, nm):
        def decorator(func):
            self.map[nm] = func
            return func
        return decorator

    def run(self, nm, params):
        func = self.map[nm]
        return func(params)
    
class Processor:
    def __init__(self, dispatcher, outfile=sys.stdout, infile=sys.stdin,
                 exitfunc=None):
        self.em = cmdtalk.CmdTalk(outfile=outfile, infile=infile,
                                  exitfunc=exitfunc)
        self.dispatcher = dispatcher
        
    def log(self, s, doexit = 0, exitvalue = 1):
        self.em.log(s, doexit, exitvalue)
        
    def process(self, params):
        # self.em.log("pCmdTalkProcessor.process: [%s]" % params)
        if not prcnmkey in params:
            raise Exception('%s not in args' % prcnmkey)
        
        return self.dispatcher.run(params[prcnmkey], params)

    def mainloop(self):
        cmdtalk.main(self.em, self)
