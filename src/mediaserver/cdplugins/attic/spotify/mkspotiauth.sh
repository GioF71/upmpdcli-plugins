#!/bin/sh

# Create a zip for a standalone spotify auth-token creation utility

fatal()
{
    echo $*
    exit 1
}
test -f spotiauthinit.py || fatal "Must run in the spotify directory"

cd ..
rm -rf /tmp/upmpdcli-spotify-authinit
cp -rp spotify /tmp/upmpdcli-spotify-authinit
cd /tmp
rm -rf upmpdcli-spotify-authinit/__pycache__ \
   upmpdcli-spotify-authinit/spotipy/__pycache__
   
zip -rv upmpdcli-spotify-authinit.zip \
upmpdcli-spotify-authinit/spotiauthinit.py \
upmpdcli-spotify-authinit/upmspotid.py \
upmpdcli-spotify-authinit/spotipy

echo "Created /tmp/upmpdcli-spotify-authinit.zip"
