# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from rmAPIClientREST import *
from rmAPIClientAuth import *
from rmAPIClientDailyStats import *
from rmAPIClientDev import *
from rmAPIClientDiag import *
from rmAPIClientMachine import *
from rmAPIClientMixer import *
from rmAPIClientParsers import *
from rmAPIClientPrograms import *
from rmAPIClientProvision import *
from rmAPIClientRestrictions import *
from rmAPIClientWatering import *
from rmAPIClientZones import *

class RMAPIClientState:
    """
    Used to cache API calls responses.
    """
    def __init__(self):
        self.cachedData = {}

class RMAPIClient(object):
    """
    RainMachine REST API Python wrapper. All function calls returns the data as a python dictionary.
    Calls and their returns are explained here: http://docs.rainmachine.apiary.io/
    """
    def __init__(self, host, port, protocol=RMAPIClientProtocol.HTTP):
        self._host = host
        self._port = port
        self._protocol = protocol

        self.state = RMAPIClientState()
        self.rest = RMAPIClientREST(self._host, self._port, self._protocol)

        #self.apiversion = self.rest.apiversion

        self.auth = RMAPIClientAuth(self.rest)
        self.dailystats = RMAPIClientDailyStats(self.rest)
        self.dev = RMAPIClientDev(self.rest)
        self.machine = RMAPIClientMachine(self.rest)
        self.diag = RMAPIClientDiag(self.rest)
        self.mixer = RMAPIClientMixer(self.rest)
        self.parsers = RMAPIClientParsers(self.rest)
        self.programs = RMAPIClientPrograms(self.rest)
        self.provision = RMAPIClientProvision(self.rest)
        self.restrictions = RMAPIClientRestrictions(self.rest)
        self.watering = RMAPIClientWatering(self.rest)
        self.zones = RMAPIClientZones(self.rest)

    @property
    def host(self):
        return self._host

    @host.setter
    def host(self, value):
        self._host = value
        self.rest = RMAPIClientREST(self._host, self._port, self._protocol)

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self,value):
        self._port = value
        self.rest = RMAPIClientREST(self._host, self._port, self._protocol)

    @property
    def protocol(self):
        return self._protocol

    @protocol.setter
    def port(self,value):
        self._protocol = value
        self.rest = RMAPIClientREST(self._host, self_protocol, self._protocol)


    def getAllMethods(self):
        """
        Returns all methods from all submodules. This is used in RMRules to build actions.
        Doesn't work for clases with have other classes as objects (see provision)
        """
        def asTuple(key, name):
            method = self.__getattribute__(key).__getattribute__(name)
            method_argc = method.__code__.co_argcount
            method_params = method.__code__.co_varnames[:method_argc]
            return (key + "_" + name, method)

        allMethods = []

        allMethods += [asTuple("auth", name) for name in self.auth.callList()]
        allMethods += [asTuple("dailystats", name) for name in self.dailystats.callList()]
        allMethods += [asTuple("dev", name) for name in self.dev.callList()]
        allMethods += [asTuple("machine", name) for name in self.machine.callList()]
        allMethods += [asTuple("diag", name) for name in self.diag.callList()]
        allMethods += [asTuple("mixer", name) for name in self.mixer.callList()]
        allMethods += [asTuple("parsers", name) for name in self.parsers.callList()]
        allMethods += [asTuple("programs", name) for name in self.programs.callList()]
        allMethods += [asTuple("provision", name) for name in self.provision.callList()]
        allMethods += [asTuple("restrictions", name) for name in self.restrictions.callList()]
        allMethods += [asTuple("watering", name) for name in self.watering.callList()]
        allMethods += [asTuple("zones", name) for name in self.zones.callList()]

        return allMethods

if __name__ == "__main__":
    httpsClient = RMAPIClient(host="127.0.0.1", port="8080", protocol=RMAPIClientProtocol.HTTPS)
    exit(1)
    assert httpsClient.auth.login('admin', True) == True
    assert str(httpsClient.auth.totp()).isdigit()
    assert httpsClient.programs.get() is not None

