# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

import uuid

from collections import OrderedDict
from rmDatabase import RMTable, RMDatabase
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp, rmGetStartOfDay, rmTimestampToDateAsString
from RMDataFramework.rmMainDataRecords import RMPastValues, RMAvailableWaterValues

from RMUtilsFramework.rmTimeUtils import rmCurrentDayTimestamp
from RMDataFramework.rmUserSettings import globalSettings

##-----------------------------------------------------------------------------------------------------
##
##
class RMUserSchTable(RMTable):
    def __init__(self, database, fake = False):
        self._tableNamePrograms = "usersch_fake" if fake else "usersch"
        self._tableNameProgZones = "usersch_zones_fake" if fake else "usersch_zones"
        RMTable.__init__(self, database)

    def initialize(self):
        # usersch table
        self.database.execute("CREATE TABLE IF NOT EXISTS %s ("\
                                    "uid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, "\
                                    "name TEXT NOT NULL, " \
                                    "type INTEGER NOT NULL DEFAULT -1, " \
                                    "param NUMERIC NOT NULL DEFAULT 0, " \
                                    "active INTEGER NOT NULL DEFAULT 1, " \
                                    "start_time INTEGER NOT NULL DEFAULT 0, "\
                                    "start_date INTEGER, "\
                                    "updated INTEGER NOT NULL DEFAULT 0, "\
                                    "cs_cycles INTEGER NOT NULL DEFAULT 0, "\
                                    "cs_min INTEGER NOT NULL DEFAULT 0, "\
                                    "delay INTEGER NOT NULL DEFAULT 0, "\
                                    "ignoreInternetWeather INTEGER NOT NULL DEFAULT 0, "\
                                    "futureField1 INTEGER NOT NULL DEFAULT 0, "\
                                    "freq_modified INTEGER NOT NULL DEFAULT 1, "\
                                    "cs_on INTEGER DEFAULT 0, " \
                                    "delay_on INTEGER DEFAULT 0,"\
                                    "useWaterSense INTEGER DEFAULT 0"
                              ")" % self._tableNamePrograms)
        # usersch_zone table
        self.database.execute("CREATE TABLE IF NOT EXISTS %s ("\
                                    "uid INTEGER PRIMARY KEY  NOT NULL ,"\
                                    "pid INTEGER NOT NULL , "\
                                    "zid INTEGER NOT NULL , "\
                                    "duration INTEGER NOT NULL , "\
                                    "active BOOL DEFAULT 1, "\
                                    "last_wd REAL DEFAULT 0"\
                              ")" % self._tableNameProgZones)
        self.database.commit()

    def saveRecord(self, value):
         _uid = None
         if(self.database.isOpen()):
                if value["uid"] == -1:
                    # insert into usersch table
                    self.database.execute("INSERT INTO %s(name, type, param, active, start_time, start_date, "\
                                                "updated, cs_cycles, cs_min, delay, ignoreInternetWeather, futureField1, "\
                                                "freq_modified, cs_on, delay_on, useWaterSense) "\
                                                "VALUES(:name, :type, :param, :active, :start_time, :start_date, "\
                                                ":updated, :cs_cycles, :cs_min, :delay, :ignoreInternetWeather, :futureField1, "\
                                                ":freq_modified, :cs_on, :delay_on, :useWaterSense)" % self._tableNamePrograms,
                                          value)

                    _uid = self.database.lastRowId()
                    #insert into usersch_zones table
                    for z in value["zoneLines"].values():
                        self.database.execute("INSERT OR REPLACE INTO %s(pid, zid, duration, active) "\
                                                            "VALUES ( ?, ?, ?, ?)" % self._tableNameProgZones,
                                              (_uid, z.zid, z.duration, z.active))

                elif value["uid"] > -1:
                    self.database.execute("UPDATE %s SET name=:name, type=:type, param=:param, active=:active, "\
                                                "start_time=:start_time, start_date=:start_date, updated=:updated, "\
                                                "cs_cycles=:cs_cycles, cs_min=:cs_min, delay=:delay, "\
                                                "ignoreInternetWeather=:ignoreInternetWeather, futureField1=:futureField1, "\
                                                "freq_modified=:freq_modified, cs_on=:cs_on, delay_on=:delay_on, useWaterSense=:useWaterSense"\
                                                " WHERE uid=:uid" % self._tableNamePrograms, value)
                    for z in value["zoneLines"].values():
                        self.database.execute("UPDATE %s SET duration=?, active=? WHERE pid=? AND zid=? " % self._tableNameProgZones,
                                              (z.duration, z.active, value["uid"], z.zid))
                    _uid = value["uid"]

                self.database.commit()
         return _uid

    def getAll(self, programDict, programClass, programZonesClass):
        if(self.database.isOpen()):
            cursor = self.database.execute("SELECT * FROM %s ORDER BY uid ASC" % self._tableNamePrograms)
            for row in cursor:
                program = programClass(row["uid"])
                program.name = row["name"]
                program.type = row["type"]
                program.param = row["param"]
                program.active = row["active"]
                program.start_time = row["start_time"]
                program.start_date = row["start_date"]
                program.updated = row["updated"]
                program.cs_cycles = row["cs_cycles"]
                program.cs_min = row["cs_min"]
                program.delay = row["delay"]
                program.ignoreInternetWeather = row["ignoreInternetWeather"]
                program.futureField1 = row["futureField1"]
                program.freq_modified = row["freq_modified"]
                program.cs_on = row["cs_on"]
                program.delay_on = row["delay_on"]
                program.useWaterSense = row["useWaterSense"]

                programDict[row["uid"]] = program

            cursor = self.database.execute("SELECT * FROM %s ORDER BY pid ASC" % self._tableNameProgZones)
            for row in cursor:
                program = programDict.get(row["pid"])
                if program is None:
                    log.error("Missing Program entry for pid %s" % row["pid"])
                    continue
                zid = row["zid"]
                if zid is None:
                    log.error("No zid defined")
                    continue
                program.zoneLines[zid] = programZonesClass(zid)
                program.zoneLines[zid].duration = row["duration"]
                program.zoneLines[zid].active = row["active"]

            return True
        return False

    def delRecord(self, uid):
        if(self.database.isOpen()):
            self.database.execute("DELETE FROM %s WHERE pid = ?" % self._tableNameProgZones, (uid,))
            self.database.execute("DELETE FROM %s WHERE uid = ?" % self._tableNamePrograms, (uid,))
            self.database.commit()
            return True
        return False

    def delAll(self):
        if (self.database.isOpen()):
            self.database.execute("DELETE FROM %s" % self._tableNamePrograms)
            self.database.execute("DELETE FROM %s" % self._tableNameProgZones)
            return True
        return False


