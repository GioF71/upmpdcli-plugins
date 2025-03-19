project(
  'upmpdcli',
  'cpp',
  license: 'LGPL 2.1+',
  version: '1.9.3',
  default_options: ['cpp_std=c++17', 'buildtype=debugoptimized'],
  meson_version: '>=0.49',
)

# Things that existed in the autoconf build
# HAVE_EXP10: use cc.links()
# https://mesonbuild.com/Compiler-properties.html
# CONFIGDIR not used at all in the code.
#
# MDU_INCLUDE_LOG (log.h include path in medocutils shared code): initially thought not needed
# but actually now needed because libupnpp.pc was changed to not set -I${includedir}/libupnpp
# in order to make sure of avoiding possible collisions by forcing user code to always use
#  #include <libupnpp/xxx.h>

######## upmpdcli itself
if get_option('upmpdcli')
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
    'src/chrono.cpp',
    'src/closefrom.cpp',
    'src/conftree.cpp',
    'src/conman.cxx',
    'src/execmd.cpp',
    'src/main.cxx',
    'src/mediaserver/cdplugins/cmdtalk.cpp',
    'src/mediaserver/cdplugins/curlfetch.cpp',
    'src/mediaserver/cdplugins/netfetch.cpp',
    'src/mediaserver/cdplugins/plgwithslave.cxx',
    'src/mediaserver/cdplugins/streamproxy.cpp',
    'src/mediaserver/contentdirectory.cxx',
    'src/mediaserver/mediaserver.cxx',
    'src/mpdcli.cxx',
    'src/netcon.cpp',
    'src/ohcredentials.cxx',
    'src/ohinfo.cxx',
    'src/ohmetacache.cxx',
    'src/ohplaylist.cxx',
    'src/ohproduct.cxx',
    'src/ohradio.cxx',
    'src/ohreceiver.cxx',
    'src/ohservice.cxx',
    'src/ohsndrcv.cxx',
    'src/ohtime.cxx',
    'src/ohvolume.cxx',
    'src/pathut.cpp',
    'src/protocolinfo.cxx',
    'src/readfile.cpp',
    'src/renderctl.cxx',
    'src/smallut.cpp',
    'src/sysvshm.cpp',
    'src/upmpd.cxx',
    'src/upmpdutils.cxx',
    'src/urlmorph.cxx',
  )
  
  auto = configuration_data()
  auto.set_quoted('UPMPDCLI_VERSION', meson.project_version())
  configure_file(
    input: 'src/config.h.in',
    output: 'config.h',
    configuration: auto,
  )
  
  upmpdcli_datadir = get_option('prefix') / get_option('datadir') / 'upmpdcli'
  
  executable(
    'upmpdcli',
    upmpdcli_sources,
    include_directories: upmpdcli_incdir,
    dependencies: deps,
    install: true,
    cpp_args: ['-DDATADIR="' + upmpdcli_datadir + '"', '-DMDU_INCLUDE_LOG="libupnpp/log.h"'],
  )
endif
#### End upmpdcli

########################### Optional Configuration GUI
if get_option('confgui')

  qt5_mod = import('qt5')
  qt5widgets = dependency('qt5', modules: 'Widgets')

  processed = qt5_mod.preprocess(
    moc_headers: ['cfgui/mainwindow.h', 'cfgui/confgui.h'],
  )

  upmpdcli_config_sources = files(
    'cfgui/confgui.cpp',
    'cfgui/xmltoconfgui.cpp',
    'cfgui/confmain.cpp',
    'cfgui/loclog/log.cpp',
    'src/conftree.cpp',
    'src/pathut.cpp',
    'src/smallut.cpp',
  )
  upmpdcli_config_sources += processed

  deps = [qt5widgets,]
  cppargs = []
  idir = 'src'
  if get_option('confgui_listifs')
    deps += dep_libupnpp
    cppargs += '-DENABLE_NETIF=1 -DMDU_INCLUDE_LOG="loclog/log.h"'
    idir = dep_libupnpp.get_pkgconfig_variable('includedir') / 'libupnpp'
  endif
  cfgincludes = include_directories(
    'src',
    'cfgui',
    'cfgui/loclog',
     idir,
  )

  executable(
    'upmpdcli-config',
    sources: upmpdcli_config_sources,
    install: true,
    dependencies: deps,
    include_directories: cfgincludes,
    cpp_args: cppargs,
  )

