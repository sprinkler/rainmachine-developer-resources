# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>
from rmAPIClientREST import *

class RMAPIClientDiag(RMAPIClientCalls):
    """
    Diagnostics (/diag) API calls
    """

    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "diag"

    def get(self):
        """
        Returns system diagnostics
        """
        return self.GET(self.baseUrl)

    def getupload(self):
        """
        Returns diagnostic upload status
        """
        return self.GET(self.baseUrl + "/upload")

    def startupload(self):
        """
        Starts diagnostic upload that will send the log files and databases to RainMachine support server
        """
        return self.POST(self.baseUrl + "/upload")

    def getlog(self):
        """
        Returns the RainMachine log file
        """
        return self.GET(self.baseUrl + "/log")

    def setloglevel(self, level):
        """
        Sets the RainMachine log level: >=20 is INFO and <=10 is DEBUG
        """
        data = {
            "level": level
        }
        return self.POST(self.baseUrl + "/log/level")

# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    diag = RMAPIClientDiag(restLocal)
    print diag.get()
    print diag.getlog()
    print diag.startupload()
    print diag.getupload()
    import time
    time.sleep(1)

    print diag.getupload()
