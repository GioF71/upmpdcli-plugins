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

import conftree
import copy
import locale
import os
import shutil
import subprocess
import sys
import time

from upmplgutils import uplog
import uprclinit


def _maybeinitconfdir(confdir, topdirs):
    if not os.path.isdir(confdir):
        if os.path.exists(confdir):
            raise Exception("Exists and not directory: %s" % confdir)
        os.mkdir(confdir)
        
    datadir = os.path.dirname(__file__)
    uplog("datadir: %s" % datadir)

    for fn in ("fields", "mimemap", "mimeconf"):
        dst = os.path.join(confdir, fn)
        src = os.path.join(datadir, "rclconfig-" + fn)
        shutil.copyfile(src, dst)

    exclpats = ""
    if uprclinit.g_minimconfig:
        exclpats = uprclinit.g_minimconfig.getexcludepatterns()

    userconfig = uprclinit.g_upconfig.get("uprclconfrecolluser")
    if not userconfig:
        userconfig = os.path.join(confdir, "recoll.conf.user")
    if os.path.exists(userconfig):
        userconfdata = open(userconfig, "rb").read()
    else:
        userconfdata = b''
        
    path = os.path.join(confdir, "recoll.conf")
    f = open(path, "wb")
    f.write(b"topdirs = %s\n"% topdirs.encode(locale.getpreferredencoding()))
    f.write(b"idxabsmlen = 0\n")
    f.write(b"loglevel = 2\n")
    f.write(b"noaspell = 1\n")
    f.write(b"nomd5types = rclaudio rclimg\n")
    f.write(b"testmodifusemtime = 1\n")
    f.write(b"idxmetastoredlen = 20000\n")
    f.write(b"audiotagfixerscript = %b\n" %
            os.path.join(datadir, "minimtagfixer.py").encode('utf-8'))
    if exclpats:
        f.write(b"skippedNames+ = " + exclpats.encode("utf-8") + b"\n")
    else:
        f.write(b"skippedNames+ = \n")
    if userconfdata:
        f.write(userconfdata)
    f.close()


_idxproc = None
_lastidxstatus = None


def runindexer(confdir, topdirs):
    global _idxproc, _lastidxstatus
    if _idxproc is not None:
        raise Exception("uprclrunindexer: already running")

    _maybeinitconfdir(confdir, topdirs)

    cf = conftree.ConfSimple(os.path.join(confdir, "recoll.conf"),
                             readonly = False)
    td = cf.get("topdirs", '')
    if td != topdirs:
        cf.set("topdirs", topdirs)

    env = copy.deepcopy(os.environ)
    env["HOME"] = confdir
    _idxproc = subprocess.Popen(["recollindex", "-c", confdir])

def indexerdone():
    global _idxproc, _lastidxstatus
    if _idxproc is None:
        return True
    _lastidxstatus = _idxproc.poll()
    if _lastidxstatus is None:
        return False
    _idxproc = None
    return True

def indexerstatus():
    return _lastidxstatus
    


# Only used for testing
if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: uprclindex.py <confdir> <topdirs>", file=sys.stderr)
        sys.exit(1)
    runindexer(sys.argv[1], sys.argv[2])
    while True:
        if indexerdone():
            uplog("Indexing done, status: %d" % indexerstatus())
            sys.exit(0)
        uplog("Waiting for indexer")
        time.sleep(1);
