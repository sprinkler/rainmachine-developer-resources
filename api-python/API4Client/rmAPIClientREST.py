# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

import urllib2, os, ssl, json
from RMUtilsFramework.rmLogging import log

class RMAPIClientProtocol:
    """
    RainMachine currently supported protocols
    """
    HTTPS = 1
    HTTP = 2

    @staticmethod
    def getAsString(protocol):
        if protocol == RMAPIClientProtocol.HTTPS:
            return "https://"
        return "http://"


class RMAPIClientCalls(object):
    """
    RainMachine currently supported methods
    """
    def __init__(self, restHandler):
        self.GET = restHandler.get
        self.POST = restHandler.post
        self.REST = restHandler.rest

    @classmethod
    def callList(cls):
        return [attr for attr in dir(cls) if not callable(attr) and not attr.startswith("__") and not attr == "callList"]


class RMAPIClientErrors:
    """
    RainMachine client errors and status codes
    """
    REQ     = {"statusCode": 900, "message": "Can't create request object"}
    OPEN    = {"statusCode": 901, "message": "Can't open URL"}
    JSON    = {"statusCode": 902, "message": "Can't parse JSON"}
    ID      = {"statusCode": 903, "message": "No ID specified"}
    PARAMS  = {"statusCode": 904, "message": "No parameters specified"}


class RMAPIClientREST(object):
    """
    RainMachine REST interface"
    """

    def get(self, apiCall, isBinary = False, extraHeaders = None,  asJSON = True):
        return self.__rest("GET", apiCall, None, isBinary, extraHeaders, self._majorversion, asJSON)

    def post(self, apiCall, data = None, isBinary = False, extraHeaders = None,  asJSON = True):
        return self.__rest("POST", apiCall, data, isBinary, extraHeaders, self._majorversion, asJSON)

    def rest(self, type, apiCall, data = None, isBinary = False, extraHeaders = None,  asJSON = True):
        return self.__rest(type, apiCall, data, isBinary, extraHeaders, self._majorversion, asJSON)

    def __rest(self, type, apiCall, data = None, isBinary = False, extraHeaders = None, majorVersion="", asJSON = True):

        protocol = RMAPIClientProtocol.getAsString(self._protocol)

        apiUrl = protocol + self._host + ":" + self._port + "/api/" + majorVersion + "/"

        if self.token is None:
            url = apiUrl + apiCall
        else:
            url = apiUrl + apiCall + "?access_token=" + self.token

        try:
            req = urllib2.Request(url)
            req.get_method = lambda: type # Force GET/POST depending on type
        except:
            return RMAPIClientErrors.REQ

        if data is not None:
            if isBinary:
                req.add_data(data=data)
            else:
                req.add_data(data=json.dumps(data))

        req.add_header("Content-type", "text/plain")
        req.add_header('User-Agent', "RMAPIClient")

        if extraHeaders is not None:
            for header in extraHeaders:
                req.add_header(header)

        try:
            log.info("REST: %s : %s" % (req.get_method(), req.get_full_url()))
            if self.context is not None:
                r = urllib2.urlopen(req, context=self.context)
            else:
                r = urllib2.urlopen(req)
            data = r.read()
        except Exception, e:
            log.error("Cannot OPEN URL: %s" % e)
            return RMAPIClientErrors.OPEN

        if asJSON:
            try:
                data = json.loads(data)
                return data
            except:
                log.info("Cannot convert reply to JSON.")
                return RMAPIClientErrors.JSON

        return  data

    def __getApiVer(self):
        data = self.__rest("GET", "apiVer")
        if data is not None:
            return data.get('apiVer', None)

        return None

    def __getContext(self):
        try:
            return ssl._create_unverified_context()
        except:
            return None

        return None

    def __init__(self, host="127.0.0.1", port="8080", protocol=RMAPIClientProtocol.HTTPS):
        self.token = None
        self._host = host
        self._port = port
        self._protocol = protocol
        self._apiversion = None
        self._majorversion = ""
        self._minorversion = ""
        self._patchversion = ""
        self.context = self.__getContext()
        self.apiversion = self.__getApiVer()

    @property
    def apiversion(self):
        if self._apiversion is None:
            self._apiversion = self.__getApiVer()

        return self._apiversion

    @apiversion.setter
    def apiversion(self, value):
        if value is not None:
            self._apiversion = value
            self._majorversion, self._minorversion, self._patchversion = self._apiversion.split(".")

if __name__ == "__main__":
    assert RMAPIClientREST("127.2.0.1", "8180").apiversion is None
    assert RMAPIClientREST("127.0.0.1", "8080").apiversion == "4.3.0"
