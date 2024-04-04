project(
  'upmpdcli',
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
     'src/ohservice.cxx',
     'src/ohservice.hxx',
     'src/ohsndrcv.cxx',
     'src/ohsndrcv.hxx',
     'src/ohtime.cxx',
     'src/ohtime.hxx',
     'src/ohvolume.cxx',
     'src/ohvolume.hxx',
     'src/pathut.cpp',
     'src/pathut.h',
     'src/protocolinfo.cxx',
     'src/protocolinfo.hxx',
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
  'src/pathut.cpp',
  'src/smallut.cpp',
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

########################### Optional scctl songcast control and web interface

if get_option('scctl')

   scctl_sources = [
     'scctl_src/scctl.cpp',
     'src/netcon.cpp',
     'src/smallut.cpp',
     'src/upmpdutils.cxx',
   ]

  scctl_includes = [dep_libupnpp.get_pkgconfig_variable('includedir') / 'libupnpp', 'src',
    'scctl_src']
  scctl = executable(
    'scctl',
    sources: scctl_sources,
    install: true,
    dependencies: [dep_libupnpp],
    include_directories: scctl_includes,
  )

install_subdir('web',
  install_dir: get_option('datadir') / 'upmpdcli',
  exclude_directories: '__pycache__',
)

endif

######################### Install data

upmpdcli_data = [
  'src/description.xml',
  'src/AVTransport.xml',
  'src/RenderingControl.xml',
  'src/ConnectionManager.xml',
  'src/OHProduct.xml',
  'src/OHCredentials.xml',
  'src/OHInfo.xml',
  'src/OHTime.xml',
  'src/OHVolume.xml',
  'src/OHPlaylist.xml',
  'src/OHReceiver.xml',
  'src/OHRadio.xml',
  'src/mediaserver/ContentDirectory.xml',
  'src/mediaserver/MS-description.xml',
  'src/protocolinfo.txt',
  'src/presentation.html',
  'src/icon.png',
  'src/upmpdcli.conf-dist',
  'src/upmpdcli.conf-xml',
]
install_data(upmpdcli_data, install_dir : get_option('datadir') / 'upmpdcli')

install_data('src/upmpdcli.conf-dist', install_dir: '/etc')

install_subdir('rdpl2stream', 
    install_dir: get_option('datadir') / 'upmpdcli',
    exclude_directories: '__pycache__',
    exclude_files: ['tststreams.txt',]
)

install_subdir('samplescripts', 
    install_dir: get_option('datadir') / 'upmpdcli' / 'src_scripts',
    strip_directory: true,
)

install_subdir('src/radio_scripts',
    install_dir: get_option('datadir') / 'upmpdcli',
    exclude_directories: 'npr',
)

install_subdir('src/mediaserver/cdplugins',
    install_dir: get_option('datadir') / 'upmpdcli',
    exclude_directories: ['attic', '.deps', 'uprcl/testrunuprcl.sh',
      'bbc/__pycache__', 'hra/__pycache__', 'mother-earth-radio/__pycache__', 
      'pycommon/__pycache__', 'qobuz/__pycache__', 'qobuz/api/__pycache__',
      'radio-browser/__pycache__', 'radio-paradise/__pycache__', 'subsonic/__pycache__',
      'tidal/__pycache__', 'upradios/__pycache__', 'uprcl/__pycache__', ],
    exclude_files: ['abuffer.h','bufxchange.h', 'cdplugin.hxx', 'cmdtalk.cpp', 'cmdtalk.h', 
     'curlfetch.cpp', 'curlfetch.h', 'netfetch.cpp', 'netfetch.h', 'plgwithslave.cxx',
     'plgwithslave.hxx', 'streamproxy.cpp', 'streamproxy.h', 'uprcl/testrunuprcl.sh'],
    )

meson.add_install_script('tools/installconfig.sh')

install_man('man/upmpdcli.1')
install_man('man/upmpdcli.conf.5')
