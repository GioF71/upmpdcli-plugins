#!/usr/bin/python3

import gmusicapi
import sys
import os

usage_string = \
'''\
Usage: gmusic-init-oauth.py <outputfile>
The output file should be copied to: 
  /var/cache/upmpdcli/gmusic/gmusic-mobile.cred
Make sure that the file and directory are accessible to the user which
runs the upmpdcli process (usually 'upmpdcli'):
  sudo chown -R upmpdcli /var/cache/upmpdcli
'''

def Usage():
    print(usage_string, file=sys.stderr)
    sys.exit(1)

if len(sys.argv) != 2:
    Usage()
outputfile = sys.argv[1]

mc = gmusicapi.Mobileclient()

mc.perform_oauth(storage_filepath=outputfile)

print("Please copy the output to /var/cache/upmpdcli/gmusic/gmusic-mobile.cred")
print("and make sure that the file and directory are readable by user upmpdcli")
print("e.g.: chown -R upmpdcli /var/cache/upmpdcli")
print("Adjust the above if the upmpdcli process runs under another user")

