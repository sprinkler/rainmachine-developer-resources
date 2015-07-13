# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

import sys
import time
import select
from socket import *


ADVERTISE_PORT = 15800
RESPONSE_PORT = 15900
SOCKET_TIMEOUT = 5 # in seconds
BROADCAST = '255.255.255.255'
SCAN_EXPIRE = 10

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
        if not isReceiving:
            sSend.sendto('python discover', (BROADCAST, ADVERTISE_PORT))

        if seenSprinklers and not isReceiving and newSprinklers:
            print "-" * 80
            for mac in seenSprinklers:
                configured = "" if seenSprinklers[mac]["wizard"] == "1" else "(unconfigured)"
                print "%s: %s %s" % (seenSprinklers[mac]["name"], seenSprinklers[mac]["http"], configured)
                newSprinklers = False
                if expireCount <= 0:
                    print "Expiring discovered sprinklers"
                    expireCount = SCAN_EXPIRE
                    seenSprinklers = {}

        ready = select.select([sRecv], [], [], SOCKET_TIMEOUT)
        if ready[0]:
            data, addr = sRecv.recvfrom(1024)

            try:
                proto, mac, name, http, wizard = data.split("||")
            except (TypeError, IndexError, ValueError) as e:
                continue

            isReceiving = True

            if mac not in seenSprinklers:
                seenSprinklers[mac] = {"name": name, "http": http, "wizard": wizard }
                newSprinklers = True

            expireCount -= 1

        else:
            isReceiving = False