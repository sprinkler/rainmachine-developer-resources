# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *

class RMAPIClientWatering(RMAPIClientCalls):
    """
    RainMachine Watering (/watering) API calls
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "watering"

    def getzone(self):
        """
        Returns the zone that is currently being watered
        """
        return self.GET(self.baseUrl + "/zone")

    def getprogram(self):
        """
        Returns the progams that watered or will water today
        """
        return self.GET(self.baseUrl + "/program")

    def getqueue(self):
        """
        Returns the watering queue. The watering queue contains all zones that are scheduled to run and their remaining
        durations
        """
        return self.GET(self.baseUrl + "/queue")

    def getpast(self, dateStr = None, days = 30):
        """
        Returns the evapotranspiration and precipitation forecast used by the already run programs
        """
        url = self.baseUrl + "/past"
        if dateStr is not None:
            url += "/" + dateStr + "/" + str(days)
        return self.GET(url)

    def getaw(self, dateStr = None, days = 30):
        """
        Returns the available water (in soil) for each zone and each program
        """
        url = self.baseUrl + "/available"
        if dateStr is not None:
            url += "/" + dateStr + "/" + str(days)
        return self.GET(url)

    def getlog(self, withDetails = False, simulated = False, dateStr = None, days = 30):
        """
        Returns the past watering log.
        """
        url = self.baseUrl + "/log"

        if simulated:
            url += "/simulated"
        if withDetails:
            url += "/details"
        if dateStr is not None:
            url += "/" + dateStr + "/" + str(days)

        return self.GET(url)

    def stopall(self):
        """
        Removes all zones from watering queue. This stop current watering completely.
        """
        return self.POST(self.baseUrl + "/stopall")


# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    watering = RMAPIClientWatering(restLocal)

    print watering.getqueue()
    print watering.getzone()
    print watering.getprogram()
    print watering.getpast()
    print watering.getaw()
    print watering.getlog(withDetails=True, dateStr="2016-06-01", days=20)
    watering.stopall()