##-----------------------------------------------------------------------------------------------------
##
##

class RMZonesAdvancedTable(RMTable):
    def initialize(self):
        #zones_advanced table
        self.database.execute("CREATE TABLE IF NOT EXISTS zones_advanced ("\
                                    "zid INTEGER PRIMARY KEY NOT NULL , "\
                                    "SoilIntakeRate FLOAT, "\
                                    "AvailableWater FLOAT, "\
                                    "MaxAllowedDepletion FLOAT, "\
                                    "RootDepth INTEGER, "\
                                    "isTallPlant boolean, "\
                                    "PrecipRate FLOAT, "\
                                    "AppEfficiency FLOAT, "\
                                    "AllowedSurfaceAcc FLOAT, "\
                                    "FieldCapacity FLOAT, "\
                                    "PermWilting FLOAT, "\
                                    "MaxRuntime INTEGER, "\
                                    "DetailedMonthsKc TEXT, "\
                                    "StartWaterLevel INTEGER"\
                            ")")
        self.database.commit()

    def addRecords(self, zoneList, commit = True):
        if(self.database.isOpen()):
                valuesToInsert = [(value.zid,
                                    value.SoilIntakeRate,
                                    value.AvailableWater, 
                                    value.MaxAllowedDepletion,
                                    value.RootDepth, 
                                    value.isTallPlant, 
                                    value.PrecipRate,
                                    value.AppEfficiency, 
                                    value.AllowedSurfaceAcc, 
                                    value.FieldCapacity,
                                    value.PermWilting,
                                    value.MaxRuntime,
                                    ",".join(str(i) for i in value.DetailedMonthsKc),
                                    value.StartWaterLevel,
                                ) for value in zoneList.values()]
                if commit:
                    try:
                        self.database.executeMany("INSERT INTO zones_advanced( zid, SoilIntakeRate, AvailableWater, MaxAllowedDepletion, RootDepth, isTallPlant, PrecipRate, \
                                                        AppEfficiency, AllowedSurfaceAcc, FieldCapacity, PermWilting, MaxRuntime, DetailedMonthsKc, StartWaterLevel) "\
                                                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valuesToInsert)
                        self.database.commit()
                    except:
                        return False
                else:
                    self.database.executeMany("INSERT INTO zones_advanced( zid, SoilIntakeRate, AvailableWater, MaxAllowedDepletion, RootDepth, isTallPlant, PrecipRate, \
                                                AppEfficiency, AllowedSurfaceAcc, FieldCapacity, PermWilting, MaxRuntime, DetailedMonthsKc, StartWaterLevel) "\
                                            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valuesToInsert)
        else:
            return False
        return True

    def addRecord(self, zone, commit = True):
        if(self.database.isOpen()):
                valuesToInsert = (zone.zid,
                                    zone.SoilIntakeRate,
                                    zone.AvailableWater, 
                                    zone.MaxAllowedDepletion,
                                    zone.RootDepth, 
                                    zone.isTallPlant, 
                                    zone.PrecipRate,
                                    zone.AppEfficiency, 
                                    zone.AllowedSurfaceAcc, 
                                    zone.FieldCapacity,
                                    zone.PermWilting,
                                    zone.MaxRuntime,
                                    ",".join(str(i) for i in zone.DetailedMonthsKc),
                                    zone.StartWaterLevel,
                            )

                if commit:
                    try:
                        self.database.execute("INSERT OR REPLACE INTO zones_advanced( zid, SoilIntakeRate, AvailableWater, MaxAllowedDepletion, RootDepth, isTallPlant, PrecipRate, \
                                                        AppEfficiency, AllowedSurfaceAcc, FieldCapacity, PermWilting, MaxRuntime, DetailedMonthsKc, StartWaterLevel) "\
                                                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valuesToInsert)
                        self.database.commit()
                    except Exception, e:
                        log.error(e)
                        return False
                else:
                        self.database.execute("INSERT OR REPLACE INTO zones_advanced( zid, SoilIntakeRate, AvailableWater, MaxAllowedDepletion, RootDepth, isTallPlant, PrecipRate, \
                                    AppEfficiency, AllowedSurfaceAcc, FieldCapacity, PermWilting, MaxRuntime, DetailedMonthsKc, StartWaterLevel) "\
                                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valuesToInsert)

        else:
            return False
        return True

    def getRecords(self, zoneList, zoneAdvancedClass):
        if(self.database.isOpen()):
            cursor = self.database.execute("SELECT * FROM zones_advanced ORDER BY uid ASC")

            for row in cursor:
                zid = row["zid"]
                zone = zoneAdvancedClass(zid)
                zone.SoilIntakeRate = row["SoilIntakeRate"]
                zone.AvailableWater = row["AvailableWater"]
                zone.MaxAllowedDepletion = row["MaxAllowedDepletion"]
                zone.RootDepth = row["RootDepth"]
                zone.isTallPlant = row["isTallPlant"]
                zone.PrecipRate = row["PrecipRate"]
                zone.AppEfficiency = row["AppEfficiency"]
                zone.AllowedSurfaceAcc = row["AllowedSurfaceAcc"]
                zone.FieldCapacity = row["FieldCapacity"]
                zone.PermWilting = row["PermWilting"]
                zone.MaxRuntime = row["MaxRuntime"]
                zone.DetailedMonthsKc = row["DetailedMonthsKc"]
                zone.StartWaterLevel = row["StartWaterLevel"]

                zoneList[zid] = zone
            return True
        return False

    def delAll(self):
        if (self.database.isOpen()):
            self.database.execute("DELETE FROM zones_advanced")
            return True
        return False


