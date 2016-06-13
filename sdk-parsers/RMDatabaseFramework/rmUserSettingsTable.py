# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from collections import OrderedDict
from rmDatabase import RMTable
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmAuthData import RMAuthToken

##-----------------------------------------------------------------------------------------------------
##
##
class RMUserSettingsHourlyRestrictionsTable(RMTable):

    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS hourlyRestrictions "\
                              "(uid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, "\
                              "dayStartMinute INTEGER NOT NULL, "\
                              "minuteDuration INTEGER NOT NULL, "\
                              "onWeekDays VARCHAR "\
                              ")")
        self.database.commit()

    def saveRestriction(self, restrictionObject):
        if self.database.isOpen():

            if restrictionObject.uid == -1: # new restriction insert
                self.database.execute("INSERT INTO hourlyRestrictions (dayStartMinute, minuteDuration, onWeekDays) "\
                                      "VALUES (?, ?, ?)", (restrictionObject.dayStartMinute, restrictionObject.minuteDuration,
                                      str(restrictionObject.onWeekDays)))
                _uid = self.database.lastRowId()
                restrictionObject.uid = _uid
            else: # update restriction
                self.database.execute("UPDATE hourlyRestrictions SET dayStartMinute=?, minuteDuration=?, "
                                      "onWeekDays=? WHERE uid=?",(restrictionObject.dayStartMinute, restrictionObject.minuteDuration,
                                        str(restrictionObject.onWeekDays), restrictionObject.uid) )

            self.database.commit()
            return True

        return False

    def deleteRestriction(self, uid):
        if self.database.isOpen():
            self.database.execute("DELETE FROM hourlyRestrictions WHERE uid=?", (uid, ))
            self.database.commit()
            return True
        return False

    def loadRestriction(self, uid, restrictionClass):
        if self.database.isOpen():
            cursor = self.database.execute("SELECT * FROM hourlyRestrictions WHERE uid=?", uid)

            for row in cursor:
                restriction = restrictionClass(row["uid"])
                restriction.dayStartMinute = row["dayStartMinute"]
                restriction.minuteDuration = row["minuteDuration"]
                tmpWeekDays = row["onWeekDays"]
                restriction.onWeekDays = [ int(d) for d in tmpWeekDays[1:-1].split(",")]

            return restriction
        return None

    def loadAllRestrictions(self, restrictionsDict, restrictionClass):
        if self.database.isOpen():
            cursor = self.database.execute("SELECT * FROM hourlyRestrictions ORDER BY uid ASC")

            for row in cursor:

                restriction = restrictionClass(row["uid"])
                restriction.dayStartMinute = row["dayStartMinute"]
                restriction.minuteDuration = row["minuteDuration"]
                tmpWeekDays = row["onWeekDays"]
                restriction.onWeekDays = [ int(d) for d in tmpWeekDays[1:-1].split(",")]

                restrictionsDict[row["uid"]] = restriction
            return True

        return False


##-----------------------------------------------------------------------------------------------------
##
##

