TEMPLATE  = app
TARGET    = upmpdcli
QT       -= core gui
CONFIG   += console c++17 thread
CONFIG   -= app_bundle

INCLUDEPATH += ../ ../src

                        
SOURCES = \
  ../src/avtransport.cxx \
  ../src/chrono.cpp \
  ../src/closefrom.cpp \
  ../src/conftree.cpp \
  ../src/conman.cxx \
  ../src/execmd.cpp \
  ../src/main.cxx \
  ../src/mediaserver/cdplugins/cmdtalk.cpp \
  ../src/mediaserver/cdplugins/curlfetch.cpp \
  ../src/mediaserver/cdplugins/netfetch.cpp \
  ../src/mediaserver/cdplugins/plgwithslave.cxx \
  ../src/mediaserver/cdplugins/streamproxy.cpp \
  ../src/mediaserver/contentdirectory.cxx \
  ../src/mediaserver/mediaserver.cxx \
  ../src/mpdcli.cxx \
  ../src/netcon.cpp \
  ../src/ohcredentials.cxx \
  ../src/ohinfo.cxx \
  ../src/ohmetacache.cxx \
  ../src/ohplaylist.cxx \
  ../src/ohproduct.cxx \
  ../src/ohradio.cxx \
  ../src/ohreceiver.cxx \
  ../src/ohservice.cxx \
  ../src/ohsndrcv.cxx \
  ../src/ohtime.cxx \
  ../src/ohvolume.cxx \
  ../src/pathut.cpp \
  ../src/protocolinfo.cxx \
  ../src/readfile.cpp \
  ../src/renderctl.cxx \
  ../src/smallut.cpp \
  ../src/sysvshm.cpp \
  ../src/upmpd.cxx \
  ../src/upmpdutils.cxx \
  ../src/urlmorph.cxx


mac {

  # Using libmpdclient from macports and installing there too. Change the
  # following to /usr/local if using, e.g. homebrew
  INCLUDEPATH += $$PWD/../../libmpdclient-2.20/include
  LIBMPDCLIENT = $$PWD/../../libmpdclient-2.20/build/libmpdclient.a
  # Portable install: use an empty datadir
  DEFINES += DATADIR=\\\"\\\"
  
  QCBUILDLOC=Qt_6_4_2_for_macOS
  QMAKE_APPLE_DEVICE_ARCHS = x86_64 arm64
  QMAKE_CXXFLAGS += -Wno-unused-parameter

  INCLUDEPATH += ../../libupnpp/libupnpp/ ../../libupnpp/
  INCLUDEPATH += ../sysdeps/jsoncpp
  INCLUDEPATH += ../../libmicrohttpd-0.9.71/src/include
  
  DEFINES += _LARGE_FILE_SOURCE
  DEFINES += _FILE_OFFSET_BITS=64
            
  SOURCES += ../sysdeps/jsoncpp/jsoncpp.cpp

  LIBS += $$PWD/../../libupnpp/build-libupnpp-$$QCBUILDLOC-Release/libupnpp.a
  LIBS += $$PWD/../../npupnp/build-libnpupnp-$$QCBUILDLOC-Release/libnpupnp.a
  LIBS += $$PWD/../../libmicrohttpd-0.9.71/src/microhttpd/.libs/libmicrohttpd.a
  LIBS += $$LIBMPDCLIENT
  LIBS += -lexpat -lcurl

}