##-----------------------------------------------------------------------------------------------------
##
##
class RMZonesTable(RMTable):
    def initialize(self):
        #zones table
        self.database.execute("CREATE TABLE IF NOT EXISTS zones ("\
                                    "uid INTEGER PRIMARY KEY NOT NULL , "\
                                    "name TEXT NOT NULL , "\
                                    "valveid INTEGER NOT NULL , "\
                                    "ETcoef INTEGER DEFAULT 0 , "\
                                    "active BOOL DEFAULT 1 , "\
                                    "type INTEGER NOT NULL DEFAULT 1 , "\
                                    "internet BOOL DEFAULT 1 , "\
                                    "savings INTEGER NOT NULL DEFAULT 50 , "\
                                    "slope INTEGER NOT NULL  DEFAULT 1, "\
                                    "sun INTEGER NOT NULL  DEFAULT 1, "\
                                    "soil INTEGER NOT NULL  DEFAULT 1, "\
                                    "group_id INTEGER DEFAULT 0, "\
                                    "history INTEGER DEFAULT 1 "\
                            ")")
        self.database.commit()

        self.zonesAdvancedTable = RMZonesAdvancedTable(self.database)

    def addRecords(self, zoneList):
        if(self.database.isOpen()):
                valuesToInsert = [(value.uid,
                               value.name,
                               value.valveid,
                               value.ETcoef,
                               value.active,
                               value.type,
                               value.internet,
                               value.savings,
                               value.slope,
                               value.sun,
                               value.soil,
                               value.group_id,
                               value.history,
                                ) for value in zoneList.values()]
                try:
                    self.database.executeMany("INSERT INTO zones( uid, name, valveid, ETcoef, active, type, internet, savings, slope, sun, soil, group_id, history) "\
                                                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valuesToInsert)
                    self.zonesAdvancedTable.addRecords(zoneList, False)
                    self.database.commit()
                except:
                    return False
        else:
            return False
        return True

    def addRecord(self, zone):
        if(self.database.isOpen()):
                valuesToInsert = (zone.uid,
                               zone.name,
                               zone.valveid,
                               zone.ETcoef,
                               zone.active,
                               zone.type,
                               zone.internet,
                               zone.savings,
                               zone.slope,
                               zone.sun,
                               zone.soil,
                               zone.group_id,
                               zone.history,
                            )
                try:
                    self.database.execute("INSERT OR REPLACE INTO zones( uid, name, valveid, ETcoef, active, type, internet, savings, slope, sun, soil, group_id, history) "\
                                                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valuesToInsert)
                    self.zonesAdvancedTable.addRecord(zone, False)
                    self.database.commit()
                except Exception, e:
                    log.error(e)
                    return False
        else:
            return False
        return True

    def getRecords(self, zoneList, zoneClass):
        if(self.database.isOpen()):
            cursor = self.database.execute("SELECT * FROM zones z, zones_advanced za WHERE z.uid=za.zid ORDER BY uid ASC")

            for row in cursor:
                zid = row["uid"]
                zone = zoneClass(zid)
                zone.name = str(row["name"])
                zone.valveid = row["valveid"]
                zone.ETcoef = row["ETcoef"]
                zone.active = row["active"]
                zone.type = row["type"]
                zone.internet = row["internet"]
                zone.savings = row["savings"]
                zone.slope = row["slope"]
                zone.sun = row["sun"]
                zone.soil = row["soil"]
                zone.group_id = row["group_id"]
                zone.history = row["history"]

                zone.SoilIntakeRate = row["SoilIntakeRate"]
                zone.AvailableWater = row["AvailableWater"]
                zone.MaxAllowedDepletion = row["MaxAllowedDepletion"]
                zone.RootDepth = row["RootDepth"]
                zone.isTallPlant = row["isTallPlant"]
                zone.PrecipRate = row["PrecipRate"]
                zone.AppEfficiency = row["AppEfficiency"]
                zone.AllowedSurfaceAcc = row["AllowedSurfaceAcc"]
                zone.FieldCapacity = row["FieldCapacity"]
                zone.PermWilting = row["PermWilting"]
                zone.MaxRuntime = row["MaxRuntime"]
                zone.DetailedMonthsKc = map(float, row["DetailedMonthsKc"].split(","))
                zone.StartWaterLevel = row["StartWaterLevel"]

                zoneList[zid] = zone
            return True
        return False

    def delAll(self):
        if (self.database.isOpen()):
            self.database.execute("DELETE FROM zones")
            self.zonesAdvancedTable.delAll()
            return True
        return False


