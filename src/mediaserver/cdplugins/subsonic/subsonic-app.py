#!/usr/bin/python3

import cmdtalkplugin
import conftree

from upmplgutils import uplog, setidprefix, direntry

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = "0$subsonic$"
setidprefix("subsonic")

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

# Possible once initialisation. Always called by browse() or search(), should remember if it has
# something to do (e.g. the _g_init thing, but this could be something else).
_g_init = False
def _initsubsonic():
    global _g_init
    if _g_init:
        return True

    # Do whatever is needed here

    _g_init = True
    return True

@dispatcher.record('trackuri')
def trackuri(a):
    # We generate URIs which directly point to the stream, so this method should never be called.
    raise Exception("trackuri: should not be called for subsonic!")


def _returnentries(entries):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries" : json.dumps(entries), "nocache" : "0"}


@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _initsubsonic()
    if 'objid' not in a:
        raise Exception("No objid in args")

    objid = a['objid']

    entries = []
    # Build a list of entries in the expected format. See for example ../radio-browser/radiotoentry
    # for an example
    
    # msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)


@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    _initsubsonic()
    objid = a["objid"]
    entries = []

    # Run the search and build a list of entries in the expected format. See for example
    # ../radio-browser/radiotoentry for an example
    
    # msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)


msgproc.mainloop()
