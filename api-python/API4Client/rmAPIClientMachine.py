# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *

class RMAPIClientMachine(RMAPIClientCalls):
    """
    Machine (/machine) related API calls
    """

    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "machine"

    def gettime(self):
        """
            Returns the date and time on device:
            "appDate": "2016-06-27 04:21:57"
        """
        return self.GET(self.baseUrl + "/time")

    def settime(self, datetimeStr):
        """
        Sets the device time, datetimeStr format is %Y-%m-%d %H:%M
        """
        return self.POST(self.baseUrl + "/time", datetimeStr)


    def getupdate(self):
        """
        Returns the status of update process and the available packages updates.
        updateStatus can take the following values:
        - STATUS_IDLE = 1
        - STATUS_CHECKING = 2
        - STATUS_DOWNLOADING = 3
        - STATUS_UPGRADING = 4
        - STATUS_ERROR = 5
        - STATUS_REBOOT = 6
        """
        return self.GET(self.baseUrl + "/update")

    def checkupdate(self):
        """
        Checks if any updates are available, the results are obtained by getupdate() function
        """
        return self.POST(self.baseUrl + "/check")


    def update(self):
        """
        Starts the update process, and will reboot device when the update has finished.
        Ongoing status can be obtaining by polling with getupdate() function
        """
        return self.POST(self.baseUrl + "/update")

    def setssh(self, enabled):
        """
        Enables or disables SSH daemon
        """
        data = {"enabled": enabled}
        return self.POST(self.baseUrl + "/ssh", data)

    def settouch(self, enabled):
        """
        Enables or disables the touch controls on Mini-8 device. This is useful if you either want to prevent
        local access to the device, or if you want to control the touch screen with an external program instead of the
        built in functionality
        """
        data = {"enabled": enabled}
        return self.POST(self.baseUrl + "/touch", data)

    def setleds(self, on):
        """
        Turns on or off the Mini-8 touch panel LED lights
        """
        data = {"enabled": on}
        return self.POST(self.baseUrl + "/lightleds", data)

    def shutdown(self):
        """
        Shutsdown the device
        """
        return self.POST(self.baseUrl + "/shutdown")

    def restart(self):
        """
        Restarts the RainMachine application without rebooting the device
        """
        return self.POST(self.baseUrl + "/restart")

    def reboot(self):
        """
        Reboots the device
        """
        return self.POST(self.baseUrl + "/reboot")

# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    machine = RMAPIClientMachine(restLocal)
    print machine.gettime()
    print machine.getupdate()

