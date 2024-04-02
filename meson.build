project(
  'upmdcli',
  'cpp',
  license: 'LGPL 2.1+',
  version: '1.8.10',
  default_options: ['cpp_std=c++17','buildtype=debugoptimized'],
  meson_version: '>=0.49',
)

# Things that existed in the autoconf build
# HAVE_EXP10: use cc.links()
# https://mesonbuild.com/Compiler-properties.html
# MDU_INCLUDE_LOG : actually not needed because include <log.h> works with -I/usr/include/libupnpp
# CONFIGDIR not used at all in the code.


deps = []
dep_libupnpp = dependency('libupnpp')
deps += dep_libupnpp
deps += dependency('libcurl')
deps += dependency('libmicrohttpd')
deps += dependency('jsoncpp')
deps += dependency('libmpdclient')
deps += dependency('threads')

upmpdcli_incdir = include_directories('src')

upmpdcli_sources = files(
     'src/avtransport.cxx',
     'src/avtransport.hxx',
     'src/chrono.cpp',
     'src/chrono.h',
     'src/closefrom.cpp',
     'src/closefrom.h',
     'src/conf_post.h',
     'src/conftree.cpp',
     'src/conftree.h',
     'src/conman.cxx',
     'src/conman.hxx',
     'src/execmd.cpp',
     'src/execmd.h',
     'src/main.cxx',
     'src/main.hxx',
     'src/mediaserver/cdplugins/abuffer.h',
     'src/mediaserver/cdplugins/bufxchange.h',
     'src/mediaserver/cdplugins/cdplugin.hxx',
     'src/mediaserver/cdplugins/cmdtalk.cpp',
     'src/mediaserver/cdplugins/cmdtalk.h',
     'src/mediaserver/cdplugins/curlfetch.cpp',
     'src/mediaserver/cdplugins/curlfetch.h',
     'src/mediaserver/cdplugins/netfetch.cpp',
     'src/mediaserver/cdplugins/netfetch.h',
     'src/mediaserver/cdplugins/plgwithslave.cxx',
     'src/mediaserver/cdplugins/plgwithslave.hxx',
     'src/mediaserver/cdplugins/streamproxy.cpp',
     'src/mediaserver/cdplugins/streamproxy.h',
     'src/mediaserver/contentdirectory.cxx',
     'src/mediaserver/contentdirectory.hxx',
     'src/mediaserver/mediaserver.cxx',
     'src/mediaserver/mediaserver.hxx',
     'src/mpdcli.cxx',
     'src/mpdcli.hxx',
     'src/netcon.cpp',
     'src/netcon.h',
     'src/ohcredentials.cxx',
     'src/ohcredentials.hxx',
     'src/ohinfo.cxx',
     'src/ohinfo.hxx',
     'src/ohmetacache.cxx',
     'src/ohmetacache.hxx',
     'src/ohplaylist.cxx',
     'src/ohplaylist.hxx',
     'src/ohproduct.cxx',
     'src/ohproduct.hxx',
     'src/ohradio.cxx',
     'src/ohradio.hxx',
     'src/ohreceiver.cxx',
     'src/ohreceiver.hxx',
     'src/ohservice.hxx',
     'src/ohservice.cxx',
     'src/ohsndrcv.cxx',
     'src/ohsndrcv.hxx',
     'src/ohtime.cxx',
     'src/ohtime.hxx',
     'src/ohvolume.cxx',
     'src/ohvolume.hxx',
     'src/protocolinfo.cxx',
     'src/protocolinfo.hxx',
     'src/pathut.cpp',
     'src/pathut.h',
     'src/readfile.cpp',
     'src/readfile.h',
     'src/renderctl.cxx',
     'src/renderctl.hxx',
     'src/smallut.cpp',
     'src/smallut.h',
     'src/sysvshm.cpp',
     'src/sysvshm.h',
     'src/upmpd.cxx',
     'src/upmpd.hxx',
     'src/upmpdutils.cxx',
     'src/upmpdutils.hxx',
     'src/urlmorph.cxx',
     'src/urlmorph.hxx',
     'src/workqueue.h',
)

auto = configuration_data()
ver = meson.project_version().split('.')
auto.set_quoted('PACKAGE_VERSION', meson.project_version())
cfile = configure_file(input: 'src/config.h.in', output: 'config.h',
                       configuration: auto)

upmpdcli_datadir = get_option('prefix') / get_option('datadir') / 'upmpdcli'

upmpdcli = executable(
  'upmpdcli',
  upmpdcli_sources,
  include_directories: upmpdcli_incdir,
  dependencies: deps,
  install: true,
  cpp_args: ['-DDATADIR="' + upmpdcli_datadir + '"'],
)

########################### Optional Configuration GUI
if get_option('confgui')

  qt5_mod = import('qt5')
  qt5widgets = dependency('qt5', modules : 'Widgets')

  processed = qt5_mod.preprocess(
    moc_headers : ['cfgui/mainwindow.h', 'cfgui/confgui.h'],
  )

  upmpdcli_config_sources = [
  'cfgui/confgui.cpp',
  'cfgui/confgui.h',
  'cfgui/confmain.cpp',
  'cfgui/mainwindow.h',
  'cfgui/picoxml.h',
  'src/conftree.cpp',
  'src/smallut.cpp',
  'src/pathut.cpp',
   processed,
  ]

  cfgincludes =  [dep_libupnpp.get_pkgconfig_variable('includedir') / 'libupnpp', 'src', 'cfgui']
  confgui = executable(
    'upmpdcli-config',
    sources: upmpdcli_config_sources,
    install: true,
    dependencies: [qt5widgets, dep_libupnpp],
    include_directories: cfgincludes,
    cpp_args: '-DENABLE_XMLCONF',
  )
    
endif
