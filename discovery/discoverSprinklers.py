# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

import sys
import time
import select
from socket import *
from pprint import pprint


ADVERTISE_PORT = 15800
RESPONSE_PORT = 15900
SOCKET_TIMEOUT = 2 # in seconds
BROADCAST = '255.255.255.255'
SCAN_EXPIRE = 20

seenSprinklers = {}

if __name__ == "__main__":
    # Sender
    sSend = socket(AF_INET, SOCK_DGRAM)
    sSend.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sSend.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    # Receiver
    sRecv = socket(AF_INET, SOCK_DGRAM)
    sRecv.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sRecv.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    sRecv.settimeout(SOCKET_TIMEOUT)
    sRecv.bind(('', RESPONSE_PORT))
    isReceiving = False
    expireCount = SCAN_EXPIRE

    while True:
        if not isReceiving and expireCount == SCAN_EXPIRE:
            print "Sending discover..."
            sSend.sendto('python discover', (BROADCAST, ADVERTISE_PORT))

        ready = select.select([sRecv], [], [], SOCKET_TIMEOUT)

        if len(ready[0]) > 0:
            data, addr = sRecv.recvfrom(1024)
            isReceiving = True

            try:
                props = data.split("||")
                if len(props) > 4: # SPK2/3
                    proto, mac, name, http, wizard = props
                else: # SPK 1 or bust
                    proto, mac, name, http = props
                    wizard = "1"
            except (TypeError, IndexError, ValueError) as e:
                print "Error parsing data from socket %s" % data
                continue

            if mac not in seenSprinklers:
                seenSprinklers[mac] = {"name": name, "http": http, "wizard": wizard }
                newSprinklers = True
        else:
            isReceiving = False
            expireCount -= SOCKET_TIMEOUT

        if expireCount <= 0:
            print "Expiring discovered sprinklers"
            expireCount = SCAN_EXPIRE
            seenSprinklers = {}
            continue

        if seenSprinklers and not isReceiving and newSprinklers:
            print "-" * 80
            for mac in seenSprinklers:
                try:
                    configured = "(configured)" if seenSprinklers[mac]["wizard"] == "1" else "(unconfigured)"
                    print "%-25.25s: \t\t%s \t%s" % (seenSprinklers[mac]["name"], seenSprinklers[mac]["http"], configured)
                    newSprinklers = False
                except Exception, e:
                    print "Exception %s %s" % (e, seenSprinklers)
                    continue
            print "-" * 80
