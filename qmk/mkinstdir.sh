#!/bin/sh


fatal()
{
    echo $*
    exit 1
}
Usage()
{
    fatal 'mkinstdir.sh <targetdir>'
}

test $# -eq 1 || Usage

TARGETDIR=$1

test -f upmpdcli.pro || fatal must be run in the qmk/ directory

QCBUILDLOC=Qt_6_6_3_for_macOS

DATADIR=$TARGETDIR/share/upmpdcli
test -d $DATADIR || mkdir -p $DATADIR || fatal cant create $DATADIR
BINDIR=$TARGETDIR/bin
test -d $BINDIR || mkdir -p $BINDIR || fatal cant create $BINDIR

plugins=`ls -F ../src/mediaserver/cdplugins | grep -E '/$' | grep -v attic/`

PLUGINSDIR=$DATADIR/cdplugins/
mkdir -p  $PLUGINSDIR || fatal cant create $PLUGINSDIR

for i in $plugins;do
    i=`echo $i|sed -e s,/,,`
    cp -rp ../src/mediaserver/cdplugins/$i $PLUGINSDIR || exit 1
done

srcs='AVTransport.xml  OHPlaylist.xml OHReceiver.xml
presentation.html upmpdcli.conf-dist description.xml OHCredentials.xml OHProduct.xml 
OHTime.xml protocolinfo.txt RenderingControl.xml upmpdcli.conf-xml ConnectionManager.xml  icon.png
OHInfo.xml  OHRadio.xml  OHVolume.xml radio_scripts'
for i in $srcs;do
    cp -rp ../src/$i $DATADIR || exit 1
done

for i in MS-description.xml ContentDirectory.xml;do
    cp -rp ../src/mediaserver/$i $DATADIR || exit 1
done
    
cp -rp ../rdpl2stream $DATADIR || exit 1

mkdir -p $DATADIR/src_scripts
cp -p ../samplescripts/* $DATADIR/src_scripts

cp -p build/${QCBUILDLOC}-Release/upmpdcli $TARGETDIR/bin

mkdir -p $TARGETDIR/etc
cp -p ../src/upmpdcli.conf-dist $TARGETDIR/etc/upmpdcli.conf



