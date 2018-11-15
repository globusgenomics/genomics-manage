#!/usr/bin/env python
import sys
import subprocess

##########################
# Config

# check volume usage
# Format: Volume: [Waring_percent, Critical_percent] (Waring_percent < Critical_percent)
VOLUMES_TO_CHECK = {
                    "/": [98, 100],
                    "/scratch": [90, 95]
                   }
##########################


CRITICAL = False
WARNING = False
to_print = "This is a report from Globus Genomics: "


for volume, check_points in VOLUMES_TO_CHECK.iteritems():
    cmd = ['df', '--output=pcent', volume]
    output = subprocess.Popen( cmd, stdout=subprocess.PIPE ).communicate()[0]
    output = filter(None, output.split("\n"))
    pcent = int(output[-1].translate(None, '%').strip())
    if pcent >= check_points[1]:
        CRITICAL = True
        to_print = to_print + "- volume {0} usage: {1}% ".format(volume, pcent)
    elif pcent >= check_points[0]:
        WARNING = True
        to_print = to_print + "- volume {0} usage: {1}% ".format(volume, pcent)

if CRITICAL:
    print to_print
    sys.exit(2)
elif WARNING:
    print to_print
    sys.exit(1)
else:
    print to_print + "volume status ok"
    sys.exit(0)
