AM_CPPFLAGS = -DDEBUG -g -Wall \
	    -DMDU_INCLUDE_LOG='<libupnpp/log.h>' \
            $(upnpp_CFLAGS) \
            $(libmpdclient_CFLAGS) \
            $(libmicrohttpd_CFLAGS) \
            $(jsoncpp_CFLAGS) \
            -I$(top_srcdir)/src \
            -I$(top_srcdir)/src/mediaserver/cdplugins \
            -DDATADIR=\"${pkgdatadir}\" -DCONFIGDIR=\"${sysconfdir}\"

AM_CXXFLAGS = -std=c++14

bin_PROGRAMS = upmpdcli scctl

if MAKECONFGUI
all-local: qtconfgui
qtconfgui:
	test -d cfgui || mkdir cfgui
	(cd cfgui; ${QMAKE} PREFIX=${prefix} upmpdcli-config.pro)
	$(MAKE) -C cfgui LFLAGS="$(LDFLAGS)" prefix=$(prefix) \
                exec_prefix=$(exec_prefix) libdir=$(libdir)
clean-local: qtconfgui-clean
qtconfgui-clean:
	-$(MAKE) -C cfgui clean
install-exec-local: qtconfgui-install
qtconfgui-install:
	$(MAKE) -C cfgui LFLAGS="$(LDFLAGS)" INSTALL_ROOT=$(DESTDIR) \
                prefix=$(prefix) exec_prefix=$(exec_prefix) libdir=$(libdir) \
                install
endif

CLEANFILES = $(BUILT_SOURCES)

upmpdcli_SOURCES = \
     src/avtransport.cxx \
     src/avtransport.hxx \
     src/chrono.cpp \
     src/chrono.h \
     src/closefrom.cpp \
     src/closefrom.h \
     src/conf_post.h \
     src/conftree.cpp \
     src/conftree.h \
     src/conman.cxx \
     src/conman.hxx \
     src/execmd.cpp \
     src/execmd.h \
     src/main.cxx \
     src/main.hxx \
     src/mediaserver/cdplugins/abuffer.h \
     src/mediaserver/cdplugins/bufxchange.h \
     src/mediaserver/cdplugins/cdplugin.hxx \
     src/mediaserver/cdplugins/cmdtalk.cpp \
     src/mediaserver/cdplugins/cmdtalk.h \
     src/mediaserver/cdplugins/curlfetch.cpp \
     src/mediaserver/cdplugins/curlfetch.h \
     src/mediaserver/cdplugins/netfetch.cpp \
     src/mediaserver/cdplugins/netfetch.h \
     src/mediaserver/cdplugins/plgwithslave.cxx \
     src/mediaserver/cdplugins/plgwithslave.hxx \
     src/mediaserver/cdplugins/streamproxy.cpp \
     src/mediaserver/cdplugins/streamproxy.h \
     src/mediaserver/contentdirectory.cxx \
     src/mediaserver/contentdirectory.hxx \
     src/mediaserver/mediaserver.cxx \
     src/mediaserver/mediaserver.hxx \
     src/mpdcli.cxx \
     src/mpdcli.hxx \
     src/netcon.cpp \
     src/netcon.h \
     src/ohcredentials.cxx \
     src/ohcredentials.hxx \
     src/ohinfo.cxx \
     src/ohinfo.hxx \
     src/ohmetacache.cxx \
     src/ohmetacache.hxx \
     src/ohplaylist.cxx \
     src/ohplaylist.hxx \
     src/ohproduct.cxx \
     src/ohproduct.hxx \
     src/ohradio.cxx \
     src/ohradio.hxx \
     src/ohreceiver.cxx \
     src/ohreceiver.hxx \
     src/ohservice.hxx \
     src/ohservice.cxx \
     src/ohsndrcv.cxx \
     src/ohsndrcv.hxx \
     src/ohtime.cxx \
     src/ohtime.hxx \
     src/ohvolume.cxx \
     src/ohvolume.hxx \
     src/protocolinfo.cxx \
     src/protocolinfo.hxx \
     src/pathut.cpp \
     src/pathut.h \
     src/readfile.cpp \
     src/readfile.h \
     src/renderctl.cxx \
     src/renderctl.hxx \
     src/smallut.cpp \
     src/smallut.h \
     src/sysvshm.cpp \
     src/sysvshm.h \
     src/upmpd.cxx \
     src/upmpd.hxx \
     src/upmpdutils.cxx \
     src/upmpdutils.hxx \
     src/urlmorph.cxx \
     src/urlmorph.hxx \
     src/workqueue.h

