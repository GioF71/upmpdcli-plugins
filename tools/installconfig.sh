#!/bin/sh

configfile=${DESTDIR}/etc/upmpdcli.conf
configsource=${MESON_SOURCE_ROOT}/src/upmpdcli.conf-dist

test -f  "$configfile" || (cp "$configsource" "$configfile" && chmod 600 "$configfile")
