# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *

class RMAPIClientMixer(RMAPIClientCalls):
    """
    RainMachine Weather Mixer (/mixer) API calls
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "mixer"

    def get(self, dateStr = None, days = 30):
        """
        Returns RainMachine weather mixer data. If dateStr (YYYY-MM-DD) is specified it returns results
        from that date for specified number of days (default 30 days)
        """
        url = self.baseUrl
        if dateStr is not None:
            url += "/" + dateStr + "/" + str(days)

        return self.GET(url)

# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    mixer = RMAPIClientMixer(restLocal)
    data = mixer.get("2016-05-01", 60)
    print "Mixer %s" % data