##-----------------------------------------------------------------------------------------------------
##
##
class RMSavingsTable(RMTable):
    def initialize(self):
        #savings_data table
        self.database.execute("CREATE TABLE IF NOT EXISTS savings_data ("\
                                    "delta INTEGER NOT NULL , "\
                                    "savings INTEGER NOT NULL , "\
                                    "scheduled INTEGER DEFAULT 0, "\
                                    "watered INTEGER DEFAULT 0 "\
                            ")")
        self.database.commit()

    def addRecords(self):
        if(self.database.isOpen()):
            return True
        return False

##-----------------------------------------------------------------------------------------------------
##
##

class RMStatusTable(RMTable):
    def initialize(self):
        #status table
        self.database.execute("CREATE TABLE IF NOT EXISTS status ("\
                                    "status INTEGER, "\
                                    "sch_id INTEGER DEFAULT '', "\
                                    "schzone_id INTEGER DEFAULT '', "\
                                    "start_time INTEGER DEFAULT '', "\
                                    "delay_time INTEGER "\
                            ")")
        self.database.commit()

    def addRecords(self):
        if(self.database.isOpen()):
            return True
        return False

##-----------------------------------------------------------------------------------------------------
##
##

class RMWaterLogTable(RMTable):
    def __init__(self, database, fake = False):
        self._tableName = "water_log_fake" if fake else "water_log"
        RMTable.__init__(self, database)

    def initialize(self):
        #water_log table
        self.database.execute("CREATE TABLE IF NOT EXISTS %s ("\
                                    "ts_started INTEGER NOT NULL , "\
                                    "usersch_id INTEGER NOT NULL , "\
                                    "zid INTEGER NOT NULL , "\
                                    "user_sec INTEGER NOT NULL , "\
                                    "machine_sec INTEGER NOT NULL , "\
                                    "real_sec INTEGER NOT NULL  DEFAULT 0, "\
                                    "flag INTEGER NOT NULL  DEFAULT 0, "\
                                    "token VARCHAR(32) NOT NULL, "\
                                    "tokenTimestamp VARCHAR(32) NOT NULL, "\
                                    "PRIMARY KEY(ts_started, usersch_id, zid)"\
                            ")" % self._tableName)
        self.database.commit()

    def addRecord(self, startTime, pid, zid, userDuration, machineDuration, realDuration, flag, token, tokenTimestamp):
        if(self.database.isOpen()):

            self.deleteRecordsByHistory(False)

            self.database.execute("INSERT OR REPLACE INTO %s VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)" % self._tableName,
                                (startTime, pid, zid, userDuration, machineDuration, realDuration, flag, token, tokenTimestamp))
            self.database.commit()
            return True
        return False

    def updateRecord(self, startTime, realDuration, flag):
        if(self.database.isOpen()):
            self.database.execute("UPDATE %s SET real_sec=?, flag=? WHERE ts_started=?" % self._tableName,
                                (realDuration, flag, startTime))
            self.database.commit()
            return True
        return False

    def deleteRecordsByHistory(self, commit = True):
        if(self.database.isOpen()):
            threshold = rmCurrentDayTimestamp() - globalSettings.waterLogHistorySize * 86400
            self.database.execute("DELETE FROM %s WHERE tokenTimestamp < ?" % self._tableName, (threshold, ))
            if commit:
                self.database.commit()

    def getRecords(self, minTimestamp, maxTimestamp):
        if(self.database.isOpen()):
            if minTimestamp and maxTimestamp:
                records = self.database.execute("SELECT ts_started, usersch_id, zid, user_sec, machine_sec, real_sec, flag, token, tokenTimestamp FROM %s "\
                                                 "WHERE ?<=tokenTimestamp AND tokenTimestamp<? "\
                                                 "ORDER BY tokenTimestamp, usersch_id, zid" % self._tableName, (minTimestamp, maxTimestamp)
                                                )
            elif minTimestamp:
                records = self.database.execute("SELECT ts_started, usersch_id, zid, user_sec, machine_sec, real_sec, flag, token, tokenTimestamp FROM %s "\
                                                 "WHERE ?<=tokenTimestamp "\
                                                 "ORDER BY tokenTimestamp, usersch_id, zid" % self._tableName, (minTimestamp, )
                                                )
            elif maxTimestamp:
                records = self.database.execute("SELECT ts_started, usersch_id, zid, user_sec, machine_sec, real_sec, flag, token, tokenTimestamp FROM %s "\
                                                 "WHERE tokenTimestamp<? "\
                                                 "ORDER BY tokenTimestamp, usersch_id, zid" % self._tableName, (maxTimestamp, )
                                                )
            else:
                records = self.database.execute("SELECT ts_started, usersch_id, zid, user_sec, machine_sec, real_sec, flag, token, tokenTimestamp FROM %s "\
                                                 "ORDER BY tokenTimestamp, usersch_id, zid" % self._tableName
                                            )

            tempResults = OrderedDict()

            for row in records:
                token = row[7]
                dayTimestamp = rmGetStartOfDay(int(row[8]))

                dayGroup = tempResults.get(dayTimestamp, None)
                if dayGroup is None:
                   dayGroup = OrderedDict()
                   tempResults[dayTimestamp] = dayGroup

                programGroup = dayGroup.get(token, None)
                if programGroup is None:
                   programGroup = OrderedDict()
                   dayGroup[token] = programGroup

                zones = programGroup.get(row[1], None)
                if zones is None:
                   zones = OrderedDict()
                   programGroup[row[1]] = zones

                zone = zones.get(row[2], None)
                if zone is None:
                   zone = OrderedDict()
                   zone["uid"] = row[2]
                   zone["flag"] = row[6]
                   zone["cycles"] = []
                   zones[row[2]] = zone

                cycles = zone["cycles"]

                info = OrderedDict()

                info["id"] = len(cycles) + 1
                info["startTime"] = rmTimestampToDateAsString(row[0])
                info["startTimestamp"] = row[0]
                info["userDuration"] = row[3]
                info["machineDuration"] = row[4]
                info["realDuration"] = row[5]

                cycles.append(info)

            results = {"days": []}

            for dayTimestamp in tempResults:
                programs = []
                day = {
                    "date": rmTimestampToDateAsString(dayTimestamp, "%Y-%m-%d"),
                    "dateTimestamp": dayTimestamp,
                    "programs": programs
                }
                results["days"].append(day)

                dayGroup = tempResults[dayTimestamp]
                for token in dayGroup:

                    tempPrograms = dayGroup[token]
                    for programId in tempPrograms:
                        zones = []
                        program = OrderedDict()
                        program["id"] = programId
                        program["zones"] = zones
                        programs.append(program)

                        tempZones = tempPrograms[programId]
                        for zoneId in tempZones:
                            zones.append(tempZones[zoneId])

            return results

        return None

    def getRecordsEx(self, minTimestamp, maxTimestamp, withManualPrograms = False):
        if(self.database.isOpen()):

            #if withManualPrograms:
            #    sqlCondition = " AND usersch_id != 0 "
            #    sqlConditionForced = " WHERE usersch_id != 0"
            #else:
            #    sqlCondition = ""
            #    sqlConditionForced = ""

            if minTimestamp and maxTimestamp:
                records = self.database.execute("SELECT tokenTimestamp, SUM(real_sec) realDuration, SUM(user_sec) userDuration, usersch_id FROM %s "\
                                                 "WHERE ?<=tokenTimestamp AND tokenTimestamp<? GROUP BY tokenTimestamp "\
                                                 "ORDER BY tokenTimestamp" % self._tableName, (minTimestamp, maxTimestamp)
                                                )
            elif minTimestamp:
                records = self.database.execute("SELECT tokenTimestamp, SUM(real_sec) realDuration, SUM(user_sec) userDuration, usersch_id FROM %s "\
                                                 "WHERE ?<=tokenTimestamp GROUP BY tokenTimestamp "\
                                                 "ORDER BY tokenTimestamp" % self._tableName, (minTimestamp, )
                                                )
            elif maxTimestamp:
                records = self.database.execute("SELECT tokenTimestamp, SUM(real_sec), SUM(user_sec) userDuration duration, usersch_id FROM %s "\
                                                 "WHERE tokenTimestamp<? GROUP BY tokenTimestamp "\
                                                 "ORDER BY tokenTimestamp" % self._tableName, (maxTimestamp, )
                                                )
            else:
                records = self.database.execute("SELECT tokenTimestamp, SUM(real_sec) realDuration, SUM(user_sec) userDuration, usersch_id FROM %s "\
                                                 "GROUP BY tokenTimestamp ORDER BY tokenTimestamp, usersch_id, zid" % self._tableName
                                            )

            tempResults = OrderedDict()

            for row in records:
                if not withManualPrograms and int(row[3]) == 0:
                    continue

                dayTimestamp = rmGetStartOfDay(int(row[0]))
                totalDurations = tempResults.get(dayTimestamp, None) # List with real and user durations

                if totalDurations is None:
                    totalDurations = [int(row[1]), int(row[2])]
                else:
                    totalDurations[0] += int(row[1])
                    totalDurations[1] += int(row[2])


                tempResults[dayTimestamp] = totalDurations

            results = {"days": []}

            for dayTimestamp in tempResults:
                date = rmTimestampToDateAsString(dayTimestamp, "%Y-%m-%d")

                day = {
                    "dayTimestamp": dayTimestamp,
                    "date": date,
                    "realDuration": tempResults.get(dayTimestamp)[0],
                    "userDuration": tempResults.get(dayTimestamp)[1]
                }
                results["days"].append(day)

            return results

        return None

    def getZoneRealWateringTime(self, programID, zoneID, minTimestamp, maxTimestamp):
        if(self.database.isOpen()):
            if programID is None:
                row = self.database.execute("SELECT SUM(real_sec) FROM %s WHERE zid=? AND ?<=ts_started AND ts_started<?" % self._tableName,
                                                (zoneID, minTimestamp, maxTimestamp)).fetchone()
            else:
                row = self.database.execute("SELECT SUM(real_sec) FROM %s WHERE usersch_id=? AND zid=? AND ?<=ts_started AND ts_started<?" % self._tableName,
                                                (programID, zoneID, minTimestamp, maxTimestamp)).fetchone()

            if row:
                return row[0]

        return None


    def getLastWatering(self, withManualPrograms = False):
        if (self.database.isOpen()):
            record = self.database.execute("SELECT * FROM %s ORDER BY ts_started DESC LIMIT 1" % self._tableName).fetchone()

            if record:
                return {
                    "startTimestamp": record[0],
                    "pid": record[1],
                    "zid": record[2],
                    "userDuration": record[3],
                    "machineDuration": record[4],
                    "realDuration": record[5],
                    "flag": record[6]
                }

        return None


    def importFromSprinklerV1Db(self, filePath):
        if(self.database.isOpen()):
            v1DB = RMDatabase(filePath)
            if not v1DB.open():
                return False

            result = False
            try:
                data = OrderedDict()
                valuesToInsert = []

                rows = v1DB.execute("SELECT ts_started, usersch_id, zid, user_sec, machine_sec, real_sec, flag FROM %s ORDER BY ts_started, zid" % self._tableName)
                for row in rows:
                    dayTimestamp = rmGetStartOfDay(int(row[0]))

                    dayData = data.get(dayTimestamp, None)
                    if dayData is None:
                        dayData = {
                            "token": uuid.uuid4().hex,
                            "tokenTimestamp": dayTimestamp
                        }
                        data[dayTimestamp] = dayData

                    valuesToInsert.append([row[0], row[1], row[2], row[3], row[4], row[5], row[6], dayData["token"], dayData["tokenTimestamp"]])

                if valuesToInsert:
                    self.database.execute("DELETE FROM %s" % self._tableName)
                    self.database.executeMany("INSERT INTO %s(ts_started, usersch_id, zid, user_sec, machine_sec, real_sec, flag, token, tokenTimestamp) "\
                                              "VALUES(?,?,?,?,?,?,?,?,?)" % self._tableName, valuesToInsert)
                    self.database.commit()
                    result = True
            except Exception, e:
                log.exception(e)

            v1DB.close()
            return result

        return False

