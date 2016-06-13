# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMDatabaseFramework.rmUserSettingsTable import RMUserSettingsTable, RMUserSettingsHourlyRestrictionsTable
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmRainSensor import RMRainSensor, RMRainSensorSoftware

class RMUserSettingsGlobalRestrictions:
    def __init__(self):
        self.minFreezeControlTemp = 2
        self.useFreezeControlTemp = False
        self.noWaterInMonths = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.noWaterInWeekDays = [0, 0 ,0, 0, 0, 0, 0]
        self.rainDelayStartTime = -1
        self.rainDelayDuration = 0
        self.hotDaysExtraWatering = False

    def asDict(self):
        return dict((key, value) for key, value in self.__dict__.iteritems() if not callable(value) and not key.startswith('_'))

    def validateUnicodeDict(self, data):
        try:
            if u"freezeProtectEnabled" in data:
                bool(data[u"freezeProtectEnabled"])

            if u"freezeProtectTemp" in data:
                float(data[u"freezeProtectTemp"])

            if u"noWaterInWeekDays" in data:
                if len(list(str(data[u"noWaterInWeekDays"]))) != 7:
                    return False

            if u"noWaterInMonths" in data:
                if len(list(str(data[u"noWaterInMonths"]))) != 12:
                    return False

            if u"rainDelayStartTime" in data:
                int(data[u"rainDelayStartTime"])

            if u"rainDelayDuration" in data:
                int(data[u"rainDelayDuration"])

            if u"hotDaysExtraWatering" in data:
                bool(data[u"hotDaysExtraWatering"])

            return True

        except:
            pass

        return False

    def updateFromUnicodeDict(self, data):
        if u"freezeProtectEnabled" in data:
            self.useFreezeControlTemp = bool(data[u"freezeProtectEnabled"])

        if u"freezeProtectTemp" in data:
            self.minFreezeControlTemp = float(data[u"freezeProtectTemp"])

        if u"noWaterInWeekDays" in data:
            self.noWaterInWeekDays = map(int, list(str(data[u"noWaterInWeekDays"])))

        if u"noWaterInMonths" in data:
            self.noWaterInMonths = map(int, list(str(data[u"noWaterInMonths"])))

        if u"rainDelayStartTime" in data:
            self.rainDelayStartTime = int(data[u"rainDelayStartTime"])

        if u"rainDelayDuration" in data:
            self.rainDelayDuration = int(data[u"rainDelayDuration"])

        if u"hotDaysExtraWatering" in data:
            self.hotDaysExtraWatering = bool(data[u"hotDaysExtraWatering"])

    def __repr__(self):
        v = vars(self)
        return ",".join([":".join((k, str(v[k]))) for k in v if not k.startswith("_")])


class RMUserSettingsHourlyRestriction:
    def __init__(self, uid=-1):
        self.uid = uid
        self.dayStartMinute = 13 * 60  # 13:00 in minutes
        self.minuteDuration = 2 * 60
        self.onWeekDays = [0, 0, 0, 0, 0, 0, 0]  # all set 1 is daily - [MTWTFSS]

    def update(self, dayStartMinute, minuteDuration, dayList):
        if dayStartMinute is not None:
            self.dayStartMinute = dayStartMinute
        if minuteDuration is not None:
            self.minuteDuration = minuteDuration
        if dayList is not None or len(dayList) == 7:
            self.onWeekDays = [d for d in dayList]

    def asDict(self):
        return dict((key, value) for key, value in self.__dict__.iteritems() if not callable(value) and not key.startswith('_'))

    def __repr__(self):
        v = vars(self)
        return ",".join([":".join((k, str(v[k]))) for k in v if not k.startswith("_")])


