#!/bin/sh

# Run the uprcl-app without an upmpdcli parent and no need to install
# Used primarily to debug the DB construction.

msg() {
	echo $* 1>&2
}
fatal() {
	msg $*;	exit 1
}
usage() {
	msg Must be run in cdplugins/uprcl
	fatal Usage: runuprcl.sh "<topaudiodir>"
}

test -f uprcl-app.py || usage

test $# = 1 || usage

topaudio=$1

export UPMPD_PATHPREFIX=/uprcl
export UPMPD_FNAME=uprcl-test

confdir=/tmp/uprcl-test-confdir
test -d ${confdir} ||  mkdir ${confdir}

configfile=${confdir}/uprcl-test.conf

cat > $configfile <<EOF
uprcluser = bugsbunny
uprclautostart = 1
uprclmediadirs = ${topaudio}
uprclhostport = 192.168.4.4:9099
uprcltitle = TEST UPRCL
uprclconfdir = ${confdir}
uprclminimconfig = /home/source/minimserver/data/minimserver.config
EOF

export UPMPD_CONFIG=${configfile}
curd=`pwd`
export PYTHONPATH="$curd:$curd/../pycommon"

./uprcl-app.py

