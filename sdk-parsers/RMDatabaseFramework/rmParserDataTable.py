# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from collections import OrderedDict

from RMDataFramework.rmForecastInfo import RMForecastInfo
from RMDataFramework.rmWeatherData import RMWeatherData
from RMDataFramework.rmParserConfig import RMParserConfig
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmTimeUtils import rmTimestampToDateAsString, rmGetStartOfDay, rmCurrentDayTimestamp, rmNormalizeTimestamp
from rmDatabase import RMTable
from RMUtilsFramework.rmLogging import log

##-----------------------------------------------------------------------------------------------------
##
##
class RMParserTable(RMTable):
    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS parser ("\
                            "ID INTEGER PRIMARY KEY AUTOINCREMENT, "\
                            "fileName VARCHAR(256) NOT NULL, "\
                            "name VARCHAR(64) NOT NULL, "\
                            "enabled BOOLEAN NOT NULL DEFAULT 1, "\
                            "params RMParaserParams DEFAULT NULL, "\
                            "UNIQUE(fileName, name)"\
                            ")")
        self.database.commit()

    def addParser(self, fileName, name, enabled, params = None):
        if(self.database.isOpen()):

            if "user-" in fileName:
                parserConfig = self.getParserWithFilename(name, fileName)
            else:
                parserConfig = self.getParser(name)
            isNew = False
            if parserConfig is None:
                self.database.execute("INSERT INTO parser (fileName, name, enabled, params) VALUES(?, ?, ?, ?)", (fileName, name, enabled, params, ))
                self.database.commit()
                parserConfig = RMParserConfig(self.database.lastRowId(), fileName, name, enabled)
                isNew = True
            elif parserConfig.fileName != fileName:
                self.database.execute("UPDATE parser SET fileName=?, name=?, enabled=?, params=? WHERE ID=?", (fileName, name, enabled, params, parserConfig.dbID, ))
                self.database.commit()
                parserConfig.fileName = fileName
                parserConfig.name = name
                parserConfig.enabled = enabled
            return parserConfig, isNew
        return None, False

    def getParserParams(self, id):
        if(self.database.isOpen()):
            row = self.database.execute("SELECT params FROM parser WHERE ID=?", (id, )).fetchone()
            if row:
                return row[0]
        return None

    def updateParserParams(self, id, params):
        if(self.database.isOpen()):
            self.database.execute("UPDATE parser SET params=? WHERE ID=?", (params, id, ))
            self.database.commit()
        return None

    def enableParser(self, id, enable):
        if(self.database.isOpen()):
            self.database.execute("UPDATE parser SET enabled=? WHERE ID=?", (enable, id, ))
            self.database.commit()

    def getParserIdByName(self, name):
        if(self.database.isOpen()):
            row = self.database.execute("SELECT ID FROM parser WHERE name=?", (name, )).fetchone()
            if row:
                return row[0]
        return None

    def getParser(self, name):
        if(self.database.isOpen()):
            row = self.database.execute("SELECT ID, fileName, enabled FROM parser WHERE name=?", (name, )).fetchone()
            if row:
                return RMParserConfig(row[0], row[1], name, row[2])
        return None

    def getParserWithFilename(self, name, filename):
        if(self.database.isOpen()):
            row = self.database.execute("SELECT ID, enabled FROM parser WHERE name=? AND fileName=?", (name, filename, )).fetchone()
            if row:
                return RMParserConfig(row[0], filename, name, row[1])
        return None

    def getAllParsers(self):
        if(self.database.isOpen()):
            results = []

            rows = self.database.execute("SELECT ID, fileName, name, enabled FROM parser ORDER BY ID")
            for row in rows:
                results.append({
                    "id": row[0],
                    "fileName": row[1],
                    "name": row[2],
                    "enabled": row[3],
                })

            return results
        return None