class RMRestrictions:
    def __init__(self):

        self.globalRestrictions = RMUserSettingsGlobalRestrictions()
        self.rainSensor = RMRainSensor()
        self.rainSensorSoftware = RMRainSensorSoftware()
        self.hourlyRestrictions = {}

        self.__dayMinTemperature = {} # Used by freeze protect
        self.__hourlyRestrictionsTable = None

    def setDatabase(self, settingsDatabase):
        self.__hourlyRestrictionsTable = RMUserSettingsHourlyRestrictionsTable(settingsDatabase)

    def loadSettings(self):
        self.__hourlyRestrictionsTable.loadAllRestrictions(self.hourlyRestrictions, RMUserSettingsHourlyRestriction)

    # -----------------------------------------------------------------------------------------------------------
    #
    #
    def newHourlyRestriction(self, dayMinuteStart, minuteDuration, dayList=None):  # dayList all 1 - Daily

        if dayList is None:
            dayList = [1] * 7

        if len(dayList) < 7:
            log.error("Invalid day list received")
            return False

        r = RMUserSettingsHourlyRestriction()
        r.dayStartMinute = dayMinuteStart
        r.minuteDuration = minuteDuration
        r.onWeekDays = [d for d in dayList]

        # Save the restriction
        result = self.__hourlyRestrictionsTable.saveRestriction(r)

        self.hourlyRestrictions[r.uid] = r

        return r

    def updateHourlyRestriction(self, uid, dayMinuteStart, minuteDuration, dayList=None):

        r = self.hourlyRestrictions.get(uid, None)

        if r is not None:
            r.update(dayMinuteStart, minuteDuration, dayList)
            # Save the restriction in DB
            result = self.__hourlyRestrictionsTable.saveRestriction(r)

        return r


    def deleteHourlyRestriction(self, uid):
        if uid is None or not uid in self.hourlyRestrictions:
            return False

        if self.__hourlyRestrictionsTable.deleteRestriction(uid):
            self.hourlyRestrictions.pop(uid)
            return True
        return False

    # -----------------------------------------------------------------------------------------------------------
    # Checks if timestamp is in the raindelay restriction. Returns -1 if not or remaining seconds if it is
    #
    def getRainDelayRestriction(self, timestamp):

        rainDelayEndTimestamp = self.globalRestrictions.rainDelayStartTime + self.globalRestrictions.rainDelayDuration

        if self.globalRestrictions.rainDelayStartTime <= timestamp and timestamp <= rainDelayEndTimestamp:
            return (rainDelayEndTimestamp - timestamp)

        return -1

    # --------------------------------------------------------------------------------------------------------------
    # Checks if day is a restriction that affects the entire day (month, day of week, freeze protect, or rain delay)
    # Returns the exact restriction id
    #
    def getDayGlobalRestriction(self, timestamp, ignoreFreezeProtect=False):
        # Cyclic import workaround
        from RMDataFramework.rmMainDataRecords import RMZoneWateringFlag

        if self.isInMonthRestriction(timestamp):
            return RMZoneWateringFlag.zwfRestrictionMonth

        if self.isInDayRestriction(timestamp):
            return RMZoneWateringFlag.zwfRestrictionDay

        if self.getRainDelayRestriction(timestamp) > 0:
            log.debug("Restricted for rain delay")
            return RMZoneWateringFlag.zwfRestrictionRainDelay

        if not ignoreFreezeProtect and self.isInFreezeProtect(timestamp):
            return RMZoneWateringFlag.zwfRestrictionFreezeProtect

        return RMZoneWateringFlag.zwfNormal

    def getDayHourlyRestriction(self, timestamp):
        dayTimestamp = rmGetStartOfDay(timestamp)
        d = datetime.fromtimestamp(dayTimestamp)
        weekDay = d.weekday()
        rWithTimestamps = []

        # generate timestamp restriction array from dayMinuteDuration -> +minuteDuration taking onWeekDays in account
        for r in self.hourlyRestrictions.values():
            if r.onWeekDays[weekDay]:
                rWithTimestamps.append((dayTimestamp + r.dayStartMinute * 60,
                                        dayTimestamp + r.dayStartMinute * 60 + r.minuteDuration * 60))  # in seconds

        rUnion = []
        for begin, end in sorted(rWithTimestamps):
            if rUnion and rUnion[-1][1] >= begin - 1 * 60:  # intersect by minute a timestamp in seconds
                rUnion[-1] = (rUnion[-1][0], end)
            else:
                rUnion.append((begin, end))

        # DEBUG Human readable format
        wantRestrictionTrace = False
        if wantRestrictionTrace:
            log.debug("USER RESTRICTIONS")
            for r in self.hourlyRestrictions.values():
                log.debug(" (%d:%d - %d:%d), " % (r.dayStartMinute / 60, r.dayStartMinute % 60,
                                                  (r.dayStartMinute + r.minuteDuration) / 60, (r.dayStartMinute + r.minuteDuration) % 60 ))

            log.debug("USER TIMESTAMP RESTRICTIONS")
            for t in sorted(rWithTimestamps):
                s = datetime.utcfromtimestamp(t[0])
                e = datetime.utcfromtimestamp(t[1])
                log.debug(" (%d:%d - %d:%d), " % (s.hour, s.minute, e.hour, e.minute))

            log.debug("INTERSECTED RESTRICTIONS")
            for t in sorted(rUnion):
                s = datetime.utcfromtimestamp(t[0])
                e = datetime.utcfromtimestamp(t[1])
                log.debug(" (%d:%d - %d:%d), " % (s.hour, s.minute, e.hour, e.minute))
        else:
            if rUnion:
                log.debug("Day %d restrictions %s" % (dayTimestamp, rUnion))
        ### END DEBUG Human readable format

        return rUnion

    def getMinTemperature(self):
        return self.__dayMinTemperature.get(rmGetStartOfDay(rmCurrentTimestamp()), None)

    def isInFreezeProtect(self, timestamp):
        if self.globalRestrictions.useFreezeControlTemp:
            dayMinTemp = self.__dayMinTemperature.get(rmGetStartOfDay(timestamp), None)

            if dayMinTemp is None:
                log.debug("No minimum temperature for %d found, won't restrict." % rmGetStartOfDay(timestamp))
                return False

            if int(dayMinTemp) <= int(self.globalRestrictions.minFreezeControlTemp):
                log.debug("Restricted for minimum temperature %s <= %s" % \
                          (`dayMinTemp`, `self.globalRestrictions.minFreezeControlTemp`))
                return True

        return False

    def isInMonthRestriction(self, timestamp):
        d = datetime.fromtimestamp(timestamp)
        currentMonth = d.month - 1

        if self.globalRestrictions.noWaterInMonths[currentMonth] == 1:
            log.debug("Restricted for %d month" % (currentMonth))
            return True

        return False

    def isInDayRestriction(self, timestamp):
        d = datetime.fromtimestamp(timestamp)
        currentWeekDay = d.weekday()

        if self.globalRestrictions.noWaterInWeekDays[currentWeekDay] == 1:
            log.debug("Restricted for %d weekday" % currentWeekDay)
            return True

        return False

    # Used by FreezeProtect restriction
    def setDayMinTemperature(self, dayTimestamp, minTemperature):
        if dayTimestamp is not None:
            self.__dayMinTemperature[dayTimestamp] = minTemperature
            log.debug("Setting minimum temperature %f for day: %d(%s)" %
                      (minTemperature, dayTimestamp, rmTimestampToDateAsString(dayTimestamp)))

    def clearDayMinTemperature(self):
        self.__dayMinTemperature = {}