upmpdcli_LDADD = $(UPMPDCLI_LIBS)

if ENABLESPOTIFY
upmpdcli_SOURCES += src/mediaserver/cdplugins/spotify/spotiproxy.cpp \
     src/mediaserver/cdplugins/spotify/spotiproxy.h 
AM_CXXFLAGS += -DENABLE_SPOTIFY
endif

scctl_SOURCES = \
    scctl_src/scctl.cpp \
    src/netcon.cpp \
    src/smallut.cpp \
    src/upmpdutils.cxx

scctl_LDADD = $(SCCTL_LIBS)
              
dist_pkgdata_DATA = src/description.xml src/AVTransport.xml \
                  src/RenderingControl.xml src/ConnectionManager.xml \
                  src/OHProduct.xml src/OHCredentials.xml src/OHInfo.xml \
                  src/OHTime.xml \
                  src/OHVolume.xml src/OHPlaylist.xml src/OHReceiver.xml \
                  src/OHRadio.xml src/mediaserver/ContentDirectory.xml \
                  src/mediaserver/MS-description.xml \
                  src/protocolinfo.txt src/presentation.html \
                  src/icon.png src/upmpdcli.conf-dist src/upmpdcli.conf-xml

rdpl2streamdir = $(pkgdatadir)/rdpl2stream
dist_rdpl2stream_DATA = \
    rdpl2stream/AsfPlaylistDecoder.py  \
    rdpl2stream/AsxPlaylistDecoder.py  \
    rdpl2stream/common.py  \
    rdpl2stream/fetchStream.py  \
    rdpl2stream/M3uPlaylistDecoder.py \
    rdpl2stream/PlsPlaylistDecoder.py  \
    rdpl2stream/RamPlaylistDecoder.py  \
    rdpl2stream/StreamDecoder.py \
    rdpl2stream/UrlInfo.py \
    rdpl2stream/XspfPlaylistDecoder.py \
    rdpl2stream/AUTHORS \
    rdpl2stream/CONTRIBUTORS \
    rdpl2stream/COPYING
    
radioscriptsdir = $(pkgdatadir)/radio_scripts
dist_radioscripts_DATA = \
                       src/radio_scripts/radio-paradise-get-flac.py \
                       src/radio_scripts/radiolist.conf \
                       src/radio_scripts/npr/src/main.rs \
                       src/radio_scripts/npr/Cargo.toml \
                       src/radio_scripts/npr/README \
                       src/radio_scripts/npo-dynamic-art.py \
                       src/radio_scripts/radio-paradise-get-art.sh \
                       src/radio_scripts/radio-paradise-meta.py \
                       src/radio_scripts/npo-funx-dynamic-art.py \
                       src/radio_scripts/radio-france-meta.py

webdir = $(pkgdatadir)
nobase_dist_web_DATA = \
    web/scweb.py \
    web/static/style.css \
    web/bottle.py \
    web/views/main.tpl \
    web/views/list.tpl \
    web/views/menu.tpl \
    web/views/assoc.tpl \
    web/views/header.tpl \
    web/views/footer.tpl \
    web/views/stop.tpl \
    web/init/default-scweb \
    web/init/scweb-service \
    web/scweb-standalone.py

