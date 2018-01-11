# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>

import time

from API4Client.rmAPIClient import *

client = RMAPIClient(host="127.0.0.1", port="18080")

provision = client.provision.get()
zones = client.zones.get()
programs = client.programs.get()

if "system" in provision:
    print provision["system"]["netName"]

if "zones" in zones:
    print "Zones:"
    for z in zones["zones"]:
        print "\t%d.%s" % (z["uid"],z["name"])

if "programs" in programs:
    print "Programs:"
    for p in programs["programs"]:
        print "\t%d.%s" % (p["uid"],p["name"])

print "Zones in watering queue: "

waterzones = client.watering.getzone()
if "zones" in waterzones:
    for z in waterzones["zones"]:
        if z["state"] == 1:
            print "%d.%s is watering now" % (z["uid"],z["name"])
        elif z["state"] == 2:
            print "%d.%s is pending" % (z["uid"],z["name"])



# Set area of zone 1 to 100 square meters and set zone 1 name as "Grass Front" and make it active
client.zones.set(1, {"name": "Grass Front", "active": True}, {"area": 100})