endif

########################### Optional scctl songcast control and web interface

if get_option('scctl')
  scctl_sources = files(
    'scctl_src/scctl.cpp',
    'src/netcon.cpp',
    'src/smallut.cpp',
    'src/upmpdutils.cxx',
  )

  scctl_includes = include_directories(
    dep_libupnpp.get_pkgconfig_variable('includedir') / 'libupnpp',
    'src',
    'scctl_src',
  )
  executable(
    'scctl',
    sources: scctl_sources,
    install: true,
    dependencies: [dep_libupnpp],
    include_directories: scctl_includes,
  )

  install_subdir(
    'web',
    install_dir: get_option('datadir') / 'upmpdcli',
    exclude_directories: '__pycache__',
  )
endif

######################### Install data

upmpdcli_data = files(
  'src/AVTransport.xml',
  'src/ConnectionManager.xml',
  'src/OHCredentials.xml',
  'src/OHInfo.xml',
  'src/OHPlaylist.xml',
  'src/OHProduct.xml',
  'src/OHRadio.xml',
  'src/OHReceiver.xml',
  'src/OHTime.xml',
  'src/OHVolume.xml',
  'src/RenderingControl.xml',
  'src/description.xml',
  'src/icon.png',
  'src/mediaserver/ContentDirectory.xml',
  'src/mediaserver/MS-description.xml',
  'src/presentation.html',
  'src/protocolinfo.txt',
  'src/upmpdcli.conf-dist',
  'src/upmpdcli.conf-xml',
)
install_data(upmpdcli_data, install_dir: get_option('datadir') / 'upmpdcli')

install_data('src/upmpdcli.conf-dist', install_dir: '/etc')

install_subdir(
  'rdpl2stream',
  install_dir: get_option('datadir') / 'upmpdcli',
  exclude_directories: '__pycache__',
  exclude_files: [
    'tststreams.txt',
  ],
)

install_subdir(
  'samplescripts',
  install_dir: get_option('datadir') / 'upmpdcli' / 'src_scripts',
  strip_directory: true,
)

install_subdir(
  'src/radio_scripts',
  install_dir: get_option('datadir') / 'upmpdcli',
  exclude_directories: 'npr',
)

install_subdir(
  'src/mediaserver/cdplugins',
  install_dir: get_option('datadir') / 'upmpdcli',
  exclude_directories: [
    'attic',
    '.deps',
    'uprcl/testrunuprcl.sh',
    'bbc/__pycache__',
    'hra/__pycache__',
    'mother-earth-radio/__pycache__',
    'pycommon/__pycache__',
    'qobuz/__pycache__',
    'qobuz/api/__pycache__',
    'radio-browser/__pycache__',
    'radio-paradise/__pycache__',
    'subsonic/__pycache__',
    'tidal/__pycache__',
    'upradios/__pycache__',
    'uprcl/__pycache__',
  ],
  exclude_files: [
    'abuffer.h',
    'bufxchange.h',
    'cdplugin.hxx',
    'cmdtalk.cpp',
    'cmdtalk.h',
    'curlfetch.cpp',
    'curlfetch.h',
    'netfetch.cpp',
    'netfetch.h',
    'plgwithslave.cxx',
    'plgwithslave.hxx',
    'streamproxy.cpp',
    'streamproxy.h',
    'uprcl/testrunuprcl.sh',
  ],
)

meson.add_install_script('tools/installconfig.sh')

install_man('man/upmpdcli.1')
install_man('man/upmpdcli.conf.5')
