# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *

class RMAPIClientPrivisionWifi(RMAPIClientCalls):
    """
    WIFI related setup
    """
    NETWORK_TYPE_DHCP = "dhcp"
    NETWORK_TYPE_STATIC = "static"

    ENCRYPTION_NONE = "none"
    ENCRYPTION_PSK = "psk"
    ENCRYPTION_PSK2 = "psk2"

    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "provision/wifi"

    def get(self):
        """
        Returns the WIFI configuration
        """
        return self.GET(self.baseUrl)

    def scan(self):
        """
        Initiate a WIFI scan and returns results of the scan.
        """
        return self.GET(self.baseUrl + "/scan")

    def set(self, ssid, encryption, password, dhcp=NETWORK_TYPE_DHCP , ip = None, mask = None, gateway = None, dns = None):
        """
        Sets up the WIFI networks
        """
        data = {
            "ssid": ssid,
            "encryption": encryption,
            "key": password,
            "networkType": dhcp,
            "addressInfo": {
                "ipaddr": ip,
                "netmask": mask,
                "gateway": gateway,
                "dns": dns
            }
        }

        return self.POST(self.baseUrl + "/settings", data)


class RMAPIClientPrivisionCloud(RMAPIClientCalls):
    """
    RainMachine Remote access related setup
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "provision/cloud"

    def get(self):
        """
        Returns the remote access configuration
        """
        return self.GET(self.baseUrl)

    def set(self, email, enabled = True):
        """
        Sets the remote access configuration. This is not fully handled by the current python client.
        More details will be added once Remote Access API is publicily available.
        """
        data = {
            "pendingEmail": email,
            "enable": enabled
        }

        return self.POST(self.baseUrl, data)

    def reset(self):
        """
        Resets remote access configuration.
        """
        return self.POST(self.baseUrl + "/reset")


class RMAPIClientProvision(RMAPIClientCalls):
    """
    RainMachine setup (/provision) API calls
    """
    def __init__(self, restHandler):
        RMAPIClientCalls.__init__(self, restHandler)
        self.baseUrl = "provision"
        self.wifi = RMAPIClientPrivisionWifi(restHandler)
        self.cloud = RMAPIClientPrivisionCloud(restHandler)

    def get(self):
        """
        Returns all configuration settings
        """
        return self.GET(self.baseUrl)

    def set(self, systemData, locationData):
        """
        Sets the configuration settings
        """
        data = {}
        if systemData is not None:
            data["system"] = systemData

        if locationData is not None:
            data["location"] = locationData

        if data:
            return self.POST(self.baseUrl, data)

        return RMAPIClientErrors.PARAMS

    def reset(self, withReboot = False):
        """
        Perform a factory reset of the current device.
        """
        data = {
            "restart": withReboot
        }

        return self.POST(self.baseUrl + "/reset")


# Test only works on localhost which doesn't require auth
if __name__ == "__main__":
    restLocal = RMAPIClientREST(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    provision = RMAPIClientProvision(restLocal)
    print provision.get()
    print provision.wifi.get()
    print provision.wifi.scan()
    print provision.cloud.get()