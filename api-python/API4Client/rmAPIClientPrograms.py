# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *

class RMAPIClientPrograms(RMAPIClientCalls):
    """
    RainMachine Schedules/Programs (/program) API calls
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "program"

    def get(self, id = None):
        """
        Returns a list of all programs available on device
        """
        url = self.baseUrl
        if id is not None:
            url += "/" + str(id)
        return self.GET(url)

    def nextrun(self):
        """
        Returns a list with the date/time for the next run of all programs.
        """
        return self.GET(self.baseUrl + "/nextrun")

    def set(self, data, id = None):
        """
        Creates or modified a program. If id is not specified a new program will be created with the settings
        specified. The data parameter should follow the structure presented here:
        http://docs.rainmachine.apiary.io/#reference/programs
        """
        url = self.baseUrl
        if id is not None:
            url += "/" + str(id)
        return self.POST(url, data)

    def delete(self, id):
        """
        Deletes a program with specified id
        """
        if id is not None:
            url = self.baseUrl + "/" + str(id) + "/delete"
            return self.POST(url)
        return None

    def start(self, id):
        """
        Manually starts watering for specified program
        """
        if id is not None:
            url = self.baseUrl + "/" + str(id) + "/start"
            return self.POST(url)
        return None

    def stop(self, id):
        """
        Removes specified program from watering queue
        """
        if id is not None:
            url = self.baseUrl + "/" + str(id) + "/stop"
            return self.POST(url)
        return None


# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    import time
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    programs = RMAPIClientPrograms(restLocal)
    data = programs.get()
    print programs.nextrun()
    print programs.start(1)
    print programs.stop(1)

    assert data.get('programs', None) is not None