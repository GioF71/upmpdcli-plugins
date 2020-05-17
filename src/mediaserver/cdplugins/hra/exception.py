from __future__ import print_function

'''
    highresaudio.exception
    ~~~~~~~~~~~~~~~

    :part_of: xbmc-highresaudio
'''
import sys
import pprint
import traceback


class HighresAudioXbmcError(Exception):

    def __init__(self, **ka):
        if not 'additional' in ka or ka['additional'] is None:
            ka['additional'] = ''
        if (not 'who' in ka) or (not 'what' in ka):
            raise Exception(
                'HighresAudioXbmcError', 'Missing constructor arguments (who|what)')
        nl = "\n"
        msg = "[HighresAudioXbmcError]" + nl
        msg += " - who        : " + pprint.pformat(ka['who']) + nl
        msg += " - what       : " + ka['what'] + nl
        msg += " - additional : " + repr(ka['additional']) + nl
#        msg += " - type       : " + self.exc_type + nl
#        msg += " - value      : " + self.exc_value + nl
        msg += " - Stack      : " + nl
        print("%s" % msg, file=sys.stderr)
        print("%s" % traceback.print_exc(10), file=sys.stderr)
