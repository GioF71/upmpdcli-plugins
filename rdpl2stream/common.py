import sys

APPVERSION="0.14"

# user-agent
try:
    import platform
    USER_AGENT = "%s/%s (%s %s; %s/%s (%s))" % (
            "Upmpdcli", APPVERSION, platform.system(), platform.machine(),
            platform.linux_distribution()[0], platform.linux_distribution()[1],
            platform.linux_distribution()[2])
except:
    USER_AGENT = "Upmpdcli/" + APPVERSION

