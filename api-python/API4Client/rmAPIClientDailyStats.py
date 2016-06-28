# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *


class RMAPIClientDailyStats(RMAPIClientCalls):
    """
    Daily statistics (/dailystats) API calls
    """

    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "dailystats"

    def get(self, withDetails = False, dateString = None):
        """
        Returns future daily watering statistics, if withDetails is True then it will output statistics for each
        zone on each program 7 days in the future.
        """
        url = self.baseUrl
        if withDetails:
            url += "/details"

        if dateString is not None:
            url += "/" + dateString

        return self.GET(url)



# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    dailystats = RMAPIClientDailyStats(restLocal)
    stats = dailystats.get(withDetails=True)
    print "Daily stats %s" % stats