##-----------------------------------------------------------------------------------------------------
##
##

class RMAvailableWaterTable(RMTable):
    def __init__(self, database, fake = False):
        self._tableName = "availableWater_fake" if fake else "availableWater"
        RMTable.__init__(self, database)

    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS %s ("\
                                    "day INTEGER NOT NULL , "\
                                    "pid INTEGER NOT NULL , "\
                                    "zid INTEGER NOT NULL , "\
                                    "aw REAL NOT NULL "\
                            ")" % self._tableName)
        self.database.commit()

    def addRecord(self, dayTimestamp, programID, zoneID, availableWater, commit = True):
        if(self.database.isOpen()):
            self.database.execute("DELETE FROM %s WHERE day=? AND pid=? AND zid=?" % self._tableName, (dayTimestamp, programID, zoneID))
            self.database.execute("INSERT OR REPLACE INTO %s VALUES(?, ?, ?, ?)" % self._tableName, (dayTimestamp, programID, zoneID, availableWater))
            if commit:
                self.database.commit()
            return True
        return False

    def getLastRecord(self, dayTimestamp, programID, zoneID):
        if(self.database.isOpen()):
            row = self.database.execute("SELECT aw FROM %s WHERE day=? AND pid=? AND zid=? ORDER BY ROWID DESC LIMIT 1" % self._tableName,
                                        (dayTimestamp, programID, zoneID)).fetchone()
            if row:
                return row[0]
        return None

    def getLastRecords(self, dayTimestamp, programID):
        if(self.database.isOpen()):
            results = {}

            records  = self.database.execute("SELECT zid, aw FROM %s WHERE day=? AND pid=? ORDER BY zid ASC" % self._tableName, (dayTimestamp, programID))
            for row in records:
                results[row[0]] = row[1]
            return results
        return None

    def getAllRecords(self):
        if(self.database.isOpen()):
            results = []

            records  = self.database.execute("SELECT day, pid, zid, aw FROM %s ORDER BY day DESC, pid ASC, zid ASC" % self._tableName)
            for row in records:
                results.append(RMAvailableWaterValues(row[0], row[1], row[2], row[3]))
            return results
        return None

    def getRecordsEx(self, minTimestamp, maxTimestamp):
        if(self.database.isOpen()):
            results = []

            if minTimestamp and maxTimestamp:
                records = self.database.execute("SELECT day, pid, zid, aw FROM %s WHERE ?<=day AND day<? "
                                                "ORDER BY day DESC, pid ASC, zid ASC"
                                                % self._tableName, (minTimestamp, maxTimestamp)
                                                )
            elif minTimestamp:
                records = self.database.execute("SELECT day, pid, zid, aw FROM %s WHERE ?<=day "
                                                 "ORDER BY day DESC, pid ASC, zid ASC" % self._tableName, (minTimestamp, )
                                                )
            elif maxTimestamp:
                records = self.database.execute("SELECT day, pid, zid, aw FROM %s  WHERE day<? "
                                                 "ORDER BY day DESC, pid ASC, zid ASC" % self._tableName, (maxTimestamp, )
                                                )
            else:
                records = self.database.execute("SELECT day, pid, zid, aw FROM %s "\
                                                 "ORDER BY day DESC, pid ASC, zid ASC" % self._tableName
                                                )

            for row in records:
                results.append(RMAvailableWaterValues(row[0], row[1], row[2], row[3]))
            return results

        return None


