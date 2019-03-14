# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *

class RMAPIClientDev(RMAPIClientCalls):
    """
    Developer (/dev) API calls
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "dev"

    def getbeta(self):
        """
        Returns "enabled": true if device is subscribed to beta quality updates
        """
        return self.GET(self.baseUrl + "/beta")

    def setbeta(self, enabled):
        """
        Subscribes or unsubscribes the device from the beta update channel
        """
        data = {"enabled": enabled}
        return self.POST(self.baseUrl + "beta", data)


# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    dev = RMAPIClientDev(restLocal)
    print dev.getbeta()
