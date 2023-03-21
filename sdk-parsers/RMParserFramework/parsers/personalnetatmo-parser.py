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

class PersonalNetatmo(RMParser):

    parserName = "PersonalNetatmo Parser"
    parserDescription = "Weather observations from NetAtmo personal weather station"
    parserForecast = False
    parserHistorical = True
    parserEnabled = False
    parserDebug = False
    parserInterval = 6 * 3600

    refreshToken = None
    username = None
    password = None

    params = {
        "username": ""
        , "password": ""
        , "clientID": ""
        , "clientSecret": ""
        , "useSpecifiedModules": False
        , "specificModules": ''
        , "_availableModules": []
    }

    baseURL = "https://api.netatmo.com/"
    authReq = baseURL + "oauth2/token"
    getUserReq = baseURL + "api/getuser"
    deviceListReq = baseURL + "api/getstationsdata"
    getMeasureUrl = baseURL + "api/getmeasure"

    accessTokenExpiration = 0
    accessToken = None
    refreshToken = None

    jsonData = None

    def perform(self):

        self.clientSecret = self.params["clientSecret"]
        self.clientID = self.params["clientID"]

        if self.username is None:
            self.username = self.params["username"]
            self.password = self.params["password"]

        if self.password is None or self.username is None:
            self.lastKnownError = "Error: Invalid username or password."
            log.error(self.lastKnownError)
            return

        if self.username != self.params["username"]:
            self.username = self.params["username"]
            self.password = self.params["password"]
            self.clientOauth()

        # Try to refresh the access token first if a previous one exists
        if self.accessToken is not None:
            self.renewAccesTokenIfNeeded()

        if self.accessToken is None:
            log.info("Doing full auth")
            self.clientOauth()

        if self.accessToken is None:
            self.lastKnownError = "Error: Authentication failure"
            log.error(self.lastKnownError)
            return

        self.getData()

        tsStartOfDayUTC = rmCurrentDayTimestamp()

        if len(self.jsonData["body"]["devices"]) == 0:
             self.lastKnownError = "No NetAtmo devices found"
             log.error(self.lastKnownError)
             return

        # Get available modules from returned json
        self.buildAvailableModules()

        # Build the list of user specified modules
        specifiedModules = []
        if self.params["useSpecifiedModules"]:
            modulesString = self.params["specificModules"]
            specifiedModules = modulesString.split(',')
            specifiedModules = [item.strip() for item in specifiedModules]

        # Only use the first reported device which should be user device if user didn't specify modules
        # Otherwise we will have multiple reports that we need to collate data from multiple devices
        # and multiple modules

        if self.params["useSpecifiedModules"]:
            for device in self.jsonData["body"]["devices"]:
                self.getDeviceData(device, specifiedModules)
        else:
            self.getDeviceData(self.jsonData["body"]["devices"][0], specifiedModules)

    def buildAvailableModules(self):
        self.params["_availableModules"] = []
        for device in self.jsonData["body"]["devices"]:
            if "modules" not in device:
                log.debug("Device doesn't have modules")
                continue

            modules = device["modules"]
            deviceName = device.get("station_name", "Unnamed Station")
            deviceLoc = str(round(device["place"]["location"][0], 2)) + "," + str(round(device["place"]["location"][1], 2))
            for module in modules:
                moduleName = 'unnamed'
                try:
                    moduleName = module["module_name"]
                except:
                    pass
                moduleID = module["_id"]
                moduleDataType = module["data_type"]

                if "CO2" in moduleDataType:
                    continue

                if ("Temperature" not in moduleDataType) and ("Rain" not in moduleDataType) and ("Wind" not in moduleDataType):
                    continue

                self.params["_availableModules"].append([moduleName, moduleID, deviceName, deviceLoc])

    def getDeviceData(self, device, specifiedModules):
        if "modules" not in device:
            log.error("Device has no modules to get outdoor data")
            return

        [llat, llon] = device["place"]["location"] # use for max distance
        deviceID = device["_id"]
        modules = device["modules"]
        minRH = 0
        maxRH = 0
        # minPress = 0
        # maxPress = 0
        maxTemp = 0
        minTemp = 0
        rain = 0
        wind = 0
        tsTemp = None
        tsWind = None
        tsRain = None
        idxTemp = 0
        idxRH = 0
        # idxPress = 0
        idxWind = 0
        idxRain = 0
        for module in modules:
            moduleName = 'unnamed'
            try:
                moduleName = module["module_name"]
            except:
                pass

            moduleID = module["_id"]
            moduleDataType = module["data_type"]

            if self.params["useSpecifiedModules"]:
                if moduleID not in specifiedModules:
                    continue
            else:
                if "CO2" in moduleDataType: # This will skip indoor base station
                    continue
                if ("Temperature" not in moduleDataType) and ("Rain" not in moduleDataType) and ("Wind" not in moduleDataType):
                    continue

            if "Rain" in moduleDataType:
                try:
                    rainJson = self.getMeasure(moduleID, deviceID, "sum_rain")
                    recordedRain = self.__toFloat(rainJson["body"][0]["value"][0][0])
                    tsRain = self.__toInt(rainJson["body"][0]["beg_time"])
                    rain += recordedRain
                    idxRain+=1
                except Exception, e:
                    log.error("Error reading rain gauge module: %s" % e)

            if "Wind" in moduleDataType:
                try:
                    windJson = self.getMeasure(moduleID, deviceID, "WindStrength")
                    recorderWind = self.__toFloat(windJson["body"][0]["value"][0][0])
                    tsWind = self.__toInt(windJson["body"][0]["beg_time"])
                    wind += recorderWind
                    idxWind+=1
                except Exception, e:
                    log.error("Error reading wind module: %s" % e)

            if "Temperature" in moduleDataType:
                try:
                    tempJson = self.getMeasure(moduleID, deviceID, "min_temp,max_temp,min_hum,max_hum,min_pressure,max_pressure")
                    [recordedMinTemp, recordedMaxTemp, recordedMinRH, recordedMaxRH, recordedMinPress, recordedMaxPress] = self.__toFloat(tempJson["body"][0]["value"][0])
                    tsTemp = self.__toInt(tempJson["body"][0]["beg_time"])
                    if(recordedMaxTemp is not None and recordedMinTemp is not None):
                        maxTemp += recordedMaxTemp
                        minTemp += recordedMinTemp
                        idxTemp += 1
                    if(recordedMinRH is not None and recordedMaxRH is not None):
                        maxRH += recordedMaxRH
                        minRH += recordedMinRH
                        idxRH += 1
                    # if(recordedMaxPress is not None and recordedMinPress is not None):
                    #     maxPress += recordedMaxPress
                    #     minPress += recordedMinPress
                    #     idxPress += 1
                except Exception, e:
                    log.error("Error reading temperature module: %s" % e)

        if idxTemp > 0 and tsTemp is not None:
            self.addValue(RMParser.dataType.MINTEMP, tsTemp, minTemp/idxTemp)
            self.addValue(RMParser.dataType.MAXTEMP, tsTemp, maxTemp/idxTemp)

        if idxRH > 0 and tsTemp is not None:
            self.addValue(RMParser.dataType.MAXRH, tsTemp, maxRH/idxRH)
            self.addValue(RMParser.dataType.MINRH, tsTemp, minRH/idxRH)

        # if idxPress > 0 and tsTemp is not None:
        #     self.addValue(RMParser.dataType.PRESSURE, tsTemp, (maxPress + minPress)/(2*idxRH))

        if idxWind and tsWind is not None:
            self.addValue(RMParser.dataType.WIND, tsWind, wind/idxWind)
        if idxRain > 0 and tsRain is not None:
            self.addValue(RMParser.dataType.RAIN, tsRain, rain/idxRain)

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
                return True
        except:
            log.error("Failed to refresh token.")
            self.accessToken = None
            self.refreshToken = None
            self.accessTokenExpiration = 0

        return False

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
            log.error("Failed to get oAuth token")
            return False

        return True

    def getData(self):
        postParams = {
            "access_token" : self.accessToken,
            }
        self.jsonData = self.postRequest(self.deviceListReq, postParams)

    def getMeasure(self, moduleID, deviceID, measure):
        postParams = {
            "access_token" : self.accessToken,
            "module_id" : moduleID,
            "device_id" :deviceID,
            "scale" : "1day",
            "type" : measure,
            "date_begin" : rmCurrentDayTimestamp() - 24*3600,
            "date_end" : rmCurrentDayTimestamp() - 1,
            "real_time" : True
        }
        try:
            jsonData = self.postRequest(self.getMeasureUrl, postParams)
            return jsonData
        except:
            return None


    def postRequest(self, url, params):
        params = urlencode(params)
        headers = {"Content-Type" : "application/x-www-form-urlencoded;charset=utf-8"}
        req = urllib2.Request(url=url, data=params, headers=headers)

        try:
            log.info("Getting data from %s" % url)
            response = urllib2.urlopen(req)
            log.debug("%s?%s" % (response.geturl(), params))
            return json.loads(response.read())
        except urllib2.URLError, e:
            log.debug(e)
            if hasattr(ssl, '_create_unverified_context'): #for mac os only in order to ignore invalid certificates
                try:
                    context = ssl._create_unverified_context()
                    response = urllib2.urlopen(req, context=context)
                    return json.loads(response.read())
                except Exception, e:
                    log.exception(e)
        return None


    def __toFloat(self, value):
        try:
            if value is None:
                return value
            if isinstance(value,list):
                out = []
                for iterVal in value:
                    out.append(self.__toFloat(iterVal))
                return out
            else:
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

if __name__ == "__main__":
    p = PersonalNetatmo()
    p.perform()