##-----------------------------------------------------------------------------------------------------
##
##

class RMAdjustedSchTable(RMTable):
    def initialize(self):
        # adjusted_schedule table #TODO Obsolete once new schedulectrl/valved implementation is ready
        self.database.execute("CREATE TABLE IF NOT EXISTS adjusted_schedule ("\
                                    "uid INTEGER PRIMARY KEY AUTOINCREMENT  NOT NULL , "\
                                    "zid INTEGER NOT NULL , "\
                                    "start_dt INTEGER NOT NULL , "\
                                    "duration INTEGER, "\
                                    "balance INTEGER, "\
                                    "user_uid INTEGER NOT NULL DEFAULT -1"\
                            ")")
        self.database.commit()

    def addRecords(self):
        if(self.database.isOpen()):
            return True
        return False

##-----------------------------------------------------------------------------------------------------
##
##
class RMPastValuesTable(RMTable):
    def __init__(self, database, fake = False):
        self._tableName = "pastValues_fake" if fake else "pastValues"
        RMTable.__init__(self, database)

    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS %s ("\
                                    "pid INTEGER NOT NULL , "\
                                    "timestamp INTEGER NOT NULL , "\
                                    "used INTEGER NOT NULL , "\
                                    "et0 DECIMAL DEFAULT NULL, "\
                                    "qpf DECIMAL DEFAULT NULL, "\
                                    "PRIMARY KEY(pid, timestamp)"\
                            ")" % self._tableName)
        self.database.commit()

    def addRecord(self, programId, timestamp, et0, qpf, used = False):
        if self.database.isOpen():
            if used:
                used = 1
            else:
                used = 0

            record = self.database.execute("SELECT used FROM %s WHERE used=1 AND pid=? AND timestamp=?" %self._tableName, (programId, timestamp)).fetchone()
            if not record:

                self.database.execute("INSERT OR REPLACE INTO %s VALUES (?, ?, ?, ?, ?)" % self._tableName,
                                  (programId, timestamp, used, et0, qpf))
                self.database.commit()

    def markRecordsAsUsed(self, programId, timestamp):
        if self.database.isOpen():
            self.database.execute("UPDATE %s SET used=1 WHERE pid=? AND timestamp=?" % self._tableName, (programId, timestamp))
            self.database.commit()

    def getLastRecordByThreshold(self, programId, startDate, endDate):
        if self.database.isOpen():
            if startDate is None or endDate is None:
                record  = self.database.execute("SELECT pv1.* FROM %s pv1 "\
                                                "INNER JOIN (SELECT DISTINCT rowid, MAX(timestamp) timestamp FROM %s WHERE pid=?) pv2 "\
                                                "ON pv1.rowid=pv2.rowid" % (self._tableName, self._tableName), (programId, )).fetchone()
            else:
                record  = self.database.execute("SELECT pv1.* FROM %s pv1 "\
                                                "INNER JOIN (SELECT DISTINCT rowid, MAX(timestamp) timestamp FROM %s WHERE pid=? AND ?<=timestamp AND timestamp<=?) pv2 "\
                                                "ON pv1.rowid=pv2.rowid" % (self._tableName,  self._tableName), (programId, startDate, endDate)).fetchone()
            if record:
                return RMPastValues(record[0], record[1], record[2], record[3], record[4])
        return None

    def getLastTimestampsByProgram(self):
        if self.database.isOpen():
            values = {}

            cursor = self.database.execute("SELECT pid, MAX(timestamp) FROM %s WHERE used=1 GROUP BY pid" % self._tableName)
            for row in cursor:
                values[row[0]] = row[1]

            return values

        return None

    def getRecordsByThreshold(self, startDate, endDate):
        if self.database.isOpen():
            values = []
            if startDate is None or endDate is None:
                cursor  = self.database.execute("SELECT pv1.* FROM %s pv1 "\
                                                "INNER JOIN (SELECT DISTINCT rowid, timestamp FROM %s) pv2 "\
                                                "ON pv1.rowid=pv2.rowid" % (self._tableName, self._tableName))
            else:
                cursor  = self.database.execute("SELECT pv1.* FROM %s pv1 "\
                                                "INNER JOIN (SELECT DISTINCT rowid, timestamp FROM %s WHERE ?<=timestamp AND timestamp<=?) pv2 "\
                                                "ON pv1.rowid=pv2.rowid" % (self._tableName,  self._tableName), (startDate, endDate))
            for row in cursor:
                values.append(RMPastValues(row[0], row[1], row[2], row[3], row[4]))

            return values

        return None

    def getAllRecords(self):
        if self.database.isOpen():
            values = []

            cursor = self.database.execute("SELECT pid, timestamp, used, et0, qpf FROM %s GROUP BY pid ORDER BY timestamp" % self._tableName)
            for row in cursor:
                values.append(RMPastValues(row[0], row[1], row[2], row[3], row[4]))

            return values

        return None

