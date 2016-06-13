# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmCurrentDayTimestamp
from RMParserFramework.rmParserManager import  RMParserManager
import urllib2, json, time, ssl
from urllib import urlencode

class Netatmo(RMParser):

    parserName = "Netatmo Parser"
    parserDescription = "Weather observations from NetAtmo personal weather station"
    parserForecast = False
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600

    refreshToken = None
    clientID = None
    clientSecret = None
    username = None
    password = None

    params = { "username": ""
              , "password": ""
              , "useSpecifiedModules" : False
              , "specificModules" : ''
              , "_availableModules" : []
              }

    baseURL = "https://api.netatmo.com/"
    authReq = baseURL + "oauth2/token"
    getUserReq = baseURL + "api/getuser"
    deviceListReq = baseURL + "api/getstationsdata"

    accessTokenExpiration = 0
    accessToken = None
    refreshToken = None

    jsonData = None

    def perform(self):

        self.clientSecret = ""
        self.clientID = ""

        if self.username is None:
            self.username = self.params["username"]
            self.password = self.params["password"]

        if self.password is None or self.username is None:
            log.info("Cannot login: no username or password provided")
            self.lastKnownError = "Error: Invalid username or password"
            return

        if self.username is not self.params["username"]:
            self.username = self.params["username"]
            self.password = self.params["password"]
            self.clientOauth()

        if self.accessToken is None:
            self.clientOauth()
        else:
            self.renewAccesTokenIfNeeded()

        if self.accessToken is None:
            log.info("Cannot login: invalid oauth")
            self.lastKnownError = "Error: Invalid username or password"
            return

        self.getData()

        tsStartOfDayUTC = rmCurrentDayTimestamp()

        specifiedModules = []
        if self.params["useSpecifiedModules"]:
            modulesString = self.params["specificModules"]
            specifiedModules = modulesString.split(',')
            specifiedModules = [item.strip() for item in specifiedModules]

        for device in self.jsonData["body"]["devices"][0:1]:
            name = device["station_name"] #put as output parameter?
            [llat, llon] = device["place"]["location"] #use for max distance
            modules = device["modules"]
            rh = 0
            temp = 0
            maxTemp = 0
            minTemp = 0
            rain = 0
            wind = 0
            tsTemp = None
            tsWind = None
            tsRain = None
            idxTemp = 0
            idxWind = 0
            idxRain = 0
            self.params["_availableModules"] = []
            for module in modules:
                moduleName = 'unnamed'
                try:
                    moduleName = module["module_name"]
                except:
                    pass
                moduleID = module["_id"]
                self.params["_availableModules"].append([moduleName , moduleID] )
                moduleDataType = module["data_type"]

                if self.params["useSpecifiedModules"]:
                    if moduleID not  in specifiedModules:
                        continue
                elif "outdoor" not in moduleName.lower() and ("Rain" not in moduleDataType) and ("Wind" not in moduleDataType):
                    continue
                try:
                    recordedRain = self.__toFloat(module["dashboard_data"]["Rain"]) #measured in C
                    tsRecordedRain = self.__toInt(module["dashboard_data"]["time_utc"])
                    if tsRecordedRain < tsStartOfDayUTC:
                        continue
                    tsRain = max(tsRecordedRain, tsRain)
                    rain += recordedRain
                    idxRain+=1
                except:
                    pass
                try:
                    recordedWind = self.__toFloat(module["dashboard_data"]["WindStrength"])
                    tsRecordedWind = self.__toInt(module["dashboard_data"]["time_utc"])
                    if tsRecordedWind < tsStartOfDayUTC:
                        continue
                    tsWind = max(recordedWind, tsWind)
                    wind += recordedWind
                    idxWind+=1
                except:
                    pass
                try:
                    recordedTemp = self.__toFloat(module["dashboard_data"]["Temperature"])
                    tsRecordedTemp = self.__toInt(module["dashboard_data"]["time_utc"])

                    if tsRecordedTemp < tsStartOfDayUTC :
                        continue

                    tsTemp = max(tsRecordedTemp, tsTemp)
                    maxTemp += self.__toFloat(module["dashboard_data"]["max_temp"])
                    minTemp += self.__toFloat(module["dashboard_data"]["min_temp"])
                    rh += self.__toFloat(module["dashboard_data"]["Humidity"]) #measured in %
                    temp += recordedTemp

                    idxTemp+=1
                except:
                    pass

            if idxTemp > 0 and tsTemp > tsStartOfDayUTC:
                self.addValue(RMParser.dataType.TEMPERATURE, tsStartOfDayUTC, temp/idxTemp)
                self.addValue(RMParser.dataType.MINTEMP, tsStartOfDayUTC, minTemp/idxTemp)
                self.addValue(RMParser.dataType.MAXTEMP, tsStartOfDayUTC, maxTemp/idxTemp)
                self.addValue(RMParser.dataType.RH, tsStartOfDayUTC, rh/idxTemp)
            if idxWind > 0 and tsWind > tsStartOfDayUTC:
                self.addValue(RMParser.dataType.WIND, tsStartOfDayUTC, wind/idxWind)
            if idxRain > 0 and tsRain > tsStartOfDayUTC:
                self.addValue(RMParser.dataType.RAIN, tsStartOfDayUTC, rain/idxRain)

        for parserCfg in RMParserManager.instance.parsers:
            if self.parserName is parserCfg.name:
                RMParserManager.instance.setParserParams(parserCfg.dbID, self.params)
                break

    def renewAccesTokenIfNeeded(self):
        try:
            if self.accessTokenExpiration < time.time():
                postParams = {
                    "grant_type" : "refresh_token",
                    "refresh_token" : self.refreshToken,
                    "client_id" : self.clientID,
                    "client_secret" : self.clientSecret
                }
                response = self.postRequest(self.authReq, postParams)
                self.accessToken = response['access_token']
                self.refreshToken = response['refresh_token']
                self.accessTokenExpiration = int(response['expire_in']) + time.time()
        except:
            log.debug("Failed to refresh token")

    def clientOauth(self):
        postParams = {
            "grant_type" : "password",
            "client_id" : self.clientID,
            "client_secret" : self.clientSecret,
            "username" : self.username,
            "password" : self.password,
            "scope" : "read_station"
         }
        try:
            resp = self.postRequest(self.authReq, postParams)
            self.accessToken = resp['access_token']
            self.refreshToken = resp['refresh_token']
            self.accessTokenExpiration = int(resp['expire_in']) + time.time()
        except:
            log.debug("Failed to get oauth token")

    def getData(self):
        postParams = {
            "access_token" : self.accessToken,
            }
        self.jsonData = self.postRequest(self.deviceListReq, postParams)


    def postRequest(self, url, params):
        params = urlencode(params)
        headers = {"Content-Type" : "application/x-www-form-urlencoded;charset=utf-8"}
        req = urllib2.Request(url=url, data=params, headers=headers)
        resp = None

        try:
            resp = urllib2.urlopen(req).read()
        except urllib2.URLError, e:
            log.debug(e)
            if hasattr(ssl, '_create_unverified_context'): #for mac os only in order to ignore invalid certificates
                try:
                    context = ssl._create_unverified_context()
                    resp = urllib2.urlopen(req, context=context).read()
                except Exception, e:
                    log.exception(e)
                    return None
            else:
                return None

        return json.loads(resp)

    def __toFloat(self, value):
        try:
            if value is None:
                return value
            return float(value)
        except:
            return None

    def __toInt(self, value):
        try:
            if value is None:
                return value
            return int(value)
        except:
            return None

#aa = Netatmo()
#aa.perform()