##-----------------------------------------------------------------------------------------------------
##
##
class RMParserUserDataTable(RMTable):
    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS parserUserDataType ("\
                            "parserID INTEGER NOT NULL, "\
                            "userDataTypeID INTEGER NOT NULL, "\
                            "FOREIGN KEY(parserID) REFERENCES parser(ID), "\
                            "FOREIGN KEY(userDataTypeID) REFERENCES userDataType(ID), "\
                            "PRIMARY KEY(parserID, userDataTypeID)"\
                            ")")
        self.database.commit()

    def addRecords(self, parserID, values):
        if(self.database.isOpen()):
            valuesToInsert = self.__filterValues(parserID, values)
            if valuesToInsert:
                self.database.executeMany("INSERT INTO parserUserDataType(parserID, userDataTypeID) VALUES(?, ?)", valuesToInsert)
                self.database.commit()

    def __filterValues(self, parserID, values):
        valuesToUpdate = {}
        valuesToInsert = []

        results = self.database.execute("SELECT userDataTypeID FROM parserUserDataType WHERE parserID=?", (parserID, ))
        for row in results:
            valuesToUpdate[row[0]] = True

        for value in values:
            if value.id not in valuesToUpdate:
                valuesToInsert.append((parserID, value.id, ))

        return valuesToInsert


##-----------------------------------------------------------------------------------------------------
##
##
class RMParserDataTable(RMTable):
    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS parserData ("\
                                            "forecastID INTEGER NOT NULL, "\
                                            "parserID INTEGER NOT NULL, "\
                                            "timestamp NUMERIC NOT NULL, "\
                                            "temperature DECIMAL DEFAULT NULL, "\
                                            "minTemperature DECIMAL DEFAULT NULL, "\
                                            "maxTemperature DECIMAL DEFAULT NULL, "\
                                            "rh DECIMAL DEFAULT NULL, "\
                                            "minRh DECIMAL DEFAULT NULL, "\
                                            "maxRh DECIMAL DEFAULT NULL, "\
                                            "wind DECIMAL DEFAULT NULL, "\
                                            "solarRad DECIMAL DEFAULT NULL, "\
                                            "skyCover DECIMAL DEFAULT NULL, "\
                                            "rain DECIMAL DEFAULT NULL, "\
                                            "et0 DECIMAL DEFAULT NULL, "\
                                            "pop DECIMAL DEFAULT NULL, "\
                                            "qpf DECIMAL DEFAULT NULL, "\
                                            "condition INTEGER DEFAULT NULL, "\
                                            "pressure DECIMAL DEFAULT NULL, "\
                                            "dewPoint DECIMAL DEFAULT NULL, "\
                                            "userData RMUserData DEFAULT NULL, "\
                                            "archived INTEGER DEFAULT 0, "\
                                            "FOREIGN KEY(forecastID) REFERENCES forecast(ID), "\
                                            "FOREIGN KEY(parserID) REFERENCES parser(ID), "\
                                            "PRIMARY KEY(forecastID, parserID, timestamp)"\
                                            ")")
        self.database.commit()

    def addRecords(self, forecastID, parserID, values):
        if(self.database.isOpen()):

            minMaxMap = {}
            for value in values:
                dayTimestamp = rmGetStartOfDay(value.timestamp)
                minMax = minMaxMap.get(dayTimestamp)

                if minMax is None:
                    minMax = self.getMinMax(parserID, dayTimestamp)
                    minMaxMap[dayTimestamp] = minMax

                minMax["minTemperature"] = self.__min(self.__min(value.minTemperature, value.temperature), minMax["minTemperature"])
                minMax["maxTemperature"] = self.__max(self.__max(value.maxTemperature, value.temperature), minMax["maxTemperature"])

                minMax["minRH"] = self.__min(self.__min(value.minRh, value.rh), minMax["minRH"])
                minMax["maxRH"] = self.__max(self.__min(value.maxRh, value.rh), minMax["maxRH"])

            valuesToInsert = []
            for value in values:
                dayTimestamp = rmGetStartOfDay(value.timestamp)
                minMax = minMaxMap[dayTimestamp]

                valuesToInsert.append((forecastID, parserID,
                                   value.timestamp,
                                   value.temperature,
                                   minMax["minTemperature"],
                                   minMax["maxTemperature"],
                                   value.rh,
                                   minMax["minRH"],
                                   minMax["maxRH"],
                                   value.wind,
                                   value.solarRad,
                                   value.skyCover,
                                   value.rain,
                                   value.et0,
                                   value.pop,
                                   value.qpf,
                                   value.condition,
                                   value.pressure,
                                   value.dewPoint,
                                   value.userData))

            self.clearHistory(parserID, False)

            self.database.executeMany("INSERT INTO parserData(forecastID, parserID, timestamp, "\
                                            "temperature, minTemperature, maxTemperature, rh, minRh, maxRh, "\
                                            "wind, solarRad, skyCover, rain, et0, pop, qpf, "\
                                            "condition, pressure, dewPoint, userData) "\
                                            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valuesToInsert)
            self.database.commit()

    def removeEntriesWithParserIdAndTimestamp(self, parserID, values):
        if(self.database.isOpen()):
            timestamps = []
            for value in values:
                timestamps.append((value.timestamp))

            minTS = int(min(timestamps))

            self.database.execute("DELETE FROM parserData WHERE parserID=? AND timestamp>=?", (parserID, minTS))
            self.database.commit()



    def clearHistory(self, parserID, commit):
        if self.database.isOpen():
            if globalSettings.parserHistorySize > 0:
                maxDayTimestamp = rmCurrentDayTimestamp()
                minDayTimestamp = maxDayTimestamp - globalSettings.parserHistorySize * 86400
                self.deleteRecordsHistoryByDayThreshold(parserID, minDayTimestamp, maxDayTimestamp, False)
            else:
                self.database.execute("DELETE FROM parserData WHERE parserID=?", (parserID, ))
                if commit:
                    self.database.commit()

    def deleteRecordsByDayThreshold(self, dayTimestamp, commit = True):
        if(self.database.isOpen()):
            self.database.execute("DELETE FROM parserData WHERE timestamp<?", (dayTimestamp, ))
            if commit:
                self.database.commit()

    def deleteRecordsHistoryByDayThreshold(self, parserID, minDayTimestampThresold, maxDayTimestampThresold, commit = True):
        if(self.database.isOpen()):
            # Delete very old data
            rows = self.database.execute("DELETE FROM parserData WHERE timestamp<?", (minDayTimestampThresold, ))
