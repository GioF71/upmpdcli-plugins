AC_INIT([upmpdcli], [1.6.1], [jfd@lesbonscomptes.com],
             [upmpdcli], [http://www.lesbonscomptes.com/upmpdcli])
AC_PREREQ([2.53])
AC_CONFIG_MACRO_DIRS([m4])
AC_CONFIG_SRCDIR([src/upmpd.cxx])
AC_CONFIG_HEADERS([src/config.h])
AH_BOTTOM([#include "src/conf_post.h"])

AM_INIT_AUTOMAKE([1.10 no-define subdir-objects foreign])

if test X"$CXXFLAGS" = X;then
   CXXFLAGS="-std=c++11 -g -O2"
fi
AC_PROG_CXX

# ! Not sure that this is needed for upmpdcli and not only libupnpp
# libupnp is configured with large file support, and we need to do the same,
# else a difference in off_t size impacts struct File_Info and prevents the
# vdir to work. This does make a difference, for exemple, for Raspbian
# on the Raspberry PI. Use the same directives as libupnp's configure.ac
AC_TYPE_SIZE_T
AC_TYPE_OFF_T
AC_DEFINE([_LARGE_FILE_SOURCE], [], [Large files support])
AC_DEFINE([_FILE_OFFSET_BITS], [64], [File Offset size])

#### Libraries
AC_CHECK_LIB([pthread], [pthread_create], [], [])

AC_ARG_ENABLE(confgui, AS_HELP_STRING([--enable-confgui],
              [Enable QT-based configuration editor GUI.]),
              enableQT=$enableval, enableQT="no")
AM_CONDITIONAL(MAKECONFGUI, [test X$enableQT = Xyes])
if test X$enableQT = Xyes ; then
  if test X$QMAKE = X ; then
     QMAKE=qmake
  fi
  case $QMAKE in
    */*) QMAKEPATH=$QMAKE;;
    *) AC_PATH_PROG([QMAKEPATH], $QMAKE, NOTFOUND);;
  esac

  if test X$QMAKEPATH = XNOTFOUND ; then 
     AC_MSG_ERROR([Cannot find the qmake program. Maybe you need to install
  qt development files and tools and/or set the QTDIR environment variable?])
  fi
  AC_CONFIG_FILES(cfgui/upmpdcli-config.pro)
  QMAKE=$QMAKEPATH
  AC_SUBST(QMAKE)
fi

AC_ARG_ENABLE(spotify, AS_HELP_STRING([--disable-spotify],
              [Disable spotify streaming module.]),
              enableSpotify=$enableval, enableSpotify="yes")
AM_CONDITIONAL(ENABLESPOTIFY, [test X$enableSpotify = Xyes])


PKG_CHECK_MODULES([upnpp], [libupnpp], [], [AC_MSG_ERROR([libupnpp not found])])
PKG_CHECK_MODULES([libmpdclient], [libmpdclient], [],
	[AC_MSG_ERROR([libmpdclient not found])])
PKG_CHECK_MODULES([libmicrohttpd], [libmicrohttpd], [],
	[AC_MSG_ERROR([libmicrohttpd not found])])
PKG_CHECK_MODULES([jsoncpp], [jsoncpp], [], [AC_MSG_ERROR([jsoncpp not found])])


AC_ARG_ENABLE(staticlink, AS_HELP_STRING([--enable-staticlink],
              [Enable static link by adding the needed libraries.]),
              enableStaticLink=$enableval, enableStaticLink="no")
if test X$enableStaticLink = Xyes ; then
    PKG_CHECK_MODULES([curl], [libcurl], [], [AC_MSG_ERROR([libcurl])])
    PKG_CHECK_MODULES([expat], [expat], [], [AC_MSG_ERROR([libexpat])])
    PKG_CHECK_MODULES([npupnp], [libnpupnp], [], [AC_MSG_ERROR([libnpupnp])])
	addstaticlibs="$npupnp_LIBS $curl_LIBS $expat_LIBS $libmicrohttpd_LIBS"
else
	addstaticlibs=""
fi


SCCTL_LIBS="$LIBS $libmpdclient_LIBS  $jsoncpp_LIBS  $libmicrohttpd_LIBS $upnpp_LIBS $addstaticlibs "
UPMPDCLI_LIBS="$LIBS $libmpdclient_LIBS  $jsoncpp_LIBS  $libmicrohttpd_LIBS $upnpp_LIBS $addstaticlibs"


if test X$enableSpotify = Xyes; then
   UPMPDCLI_LIBS="$UPMPDCLI_LIBS -ldl "
fi

echo "UPMPDCLI_LIBS=$UPMPDCLI_LIBS"

LIBS=""

#### Functions
AC_LINK_IFELSE(
    [AC_LANG_PROGRAM([#include <math.h>], [double x = exp10(1.0);])],
    [AC_DEFINE([HAVE_EXP10], [1], [Define to 1 if you have the 'exp10' function])],
  [])

dnl AC_CHECK_DECLS([exp10(double)], [], [],
dnl [#include <math.h>])

AC_FUNC_LIBUPNPP_LINNSONGCAST

AC_SUBST(UPMPDCLI_LIBS)
AC_SUBST(SCCTL_LIBS)

AC_CONFIG_FILES([Makefile])
AC_OUTPUT