cdpluginspycomdir = $(pkgdatadir)/cdplugins/pycommon
dist_cdpluginspycom_DATA = \
                    src/mediaserver/cdplugins/pycommon/cmdtalk.py \
                    src/mediaserver/cdplugins/pycommon/cmdtalkplugin.py \
                    src/mediaserver/cdplugins/pycommon/conftree.py \
                    src/mediaserver/cdplugins/pycommon/routing.py \
                    src/mediaserver/cdplugins/pycommon/upmplgmodels.py \
                    src/mediaserver/cdplugins/pycommon/upmplgutils.py \
                    src/mediaserver/cdplugins/pycommon/xbmcplug.py \
                    src/mediaserver/cdplugins/pycommon/upradioconf.py
cdpluginstidaldir = $(pkgdatadir)/cdplugins/tidal
dist_cdpluginstidal_DATA = \
                    src/mediaserver/cdplugins/tidal/tidal-app.py \
                    src/mediaserver/cdplugins/tidal/codec.py \
                    src/mediaserver/cdplugins/tidal/constants.py \
                    src/mediaserver/cdplugins/tidal/element_type.py \
                    src/mediaserver/cdplugins/tidal/identifier_util.py \
                    src/mediaserver/cdplugins/tidal/item_identifier_key.py \
                    src/mediaserver/cdplugins/tidal/item_identifier.py \
                    src/mediaserver/cdplugins/tidal/option_key.py \
                    src/mediaserver/cdplugins/tidal/persistence.py \
                    src/mediaserver/cdplugins/tidal/played_track.py \
                    src/mediaserver/cdplugins/tidal/search_type.py \
                    src/mediaserver/cdplugins/tidal/tag_type.py \
                    src/mediaserver/cdplugins/tidal/upnp_util.py

cdpluginsqobuzdir = $(pkgdatadir)/cdplugins/qobuz
dist_cdpluginsqobuz_DATA = \
                  src/mediaserver/cdplugins/qobuz/__init__.py \
                  src/mediaserver/cdplugins/qobuz/qobuz-app.py \
                  src/mediaserver/cdplugins/qobuz/session.py 
cdpluginsqobuzlibdir = $(pkgdatadir)/cdplugins/qobuz/api
dist_cdpluginsqobuzlib_DATA = \
                  src/mediaserver/cdplugins/qobuz/api/__init__.py \
                  src/mediaserver/cdplugins/qobuz/api/raw.py \
                  src/mediaserver/cdplugins/qobuz/api/spoofbuz.py 

cdpluginshradir = $(pkgdatadir)/cdplugins/hra
dist_cdpluginshra_DATA = \
                  src/mediaserver/cdplugins/hra/hra-app.py \
                  src/mediaserver/cdplugins/hra/hraapi.py \
                  src/mediaserver/cdplugins/hra/session.py

cdpluginsdeezerdir = $(pkgdatadir)/cdplugins/deezer
dist_cdpluginsdeezer_DATA = \
                  src/mediaserver/cdplugins/deezer/deezer-app.py \
                  src/mediaserver/cdplugins/deezer/deezerapi.py \
                  src/mediaserver/cdplugins/deezer/deezersession.py

cdpluginsbbcdir = $(pkgdatadir)/cdplugins/bbc
dist_cdpluginsbbc_DATA = \
                  src/mediaserver/cdplugins/bbc/bbc-app.py

cdpluginsradiobrowserdir = $(pkgdatadir)/cdplugins/radio-browser
dist_cdpluginsradiobrowser_DATA = \
                  src/mediaserver/cdplugins/radio-browser/radio-browser-app.py

cdpluginsspotifydir = $(pkgdatadir)/cdplugins/spotify
dist_cdpluginsspotify_DATA = \
                  src/mediaserver/cdplugins/spotify/spotify-app.py \
                  src/mediaserver/cdplugins/spotify/session.py \
                  src/mediaserver/cdplugins/spotify/upmspotid.py


