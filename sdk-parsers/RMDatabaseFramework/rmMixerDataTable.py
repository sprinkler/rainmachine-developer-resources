# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from collections import OrderedDict

from RMUtilsFramework.rmTimeUtils import rmTimestampToDateAsString
from RMDataFramework.rmForecastInfo import RMForecastInfo
from RMDataFramework.rmMixerData import RMMixerData
from rmDatabase import RMTable
from RMUtilsFramework.rmLogging import log

##-----------------------------------------------------------------------------------------------------
##
##
class RMMixerDataTable(RMTable):
    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS mixerData ("\
                                            "forecastID INTEGER NOT NULL, "\
                                            "forecastTimestamp INTEGER NOT NULL, "\
                                            "timestamp NUMERIC NOT NULL, "\
                                            "temperature DECIMAL DEFAULT NULL, "\
                                            "rh DECIMAL DEFAULT NULL, "\
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
                                            "minTemp DECIMAL DEFAULT NULL, "\
                                            "maxTemp DECIMAL DEFAULT NULL, "\
                                            "minRH DECIMAL DEFAULT NULL, "\
                                            "maxRH DECIMAL DEFAULT NULL, "\
                                            "et0calc DECIMAL DEFAULT NULL, "\
                                            "et0final DECIMAL DEFAULT NULL, "\
                                            #"FOREIGN KEY(forecastID) REFERENCES forecast(ID), "\
                                            "PRIMARY KEY(forecastID, timestamp)"\
                                            ")")
        self.database.commit()

    def addRecords(self, forecastID, forecastTimestamp, values):
        if(self.database.isOpen()):
            valuesToInsert = [(forecastID,
                               forecastTimestamp,
                               value.timestamp,
                               value.temperature,
                               value.rh,
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
                               value.minTemp,
                               value.maxTemp,
                               value.minRH,
                               value.maxRH,
                               value.et0calc,
                               value.et0final
                                ) for value in values]

            self.database.executeMany("INSERT INTO mixerData(forecastID, forecastTimestamp, timestamp, "\
                                      "temperature, rh, wind, solarRad, skyCover, rain, et0, pop, qpf, "\
                                      "condition, pressure, dewPoint, "\
                                      "minTemp, maxTemp, minRH, maxRH, et0calc, et0final) "\
                                      "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valuesToInsert)
            self.database.commit()

    def deleteOlderDataByTimestampCollision(self, values):
        if(self.database.isOpen()):
            timestampsToDelete = [(value.timestamp,) for value in values]
            self.database.executeMany("DELETE FROM mixerData "\
                                  "WHERE timestamp=? ", timestampsToDelete)
            self.database.commit()

    def getRecordsByThreshold(self, minTimestamp = None, maxTimestamp = None, orderAsc = True, asDict = False):
        result = []
        if(self.database.isOpen()):
            cursor = None

            order = "ASC"
            if not orderAsc:
                order = "DESC"

            if(minTimestamp == None and maxTimestamp == None):
                cursor = self.database.execute("SELECT * FROM mixerData ORDER BY timestamp " + order)
            if(maxTimestamp == None):
                cursor = self.database.execute("SELECT * FROM mixerData WHERE timestamp=? ORDER BY timestamp " + order, (minTimestamp, ))
            else:
                cursor = self.database.execute("SELECT * FROM mixerData WHERE ?<=timestamp AND timestamp<? ORDER BY timestamp " + order,
                                    (minTimestamp, maxTimestamp, ))

            for row in cursor:
                mixerData = RMMixerData(row[2])
                mixerData.temperature = row[3]
                mixerData.rh = row[4]
                mixerData.wind = row[5]
                mixerData.solarRad = row[6]
                mixerData.skyCover = row[7]
                mixerData.rain = row[8]
                mixerData.et0 = row[9]
                mixerData.pop = row[10]
                mixerData.qpf = row[11]
                mixerData.condition = row[12]
                mixerData.pressure = row[13]
                mixerData.dewPoint = row[14]
                mixerData.minTemp = row[15]
                mixerData.maxTemp = row[16]
                mixerData.minRH = row[17]
                mixerData.maxRH = row[18]
                mixerData.et0calc = row[19]
                mixerData.et0final = row[20]

                result.append(mixerData)

        return result

    def getLastRecordsByThreshold(self, minTimestamp = None, maxTimestamp = None, orderAsc = True, asDict = False, noOfRecords = None):
        if asDict:
            result = OrderedDict()
        else:
            result = []

        if(self.database.isOpen()):
            cursor = None

            order = "ASC"
            if not orderAsc:
                order = "DESC"

            limit = ""
            if noOfRecords:
                limit = " LIMIT %d" % noOfRecords

            if minTimestamp is None and maxTimestamp is None:
                cursor = self.database.execute("SELECT MAX(forecastID), * FROM mixerData GROUP BY timestamp ORDER BY timestamp " + order + limit)
            elif minTimestamp is None:
                cursor = self.database.execute("SELECT MAX(forecastID), * FROM mixerData WHERE timestamp<=? GROUP BY timestamp ORDER BY timestamp " + order + limit, (maxTimestamp, ))
            elif maxTimestamp is None:
                cursor = self.database.execute("SELECT MAX(forecastID), * FROM mixerData WHERE ?<=timestamp GROUP BY timestamp ORDER BY timestamp " + order + limit, (minTimestamp, ))
            else:
                cursor = self.database.execute("SELECT MAX(forecastID), * FROM mixerData WHERE ?<=timestamp AND timestamp<=? GROUP BY timestamp ORDER BY timestamp " + order + limit,
                                    (minTimestamp, maxTimestamp, ))

            for row in cursor:
                mixerData = RMMixerData(row[3])
                mixerData.temperature = row[4]
                mixerData.rh = row[5]
                mixerData.wind = row[6]
                mixerData.solarRad = row[7]
                mixerData.skyCover = row[8]
                mixerData.rain = row[9]
                mixerData.et0 = row[10]
                mixerData.pop = row[11]
                mixerData.qpf = row[12]
                mixerData.condition = row[13]
                mixerData.pressure = row[14]
                mixerData.dewPoint = row[15]
                mixerData.minTemp = row[16]
                mixerData.maxTemp = row[17]
                mixerData.minRH = row[18]
                mixerData.maxRH = row[19]
                mixerData.et0calc = row[20]
                mixerData.et0final = row[21]

                if asDict:
                    result[row[3]] = mixerData
                else:
                    result.append(mixerData)

        return result

    def getRecordsByForecast(self, useInsertOrder = False):
        result = OrderedDict()
        if(self.database.isOpen()):
            cursor = None
            if useInsertOrder:
                cursor = self.database.execute("SELECT * FROM mixerData ORDER BY forecastID ASC, timestamp ASC")
            else:
                cursor = self.database.execute("SELECT * FROM mixerData ORDER BY forecastID DESC, timestamp ASC")

            for row in cursor:
                forecastID = row[0]
                forecastTimestamp = row[1]

                mixerData = RMMixerData(row[2])
                mixerData.temperature = row[3]
                mixerData.rh = row[4]
                mixerData.wind = row[5]
                mixerData.solarRad = row[6]
                mixerData.skyCover = row[7]
                mixerData.rain = row[8]
                mixerData.et0 = row[9]
                mixerData.pop = row[10]
                mixerData.qpf = row[11]
                mixerData.condition = row[12]
                mixerData.pressure = row[13]
                mixerData.dewPoint = row[14]
                mixerData.minTemp = row[15]
                mixerData.maxTemp = row[16]
                mixerData.minRH = row[17]
                mixerData.maxRH = row[18]
                mixerData.et0calc = row[19]
                mixerData.et0final = row[20]

                if forecastID in result:
                    result[forecastID]["values"].append(mixerData)
                else:
                    result[forecastID] = {"timestamp" : forecastTimestamp, "values": [mixerData, ]}
        return result

    def getRecordsForLastForecast(self):
        forecast = None
        values = None
        if(self.database.isOpen()):

            cursor = self.database.execute("SELECT * FROM mixerData WHERE forecastID=(SELECT MAX(forecastID) from mixerData) ORDER BY timestamp ASC")

            for row in cursor:
                if not forecast:
                    forecast = RMForecastInfo(row[0], row[1])
                    values = []

                mixerData = RMMixerData(row[2])
                mixerData.temperature = row[3]
                mixerData.rh = row[4]
                mixerData.wind = row[5]
                mixerData.solarRad = row[6]
                mixerData.skyCover = row[7]
                mixerData.rain = row[8]
                mixerData.et0 = row[9]
                mixerData.pop = row[10]
                mixerData.qpf = row[11]
                mixerData.condition = row[12]
                mixerData.pressure = row[13]
                mixerData.dewPoint = row[14]
                mixerData.minTemp = row[15]
                mixerData.maxTemp = row[16]
                mixerData.minRH = row[17]
                mixerData.maxRH = row[18]
                mixerData.et0calc = row[19]
                mixerData.et0final = row[20]

                values.append(mixerData)

        return forecast, values

    def getLastRecordForDayForSimulator(self, dayTimestamp):
        result = OrderedDict()

        if(self.database.isOpen()):
            minTimestamp = dayTimestamp
            maxTimestamp = dayTimestamp + 86400

            row = self.database.execute("SELECT * FROM mixerData WHERE ?<=timestamp AND timestamp<? GROUP BY timestamp ORDER BY forecastID DESC LIMIT 1",
                                (minTimestamp, maxTimestamp, )).fetchone()

            if row:
                mixerData = RMMixerData(row[2])
                mixerData.temperature = row[3]
                mixerData.rh = row[4]
                mixerData.wind = row[5]
                mixerData.solarRad = row[6]
                mixerData.skyCover = row[7]
                mixerData.rain = row[8]
                mixerData.et0 = row[9]
                mixerData.pop = row[10]
                mixerData.qpf = row[11]
                mixerData.condition = row[12]
                mixerData.pressure = row[13]
                mixerData.dewPoint = row[14]
                mixerData.minTemp = row[15]
                mixerData.maxTemp = row[16]
                mixerData.minRH = row[17]
                mixerData.maxRH = row[18]
                mixerData.et0calc = row[19]
                mixerData.et0final = row[20]

                mixerDataDict = {
                    row[2]: mixerData
                }

                result = {
                    "forecastID": row[0],
                    "forecastTimestamp": row[1],
                    "data": mixerDataDict
                }

        return result

    def getLastKnownConditionForDay(self, dayTimestamp):
        if(self.database.isOpen()):
            minTimestamp = dayTimestamp
            maxTimestamp = dayTimestamp + 86400

            row = self.database.execute("SELECT condition FROM mixerData WHERE ?<=timestamp AND timestamp<? AND condition IS NOT NULL ORDER BY forecastID DESC, forecastTimestamp DESC LIMIT 1",
                                (minTimestamp, maxTimestamp, )).fetchone()

            if row:
                return row[0]

        return None

    def deleteRecordsByDayThreshold(self, dayTimestamp, commit = True):
        if(self.database.isOpen()):
            self.database.execute("DELETE FROM mixerData WHERE timestamp<?", (dayTimestamp, ))
            if commit:
                self.database.commit()

    def deleteRecordsHistoryByDayThreshold(self, dayTimestamp, commit = True):
        if(self.database.isOpen()):

            # Test Query
            #
            # SELECT * FROM mixerData WHERE NOT EXISTS
            # (SELECT NULL FROM
            #   (SELECT forecastTimestamp fTs, timestamp dayTs FROM mixerData WHERE timestamp<1411096483
            #    EXCEPT SELECT DISTINCT MAX(forecastTimestamp) fTs, timestamp dayTs FROM mixerData WHERE timestamp<1411096483 GROUP BY timestamp
            #   ) toDelete
            #  WHERE mixerData.forecastTimestamp=toDelete.fTs and mixerData.timestamp=toDelete.dayTs
            # );

            query = "DELETE FROM mixerData WHERE EXISTS (SELECT NULL from "\
                                                "("\
                                                    "SELECT forecastTimestamp fTs, timestamp dayTs FROM mixerData WHERE forecastTimestamp<? "\
                                                        "EXCEPT "\
                                                    "SELECT DISTINCT MAX(forecastTimestamp) fTs, timestamp dayTs FROM mixerData WHERE forecastTimestamp<? GROUP BY timestamp "\
                                                ") toDelete "\
                                                "WHERE mixerData.forecastTimestamp=toDelete.fTs and mixerData.timestamp=toDelete.dayTs)"

            self.database.execute(query, (dayTimestamp, dayTimestamp, ))
            if commit:
                self.database.commit()

    def getLastRecordsForecast(self):
        if self.database.isOpen():
            record = self.database.execute("SELECT MAX(forecastID), MAX(forecastTimestamp) FROM mixerData").fetchone()
            return record[0], record[1]
        return None, None

    def clear(self, commit):
        if(self.database.isOpen()):
            self.database.execute("DELETE FROM mixerData")
            if commit:
                self.database.commit()

    def dump(self):
        if self.database.isOpen():
            cursor = self.database.execute("SELECT * FROM mixerData ORDER BY timestamp DESC, forecastID DESC")

            for row in cursor:
                log.debug("fID=%d, fTs=%s,  dTs=%s" % (row[0], rmTimestampToDateAsString(row[1]), rmTimestampToDateAsString(row[2])))
