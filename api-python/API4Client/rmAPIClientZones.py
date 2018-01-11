# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *

class RMAPIClientZones(RMAPIClientCalls):
    """
    RainMachine Zones (/zone) API calls
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "zone"

    def get(self, id = None):
        """
        Returns the list of zones and their basic setup. If id is specified a single zone is returned
        """
        url = self.baseUrl
        if id is not None:
            url += "/" + str(id)
        return self.GET(url)

    def properties(self, id):
        """
        Returns advanced properties for a zone.
        """
        url = self.baseUrl
        if id is not None:
            url += "/" + str(id)

        url += "/properties"
        return self.GET(url)

    def start(self, id, duration = 300):
        """
        Manually starts watering for specified zone and duration. If duration is not specified
        zone is started with a 5 minutes duration.
        """
        if id is not None:
            url = self.baseUrl + "/" + str(id) + "/start"
            data = {"time": duration}
            return self.POST(url, data)

        return RMAPIClientErrors.ID

    def stop(self, id):
        """
        Stops watering the specified zone.
        """
        if id is not None:
            url = self.baseUrl + "/" + str(id) + "/stop"
            return self.POST(url)

        return RMAPIClientErrors.ID

    def set(self, id, properties, advanced = None):
        """
        Sets the properties of specified zone.
        """
        if id is not None:
            url = self.baseUrl + "/" + str(id) + "/properties"
            data = properties

            if advanced is not None:
                data["waterSense"] = advanced

            return self.POST(url, data)

        return RMAPIClientErrors.ID


# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    zones = RMAPIClientZones(restLocal)
    data = zones.get()
    testZoneName = "Zone from RMAPIClient"
    assert data.get('zones', None) is not None

    print data
    print zones.get(1)
    print zones.start(1)
    print zones.stop(1)
    print zones.properties(1)
    print zones.set(2, {"name": testZoneName})
    zone2 = zones.get(2)
    assert zone2.get('name', "")  == testZoneName