cdpluginsspotifylibdir = $(pkgdatadir)/cdplugins/spotify/spotipy
dist_cdpluginsspotifylib_DATA = \
                  src/mediaserver/cdplugins/spotify/spotipy/__init__.py \
                  src/mediaserver/cdplugins/spotify/spotipy/client.py \
                  src/mediaserver/cdplugins/spotify/spotipy/oauth2.py \
                  src/mediaserver/cdplugins/spotify/spotipy/util.py

cdpluginsradiosdir = $(pkgdatadir)/cdplugins/upradios
dist_cdpluginsradios_DATA = \
                 src/mediaserver/cdplugins/upradios/upradios-app.py

cdpluginsuprcldir = $(pkgdatadir)/cdplugins/uprcl
dist_cdpluginsuprcl_DATA = \
                 src/mediaserver/cdplugins/uprcl/bottle.py \
                 src/mediaserver/cdplugins/uprcl/minimconfig.py \
                 src/mediaserver/cdplugins/uprcl/minimtagfixer.py \
                 src/mediaserver/cdplugins/uprcl/rclconfig-fields \
                 src/mediaserver/cdplugins/uprcl/rclconfig-mimeconf \
                 src/mediaserver/cdplugins/uprcl/rclconfig-mimemap \
                 src/mediaserver/cdplugins/uprcl/rwlock.py \
                 src/mediaserver/cdplugins/uprcl/uprcl-app.py \
                 src/mediaserver/cdplugins/uprcl/uprclfolders.py \
                 src/mediaserver/cdplugins/uprcl/uprclhttp.py \
                 src/mediaserver/cdplugins/uprcl/uprclindex.py \
                 src/mediaserver/cdplugins/uprcl/uprclinit.py \
                 src/mediaserver/cdplugins/uprcl/uprclplaylists.py \
                 src/mediaserver/cdplugins/uprcl/uprclsearch.py \
                 src/mediaserver/cdplugins/uprcl/uprcltags.py \
                 src/mediaserver/cdplugins/uprcl/uprcltagscreate.py \
                 src/mediaserver/cdplugins/uprcl/uprcluntagged.py \
                 src/mediaserver/cdplugins/uprcl/uprclutils.py

uprclbottlestaticdir = $(pkgdatadir)/cdplugins/uprcl/bottle/static
dist_uprclbottlestatic_DATA = \
    src/mediaserver/cdplugins/uprcl/bottle/static/style.css
uprclbottleviewsdir = $(pkgdatadir)/cdplugins/uprcl/bottle/views
dist_uprclbottleviews_DATA = \
    src/mediaserver/cdplugins/uprcl/bottle/views/footer.tpl \
    src/mediaserver/cdplugins/uprcl/bottle/views/header.tpl \
    src/mediaserver/cdplugins/uprcl/bottle/views/main.tpl
    
