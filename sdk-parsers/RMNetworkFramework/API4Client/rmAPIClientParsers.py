# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

import json
from rmAPIClientREST import *


class RMAPIClientParsers(RMAPIClientCalls):
    """
    Weather parser (/parser) API calls
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "parser"

    def get(self, id = None):
        """
        Returns weather parsers parameters and status. If id is not specified it returns data for all existing parsers
        """
        url = self.baseUrl
        if id is not None:
            url += "/" + str(id)

        return self.GET(url)

    def getdata(self, id, dateStr = None, days = None):
        """
        Returns weather data from the specified parser
        """
        url = self.baseUrl + "/" + str(id) + "/data/"

        if dateStr is not None:
            url += dateStr
            if days is not None:
                url += "/" + str(days)

        return self.GET(url)

    def activate(self, id, enabled = True):
        """
        Enables or disables a parser. To be executed by RainMachine a parser should be enabled
        """
        url = self.baseUrl + "/" + str(id) + "/activate"
        data = {"activate" : enabled }
        return self.POST(url, data)

    def delete(self, id):
        """
        Deletes a parser that was uploaded by user.
        """
        url = self.baseUrl + "/" + str(id) + "/delete"
        return self.POST(url)

    def setdefaults(self, id):
        """
        Set default parameters for specified parser
        """
        url = self.baseUrl + "/" + str(id) + "/defaults"
        return self.POST(url)

    def setparams(self, id, params):
        """
        Set the specified parameters for specified parser id
        """
        url = self.baseUrl + "/" + str(id) + "/params"
        try:
            params = json.dumps(params)
            return self.POST(url, params)
        except:
            pass

        return RMAPIClientErrors.JSON

    def run(self, id = -1, withParser = True, withMixer = True, withSimulator = False):
        """
        Forcefully run weather parsers. If id is -1 then all enabled parsers are run.
        If withMixer is true, the RainMachine Weather Mixer will be execute to mix the results from each parsers.
        """
        url = self.baseUrl + "/run"

        data = {
            "parser": withParser,
            "mixer": withMixer,
            "simulator": withSimulator
        }

        if id > -1:
            data["parserId"] = id

        return self.POST(url, data)


# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    parsers = RMAPIClientParsers(restLocal)
    p = parsers.get()
    print "Parsers %s" % p

    data = parsers.getdata(6, "2016-05-01", 60)
    print "Parser 6 Data: %s" % data

    parsers.activate(6, False)
    parsers.activate(6)
    parsers.setparams(6, {"test": False})
    parsers.setdefaults(6)
    parsers.delete(6)
    parsers.run()