#SELECT f.ID, f.timestamp, p.rowid, p.timestamp, p.temperature, p.rh, p.wind, p.solarRad, p.skyCover, p.rain, p.et0, p.pop, p.qpf, p.condition, p.pressure, p.dewPoint, p.archived FROM parserData p, forecast f WHERE f.ID=p.forecastID ORDER BY p.timestamp DESC, p.forecastID DESC
            # Compute new data
            query = "SELECT f.ID, f.timestamp, p.rowid, p.timestamp, p.temperature, p.rh, p.wind, p.solarRad, p.skyCover, p.rain, p.et0, p.pop, p.qpf, p.condition, p.pressure, p.dewPoint, p.archived "\
                    "FROM parserData p, forecast f WHERE f.ID=p.forecastID AND p.parserID=? ORDER BY p.timestamp DESC, p.forecastID DESC"
            rows = self.database.execute(query, (parserID, ))

            tempData = OrderedDict()
            rowIdsToDelete = []
            rowIdsToKeep = []
            newData = []

            lastDayTimestamp = None
            lastForecastID = None

            for row in rows:
                forecastID = row[0]
                forecastDayTimestamp = rmGetStartOfDay(row[1])
                dayTimestamp = rmGetStartOfDay(row[3])

                if lastDayTimestamp != dayTimestamp: # Enter a new day
                    lastDayTimestamp = dayTimestamp
                    lastForecastID = forecastID

                if maxDayTimestampThresold <= forecastDayTimestamp:
                    continue

                if lastForecastID != forecastID: # We want only the last forecast for this day
                    rowIdsToDelete.append(str(row[2]))
                    continue

                timestamp = rmNormalizeTimestamp(row[3])
                #timestampOffset = timestamp - dayTimestamp

                dayData = tempData.get(dayTimestamp, None)
                if dayData is None:
                    tempData[dayTimestamp] = dayData = {}
                    dayData["count"] = 0
                    dayData["data"] = {
                        "rowid": row[2],
                        "forecastID": forecastID,
                        "condition": None,
                        "archived": row[16]
                    }
                    rowIdsToKeep.append(str(row[2]))
                else:
                    rowIdsToDelete.append(str(row[2]))

                dayData["count"] += 1
                dayData = dayData["data"]

                dayData["temperature"] = self.__sum(dayData.get("temperature", None), row[4])
                dayData["rh"] = self.__sum(dayData.get("rh", None), row[5])
                dayData["wind"] = self.__sum(dayData.get("wind", None), row[6])
                dayData["solarRad"] = self.__sum(dayData.get("solarRad", None), row[7])
                dayData["skyCover"] = self.__sum(dayData.get("skyCover", None), row[8])
                dayData["rain"] = self.__sum(dayData.get("rain", None), row[9])
                dayData["et0"] = row[10]
                dayData["pop"] = self.__sum(dayData.get("pop", None), row[11])
                dayData["qpf"] = self.__sum(dayData.get("qpf", None), row[12])
                dayData["pressure"] = self.__sum(dayData.get("pressure", None), row[14])
                dayData["dewPoint"] = self.__sum(dayData.get("dewPoint", None), row[15])

                if row[13]: # and 43200 <= timestampOffset <= 50400: # between 12-14.
                    dayData["condition"] = row[13]


            for dayTimestamp in tempData:
                dayData = tempData[dayTimestamp]

                count = dayData["count"]
                dayData = dayData["data"]

                if not dayData["archived"]:
                    if count > 1:
                        dayData["temperature"] = self.__avg(dayData.get("temperature", None), count)
                        dayData["rh"] = self.__avg(dayData.get("rh", None), count)
                        dayData["wind"] = self.__avg(dayData.get("wind", None), count)
                        dayData["solarRad"] = self.__avg(dayData.get("solarRad", None), count)
                        dayData["skyCover"] = self.__avg(dayData.get("skyCover", None), count)
                        dayData["rain"] = self.__avg(dayData.get("rain", None), count)
                        dayData["pop"] = self.__avg(dayData.get("pop", None), count)
                        dayData["pressure"] = self.__avg(dayData.get("pressure", None), count)
                        dayData["dewPoint"] = self.__avg(dayData.get("dewPoint", None), count)

                    newData.append((dayTimestamp, dayData["temperature"], dayData["rh"], dayData["wind"], dayData["solarRad"],
                                    dayData["skyCover"], dayData["rain"], dayData["et0"], dayData["pop"], dayData["qpf"],
                                    dayData["condition"], dayData["pressure"], dayData["dewPoint"], dayData["rowid"]))

            # Delete unnecessary data
            if rowIdsToDelete:
                self.database.execute("DELETE FROM parserData WHERE rowid IN(%s)" % ",".join(rowIdsToDelete))

            # Update computed data
            if newData:
                query = "UPDATE parserData SET timestamp=?, temperature=?, rh=?, wind=?, solarRad=?, skyCover=?, rain=?, et0=?, pop=?, qpf=?, condition=?, pressure=?, dewPoint=?, archived=1 WHERE rowid=?"
                self.database.executeMany(query, newData)

            self.database.execute("DELETE FROM forecast WHERE processed <> 0 AND ID NOT IN (SELECT DISTINCT forecastID FROM parserData)")

            if commit:
                self.database.commit()


    def getLastForecastByParser(self):

        if self.database.isOpen():
            allRecords = OrderedDict()    #
    #def getLastRecordsKeys(self):
    #    ### key[0] is RMForecastInfo, key[1] is parserID
    #    if self.database.isOpen():
    #        allRecords = []
    #
    #        #SELECT pID, f.* FROM forecast f, (SELECT DISTINCT pd.forecastID fID, pd.parserID pID from forecast f, parserData pd WHERE f.processed=0 AND f.id=pd.forecastID UNION SELECT MAX(parserData.forecastID) fID, parserData.parserID pID FROM parserData GROUP BY parserID) AS pf WHERE pf.fID=f.id ORDER BY f.id DESC, pID DESC;
    #        records = self.database.execute("SELECT pID, f.id, f.timestamp, f.processed FROM forecast f, ("\
    #                                           "SELECT DISTINCT pd.forecastID fID, pd.parserID pID from forecast f, parserData pd WHERE f.processed=0 AND f.id=pd.forecastID "\
    #                                             "UNION "\
    #                                           "SELECT MAX(parserData.forecastID) fID, parserData.parserID pID FROM parserData GROUP BY parserID) AS pf "\
    #                                        "WHERE pf.fID=f.id ORDER BY f.id DESC, pID DESC")
    #
    #        for row in records:
    #            parserID = row[0]
    #            forecast = RMForecastInfo(row[1], row[2], row[3])
    #            allRecords.append((forecast, parserID, ))
    #        return allRecords
    #    return None


            #SELECT pd.pID, f.* FROM (SELECT max(pd.forecastID) fID, pd.parserID pID FROM parserData pd  GROUP BY pd.parserID) pd, forecast f WHERE pd.fID=f.ID ORDER BY f.ID DESC, pd.pID DESC;
            records = self.database.execute("SELECT pd.pID, f.* FROM (SELECT max(pd.forecastID) fID, pd.parserID pID FROM parserData pd  GROUP BY pd.parserID) pd, forecast f WHERE pd.fID=f.ID ORDER BY f.ID DESC, pd.pID DESC")

            for row in records:
                allRecords[row[0]] = RMForecastInfo(row[1], row[2], row[3])

            return allRecords
        return None

    def getLatestRecordsKeys(self):
        ### key[0] is forecastID, key[1] is parserID
        if self.database.isOpen():
            allRecords = []

            #SELECT pID, f.* FROM forecast f, (SELECT DISTINCT pd.forecastID fID, pd.parserID pID from forecast f, parserData pd WHERE f.processed=0 AND f.id=pd.forecastID UNION SELECT MAX(parserData.forecastID) fID, parserData.parserID pID FROM parserData GROUP BY parserID) AS pf WHERE pf.fID=f.id ORDER BY f.id DESC, pID DESC;
            records = self.database.execute("SELECT f.id, pID FROM forecast f, ("\
                                               "SELECT DISTINCT pd.forecastID fID, pd.parserID pID from forecast f, parserData pd WHERE f.processed=0 AND f.id=pd.forecastID "\
                                                 "UNION "\
                                               "SELECT MAX(parserData.forecastID) fID, parserData.parserID pID FROM parserData GROUP BY parserID) AS pf "\
                                            "WHERE pf.fID=f.id ORDER BY f.id DESC, pID DESC")

            for row in records:
                allRecords.append((row[0], row[1]))
            return allRecords
        return None

    def getRecordsForKey(self, key, ignoreDisabledParser = False):
        ### key[0] is forecastID, key[1] is parserID
        if self.database.isOpen():
            allRecords = []

            if ignoreDisabledParser:
                records = self.database.execute("SELECT pd.* from parserData pd, parser p WHERE pd.forecastID=? AND pd.parserID=? AND pd.parserID=p.ID AND p.enabled<>0", (key[0], key[1], ))
            else:
                records = self.database.execute("SELECT * from parserData WHERE forecastID=? AND parserID=?", (key[0], key[1], ))
            for row in records:
                weatherData = RMWeatherData(row[2])
                weatherData.temperature = row[3]
                weatherData.minTemperature = row[4]
                weatherData.maxTemperature = row[5]
                weatherData.rh = row[6]
                weatherData.minRh = row[7]
                weatherData.maxRh = row[8]
                weatherData.wind = row[9]
                weatherData.solarRad = row[10]
                weatherData.skyCover = row[11]
                weatherData.rain = row[12]
                weatherData.et0 = row[13]
                weatherData.pop = row[14]
                weatherData.qpf = row[15]
                weatherData.condition = row[16]
                weatherData.pressure = row[17]
                weatherData.dewPoint = row[18]
                weatherData.userData = row[19]

                allRecords.append(weatherData)
            return allRecords
        return None

    def getRecordsByParserName(self, parserName):
        results = OrderedDict()
        if self.database.isOpen():
            #SELECT f.timestamp, f.processed, pd.* FROM parser p, forecast f, parserData pd WHERE p.name='ForecastIO Parser' AND p.id == pd.parserID AND f.id == pd.forecastID ORDER BY f.id DESC, pd.timestamp DESC;
            records = self.database.execute("SELECT f.timestamp, f.processed, pd.* FROM parser p, forecast f, parserData pd "\
                                            "WHERE p.name=? AND p.id == pd.parserID AND f.id == pd.forecastID "\
                                            "ORDER BY f.id DESC, pd.timestamp ASC", (parserName, ))
            for row in records:
                forecast = RMForecastInfo(row[2], row[0], row[1])

                weatherData = RMWeatherData(row[4])
                weatherData.temperature = row[5]
                weatherData.minTemperature = row[6]
                weatherData.maxTemperature = row[7]
                weatherData.rh = row[8]
                weatherData.minRh = row[9]
                weatherData.maxRh = row[10]
                weatherData.wind = row[11]
                weatherData.solarRad = row[12]
                weatherData.skyCover = row[13]
                weatherData.rain = row[14]
                weatherData.et0 = row[15]
                weatherData.pop = row[16]
                weatherData.qpf = row[17]
                weatherData.condition = row[18]
                weatherData.pressure = row[19]
                weatherData.dewPoint = row[20]
                weatherData.userData = row[21]

                dayTimestamp = rmGetStartOfDay(weatherData.timestamp)

                forecastValues = None
                if forecast in results:
                    forecastValues = results[forecast]
                else:
                    forecastValues = OrderedDict()
                    results[forecast] = forecastValues

                dailyValues = None
                if dayTimestamp in forecastValues:
                    dailyValues = forecastValues[dayTimestamp]
                else:
                    dailyValues = []
                    forecastValues[dayTimestamp] = dailyValues

                dailyValues.append([weatherData, ])

        return results

    def getRecordsByParserID(self, parserID, minDayTimestamp = None, maxDayTimestamp = None):
        results = OrderedDict()
        if self.database.isOpen():
            #SELECT f.timestamp, f.processed, pd.* FROM parser p, forecast f, parserData pd WHERE p.name='ForecastIO Parser' AND p.id == pd.parserID AND f.id == pd.forecastID ORDER BY f.id DESC, pd.timestamp DESC;
            if minDayTimestamp and minDayTimestamp:
                records = self.database.execute("SELECT f.timestamp, f.processed, pd.* FROM forecast f, parserData pd "\
                                                "WHERE pd.parserID==? AND f.id == pd.forecastID AND ?<=pd.timestamp AND pd.timestamp<? "\
                                                "ORDER BY f.id DESC, pd.timestamp ASC", (parserID, minDayTimestamp, maxDayTimestamp))
            elif minDayTimestamp:
                records = self.database.execute("SELECT f.timestamp, f.processed, pd.* FROM forecast f, parserData pd "\
                                                "WHERE pd.parserID==? AND f.id == pd.forecastID AND ?<=pd.timestamp "\
                                                "ORDER BY f.id DESC, pd.timestamp ASC", (parserID, minDayTimestamp))
            elif maxDayTimestamp:
                records = self.database.execute("SELECT f.timestamp, f.processed, pd.* FROM forecast f, parserData pd "\
                                                "WHERE pd.parserID==? AND f.id == pd.forecastID AND pd.timestamp<? "\
                                                "ORDER BY f.id DESC, pd.timestamp ASC", (parserID, maxDayTimestamp))
            else:
                records = self.database.execute("SELECT f.timestamp, f.processed, pd.* FROM forecast f, parserData pd "\
                                                "WHERE pd.parserID==? AND f.id == pd.forecastID "\
                                                "ORDER BY f.id DESC, pd.timestamp ASC", (parserID, ))
            for row in records:
                forecast = RMForecastInfo(row[2], row[0], row[1])

                weatherData = RMWeatherData(row[4])
                weatherData.temperature = row[5]
                weatherData.minTemperature = row[6]
                weatherData.maxTemperature = row[7]
                weatherData.rh = row[8]
                weatherData.minRh = row[9]
                weatherData.maxRh = row[10]
                weatherData.wind = row[11]
                weatherData.solarRad = row[12]
                weatherData.skyCover = row[13]
                weatherData.rain = row[14]
                weatherData.et0 = row[15]
                weatherData.pop = row[16]
                weatherData.qpf = row[17]
                weatherData.condition = row[18]
                weatherData.pressure = row[19]
                weatherData.dewPoint = row[20]
                weatherData.userData = row[21]

                dayTimestamp = rmGetStartOfDay(weatherData.timestamp)

                forecastValues = None
                if forecast in results:
                    forecastValues = results[forecast]
                else:
                    forecastValues = OrderedDict()
                    results[forecast] = forecastValues

                dailyValues = None
                if dayTimestamp in forecastValues:
                    dailyValues = forecastValues[dayTimestamp]
                else:
                    dailyValues = []
                    forecastValues[dayTimestamp] = dailyValues

                dailyValues.append(weatherData)

        return results

    def getMinMax(self, parserID, dayTimestamp):
        ### Min and Max are computed only from the last forecast for that day.

        results = {
            "minTemperature": None,
            "maxTemperature": None,
            "minRH": None,
            "maxRH": None
        }

        if self.database.isOpen():
            minForecastTimestamp = None
            maxForecastTimestamp = None
            maxDayTimestamp = dayTimestamp + 86400

            rows = self.database.execute("SELECT f.timestamp, pd.timestamp, pd.temperature, pd.minTemperature, pd.maxTemperature, pd.rh, pd.minRh, pd.maxRh "\
                                         "FROM forecast f, parserData pd "\
                                         "WHERE pd.parserID=? AND ?<=pd.timestamp AND pd.timestamp<=? AND pd.forecastID=f.ID ORDER BY pd.forecastID DESC",
                                         (parserID, dayTimestamp - 2 * 86400, dayTimestamp + 2 * 86400))
            for row in rows:
                timestamp = rmGetStartOfDay(row[1])

                if dayTimestamp <= timestamp < maxDayTimestamp:
                    forecastTimestamp = rmGetStartOfDay(row[0])
                    if maxForecastTimestamp is None:
                        minForecastTimestamp = forecastTimestamp
                        maxForecastTimestamp = forecastTimestamp + 86400

                    if minForecastTimestamp <= forecastTimestamp < maxForecastTimestamp:
                        minTemp = self.__val(row[3], row[2])
                        maxTemp = self.__val(row[4], row[2])

                        minRH = self.__val(row[6], row[5])
                        maxRH = self.__val(row[7], row[5])

                        results["minTemperature"] = self.__min(results["minTemperature"], minTemp)
                        results["maxTemperature"] = self.__max(results["maxTemperature"], maxTemp)

                        results["minRH"] = self.__min(results["minRH"], minRH)
                        results["maxRH"] = self.__max(results["maxRH"], maxRH)

        return results

    def deleteRecordsByTimestampThreshold(self, parserID, minTimestamp, maxTimestamp = None):
        if(self.database.isOpen()):
            if(maxTimestamp == None):
                self.database.execute("DELETE FROM parserData WHERE parserID=? AND timestamp<?",
                                    (parserID, minTimestamp, ))
                self.database.commit()
            else:
                self.database.execute("DELETE FROM parserData WHERE parserID=? AND (timestamp<? OR ?<timestamp)",
                                    (parserID, minTimestamp, maxTimestamp, ))
                self.database.commit()

    def deleteRecordsByParser(self, parserID):
        if(self.database.isOpen()):
            self.database.execute("DELETE FROM parserData WHERE parserID=?", (parserID, ))
            self.database.commit()

    def clear(self, commit):
        if(self.database.isOpen()):
            self.database.execute("DELETE FROM parserData")
            if commit:
                self.database.commit()

    def dump(self):
        if self.database.isOpen():
            results = self.database.execute("SELECT timestamp, COUNT(parserID) FROM parserData GROUP BY timestamp;")
            for row in results:
                log.debug("(", rmTimestampToDateAsString(row[0]), ", ", row[1], ")")
                pass

    def __sum(self, initial, toAdd):
        if initial == None and toAdd == None:
            return None
        if initial == None:
            return toAdd
        if toAdd == None:
            return initial
        return initial + toAdd

    def __avg(self, value, count):
        if value == None or count < 1:
            return None
        return round(value / count, 2)

    def __val(self, a, defaultVal):
        if a == None:
            return defaultVal
        return a

    def __min(self, a, b):
        if a == None and b == None:
            return None
        if a == None:
            return b
        if b == None:
            return a
        return min(a, b)

    def __max(self, a, b):
        if a == None and b == None:
            return None
        if a == None:
            return b
        if b == None:
            return a
        return max(a, b)