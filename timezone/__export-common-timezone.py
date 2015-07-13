#!/usr/bin/python

import os
import json
from pytz import common_timezones

timezone = {}
of = open("rmTimeZoneDB.py", "w")
of.write("# Common Timezones for use with RainMachine and OpenWRT TZ env var\n")
of.write("# Automatically generated from zoneinfo files by export-common-timezone.py\n")

of.write("\n\nrmTimeZoneDB = {\n")

for i in common_timezones:
    print i
    f = open(os.path.join("zoneinfo", i), 'rb')
    l = f.readlines()
    timezone[i] = l[-1].rstrip()
    of.write("\t\"%s\":\t\"%s\",\n" % (i, timezone[i]))

of.write("}\n")

json.dump(timezone, open("rmTimeZoneDB.json", "w"), indent=4, sort_keys=True)