cdpluginssubsonicdir = $(pkgdatadir)/cdplugins/subsonic
dist_cdpluginssubsonic_DATA = \
                 src/mediaserver/cdplugins/subsonic/album_util.py \
                 src/mediaserver/cdplugins/subsonic/artist_initial_cache.py \
                 src/mediaserver/cdplugins/subsonic/artist_initial_cache_provider.py \
                 src/mediaserver/cdplugins/subsonic/art_retriever.py \
                 src/mediaserver/cdplugins/subsonic/cache_manager_provider.py \
                 src/mediaserver/cdplugins/subsonic/caching.py \
                 src/mediaserver/cdplugins/subsonic/codec.py \
                 src/mediaserver/cdplugins/subsonic/codec_delimiter_style.py \
                 src/mediaserver/cdplugins/subsonic/config.py \
                 src/mediaserver/cdplugins/subsonic/connector_provider.py \
                 src/mediaserver/cdplugins/subsonic/converter.py \
                 src/mediaserver/cdplugins/subsonic/element_type.py \
                 src/mediaserver/cdplugins/subsonic/entry_creator.py \
                 src/mediaserver/cdplugins/subsonic/identifier_util.py \
                 src/mediaserver/cdplugins/subsonic/item_identifier_key.py \
                 src/mediaserver/cdplugins/subsonic/item_identifier.py \
                 src/mediaserver/cdplugins/subsonic/msgproc_provider.py \
                 src/mediaserver/cdplugins/subsonic/search_type.py \
                 src/mediaserver/cdplugins/subsonic/selector.py \
                 src/mediaserver/cdplugins/subsonic/subsonic-app.py \
                 src/mediaserver/cdplugins/subsonic/subsonic_init.py \
                 src/mediaserver/cdplugins/subsonic/subsonic_init_provider.py \
                 src/mediaserver/cdplugins/subsonic/subsonic_util.py \
                 src/mediaserver/cdplugins/subsonic/tag_type.py \
                 src/mediaserver/cdplugins/subsonic/upnp_util.py

EXTRA_DIST = \
    autogen.sh \
    cfgui/Makefile \
    cfgui/confgui.cpp \
    cfgui/confgui.h \
    cfgui/confmain.cpp \
    cfgui/mainwindow.h \
    cfgui/picoxml.h \
    cfgui/upmpdcli-config.pro \
    autogen.sh \
    src/mediaserver/cdplugins/spotify/spotiproxy.cpp \
    src/mediaserver/cdplugins/spotify/spotiproxy.h \
    src/upmpdcli.conf-xml \
    systemd/upmpdcli.service


install-data-hook:
	(cd $(DESTDIR)$(sysconfdir); test -f upmpdcli.conf || \
		mv upmpdcli.conf-dist upmpdcli.conf; chmod 600 upmpdcli.conf)
	(cd $(DESTDIR)$(pkgdatadir); test -d src_scripts || mkdir src_scripts)
	(cd $(DESTDIR)/$(cdpluginsbbcdir); chmod a+x bbc-app.py) 
	(cd $(DESTDIR)/$(cdpluginsdeezerdir); chmod a+x deezer-app.py) 
	(cd $(DESTDIR)/$(cdpluginshradir); chmod a+x hra-app.py) 
	(cd $(DESTDIR)/$(cdpluginsqobuzdir); chmod a+x qobuz-app.py) 
	(cd $(DESTDIR)/$(cdpluginsradiosdir); chmod a+x upradios-app.py) 
	(cd $(DESTDIR)/$(cdpluginsspotifydir); chmod a+x spotify-app.py) 
	(cd $(DESTDIR)/$(cdpluginssubsonicdir); chmod a+x subsonic-app.py) 
	(cd $(DESTDIR)/$(cdpluginstidaldir); chmod a+x tidal-app.py) 
	(cd $(DESTDIR)/$(cdpluginsuprcldir); chmod a+x uprcl-app.py) 
	(cd $(DESTDIR)/$(cdpluginsradiobrowserdir); chmod a+x radio-browser-app.py) 
	(cd $(DESTDIR)/$(radioscriptsdir);chmod a+rx . *;chmod a-x radiolist.conf)
	(cd $(DESTDIR)/$(rdpl2streamdir);chmod a+x fetchStream.py)
	(cd $(DESTDIR)/$(webdir)/web;chmod a+x scweb-standalone.py)
        
dist_pkgdata_SCRIPTS = samplescripts/Analog-Input

dist_sysconf_DATA = src/upmpdcli.conf-dist

dist_man1_MANS = man/upmpdcli.1

dist-hook:
	if test -z "$(NOTAG)";then \
	    test -z "`git status -s | grep -v '??' | grep -v Makefile.am`";  \
	    git tag -a upmpdcli-v$(VERSION) -m 'version $(VERSION)'; \
	fi