class RMUserSettingsTable(RMTable):
    # How the bool values are saved in DB
    RMUserSettingsBoolTranslation = ["OFF", "ON"]

    def initialize(self):
        #settings table
        self.database.execute("CREATE TABLE IF NOT EXISTS auth ("\
                                    "password VARCHAR(128) PRIMARY KEY NOT NULL"\
                            ")")

        self.database.execute("CREATE TABLE IF NOT EXISTS system ("\
                                    "key VARCHAR, "\
                                    "value VARCHAR "\
                            ")")

        self.database.execute("CREATE TABLE IF NOT EXISTS location ("\
                                    "key VARCHAR, "\
                                    "value VARCHAR "\
                            ")")

        self.database.execute("CREATE TABLE IF NOT EXISTS globalRestrictions ("\
                                    "key VARCHAR, "\
                                    "value VARCHAR "\
                            ")")

        self.database.execute("CREATE TABLE IF NOT EXISTS cloud ("\
                                    "key VARCHAR, "\
                                    "value VARCHAR "\
                            ")")

        self.database.commit()

    def savePassword(self, password):
        if (self.database.isOpen()):
            self.database.execute("DELETE FROM auth")
            self.database.execute("INSERT INTO auth VALUES(?)", (password, ))
            self.database.commit()

    def getPassword(self):
        if (self.database.isOpen()):
            row = self.database.execute("SELECT password FROM auth").fetchone()
            if row:
                return str(row[0])
        return None

    def deleteAll(self):
        if (self.database.isOpen()):

            self.database.execute("DELETE FROM system")
            self.database.execute("DELETE FROM location")
            self.database.execute("DELETE FROM globalRestrictions")
            self.database.execute("DELETE FROM cloud")

            return True
        return False

    def saveRecords(self, systemValues, locationValues, restrictionValues, cloudValues):

        if(self.database.isOpen()):

            self.__executeKeyValueUpsert("system", systemValues)
            self.__executeKeyValueUpsert("location", locationValues)
            self.__executeKeyValueUpsert("globalRestrictions", restrictionValues)
            self.__executeKeyValueUpsert("cloud", cloudValues)

            self.database.commit()
            return True
        return False

    def loadAllRecords(self, settingsInstance):
        if (self.database.isOpen()):

            d = self.__readRecordsFromTable("system")
            settingsInstance.__dict__.update(d)

            d = self.__readRecordsFromTable("location")
            settingsInstance.location.__dict__.update(d)

            d = self.__readRecordsFromTable("globalRestrictions")
            settingsInstance.restrictions.globalRestrictions.__dict__.update(d)

            d = self.__readRecordsFromTable("cloud")
            settingsInstance.cloud.__dict__.update(d)

            d = None
            return True
        return False

    def __readRecordsFromTable(self, tableName):
        d = {}
        if (self.database.isOpen()):
            cursor = self.database.execute("SELECT key, value FROM " + tableName)
            records = cursor.fetchall()
            for r in records:
                # Translate to float or to True/False
                try:
                    tmpValue = float(r["value"])
                    if tmpValue.is_integer():
                        tmpValue = int(tmpValue)
                except:
                    try:
                        tmpValue = eval(r["value"])
                    except:
                        tmpValue = r["value"]

                if tmpValue == "ON":
                    tmpValue = True
                elif tmpValue == "OFF":
                    tmpValue = False

                d[r["key"]] = tmpValue

            records = None
            cursor = None

        return d


    def __executeKeyValueUpsert(self, tableName, values):

         # Translate bool to ON/OFF
        for k,v in values.iteritems():
            if type(v) == bool:
                values[k] = self.RMUserSettingsBoolTranslation[int(v)]

        valuesToInsert = []
        valuesToUpdate = []

        # get existing records for globals table
        cursor = self.database.execute("SELECT * FROM " + tableName)
        existingRecords = cursor.fetchall()

        # Add items to list for SQL UPDATE
        for r in existingRecords:
            if r["key"] in values.keys():
                #log.debug("Existing key %s in cursor" % r["key"])
                valuesToUpdate.append((str(values.get(r["key"])), r["key"]))
                values.pop(r["key"], None)

        #Add items to list for SQL INSERT
        valuesToInsert = [(k, str(v)) for k,v in values.iteritems()]

        self.database.executeMany("UPDATE " + tableName + " SET value=? WHERE key=?", valuesToUpdate)
        self.database.executeMany("INSERT INTO " + tableName + " (key, value) VALUES (?, ?)", valuesToInsert)

        valuesToInsert = None
        valuesToUpdate = None
        existingRecords = None
        cursor = None

##-----------------------------------------------------------------------------------------------------
##
##
class RMAuthTokensTable(RMTable):
    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS authTokens ("\
                                    "token TEXT PRIMARY KEY NOT NULL, " \
                                    "expiration INTEGER NOT NULL)"
                            )
        self.database.commit()

    def addRecord(self, token, expiration):
        if self.database.isOpen():
            self.database.execute("INSERT OR REPLACE INTO authTokens VALUES (?, ?)", (token, expiration))
            self.database.commit()

    def deleteRecord(self, token):
        if self.database.isOpen():
            self.database.execute("DELETE FROM authTokens WHERE token=?", (token, ))
            self.database.commit()

    def deleteExpiredRecords(self, timestamp):
        if self.database.isOpen():
            self.database.execute("DELETE FROM authTokens WHERE expiration<?", (timestamp, ))
            self.database.commit()

    def deleteAllRecords(self):
        if self.database.isOpen():
            self.database.execute("DELETE FROM authTokens")
            self.database.commit()

    def getAllRecords(self, asDict = True):
        if self.database.isOpen():
            if asDict:
                records = OrderedDict()
            else:
                records = []

            rows = self.database.execute("SELECT token, expiration FROM authTokens")
            for row in rows:
                if asDict:
                    records[str(row[0])] = RMAuthToken(str(row[0]), row[1])
                else:
                    records.append(RMAuthToken(str(row[0]), row[1]))

            return records

        return None
