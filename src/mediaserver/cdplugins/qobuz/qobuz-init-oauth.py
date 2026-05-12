#!/usr/bin/env python3

import sys
import os
import getopt

thisdir=os.path.dirname(__file__)
sys.path.append(os.path.join(thisdir, "../pycommon"))
from upmplgutils import *
from conftree import ConfSimple

from api.bundle import Bundle

import socket
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

## We would like to check the content of the cache config file, but this is complicated because
## it depends on upmpdcli being started as root (cache in /var), or as a regular user (cache in
## ~/.cache). So the following is not used for now.
def check_success():
    input("Please type <CR> when you get the 'successful' page in the browser")
    
    config = ConfSimple(os.path.join(getcachedir("qobuz"), "config"))
    auth_token = config.get("user_auth_token")
    user_id = config.get("user_id")
    if auth_token and user_id:
        print("Successfully got user id and authorization token")
    else:
        print("Seems to have failed")
    

def perform_oauth_login(host, port):
    bundle = Bundle()
    app_id = str(bundle.get_app_id())

    oauth_url_base = (
        f"https://www.qobuz.com/signin/oauth"
        f"?ext_app_id={app_id}"
        
    )
    oauth_url_local = oauth_url_base + f"&redirect_url=http://localhost:{port}/qobuz/oauth/"
    oauth_url_net = oauth_url_base + f"&redirect_url=http://{host}:{port}/qobuz/oauth/"

    print("This script must run on the same machine as upmpdcli")
    print("Open one of the following URLs in your browser to authenticate with Qobuz:")
    print()
    print("- If upmpdcli and the script run on the same machine as the WEB browser, use:")
    print(f"{oauth_url_local}")
    print()
    print("- If the upmpdcli and the script run on a different machine than the browser, use:")
    print(f"{oauth_url_net}")


def msg(s):
    print(f"{s}", file=sys.stderr)
    
###### Main
configfile = "/etc/upmpdcli.conf"
opts = getopt.getopt(sys.argv[1:], "c:")
for opt, arg in opts[0]:
    if opt == "-c":
        configfile = arg

if not os.path.exists(configfile):
    msg("Upmpdcli configuration file not found in the default location (/etc/upmpdcli.conf)")
    msg("Please use the -c option to set the configuration file location")
    sys.exit(1)
os.environ["UPMPD_CONFIG"] = configfile

host = getOptionValue("plgmicrohttphost", get_ip())
port = getOptionValue("plgmicrohttpport", 49149)

perform_oauth_login(host, port)