##-----------------------------------------------------------------------------------------------------
##
##
class RMWaterSenseTable(RMTable):
    def __init__(self, database, fake = False):
        self._tableName = "waterSense_fake" if fake else "waterSense"
        RMTable.__init__(self, database)

    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS %s ("\
                                    "zid INTEGER NOT NULL, "\
                                    "timestamp INTEGER NOT NULL , "\
                                    "day INTEGER NOT NULL , "\
                                    "startWaterLevel DECIMAL NOT NULL," \
                                    "PRIMARY KEY(zid, day)"\
                            ")" % self._tableName)
        self.database.commit()

    def addRecord(self, zid, timestamp, day, startWaterLevel):
        if(self.database.isOpen()):
            try:
                self.database.execute("INSERT OR REPLACE INTO %s(zid, timestamp, day, startWaterLevel) "\
                                            "VALUES(?, ?, ?, ?)" % self._tableName,
                                      (zid, timestamp, day, startWaterLevel))

                self.database.commit()

                return True
            except Exception, e:
                log.error(e)
        return False

    def findRecord(self, zid, day):
        if(self.database.isOpen()):
            record = self.database.execute("SELECT startWaterLevel FROM %s WHERE zid=? AND day=?" % self._tableName, (zid, day)).fetchone()
            if record:
                return record[0]

        return None

##-----------------------------------------------------------------------------------------------------
##
##
class RMMainDataTable(RMTable):
    def initialize(self):
        self.userSchTable = RMUserSchTable(self.database, False)
        self.userSchTableFake = RMUserSchTable(self.database, True)
        self.zonesTable = RMZonesTable(self.database)
        self.savingsTable = RMSavingsTable(self.database)
        self.statusTable = RMStatusTable(self.database)
        self.waterLogTable = RMWaterLogTable(self.database, False)
        self.waterLogTableFake = RMWaterLogTable(self.database, True)
        self.availableWaterTable = RMAvailableWaterTable(self.database, False)
        self.availableWaterTableFake = RMAvailableWaterTable(self.database, True)
        self.adjustedSchTable = RMAdjustedSchTable(self.database)
        self.pastValuesTable = RMPastValuesTable(self.database, False)
        self.pastValuesTableFake = RMPastValuesTable(self.database, True)
        self.waterSenseTable = RMWaterSenseTable(self.database, False)
        self.waterSenseTableFake = RMWaterSenseTable(self.database, True)
