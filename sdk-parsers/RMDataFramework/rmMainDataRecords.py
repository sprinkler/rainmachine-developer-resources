# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>

from RMDataFramework.rmUserSettings import globalSettings
import os, shutil, time, stat
from RMUtilsFramework.rmLogging import log
from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp

# Can be used as base class for a class that has public members with
# same name as their database keys
class publicMembersAsDBKey:
    def __init__(self):
        pass
    def getDBKeys(self):
        keys = []
        for key in vars(self):
            if not key.startswith("__"):
                keys.append(key)
        return keys

##-----------------------------------------------------------------------------------------------------
##
##
class RMZoneTypes:
    ztNone = 1
    ztGrass = 2
    ztFruitTrees = 3
    ztFlowers = 4
    ztVegetables = 5
    ztCitrus = 6
    ztBushes = 7

    parameters = {
        ztNone:         {"cropCoef": 0.80, "allowedDepletion": 0.40, "rootDepth": 20.32, "isTall": False},
        ztGrass:        {"cropCoef": 0.80, "allowedDepletion": 0.40, "rootDepth": 20.32, "isTall": False},
        ztFruitTrees:   {"cropCoef": 0.95, "allowedDepletion": 0.50, "rootDepth": 101.6, "isTall": True},
        ztFlowers:      {"cropCoef": 1.00, "allowedDepletion": 0.50, "rootDepth": 22.86, "isTall": True},
        ztVegetables:   {"cropCoef": 1.15, "allowedDepletion": 0.35, "rootDepth": 45.72, "isTall": True},
        ztCitrus:       {"cropCoef": 0.65, "allowedDepletion": 0.50, "rootDepth": 101.6, "isTall": True},
        ztBushes:       {"cropCoef": 1.00, "allowedDepletion": 0.50, "rootDepth": 71.12, "isTall": True},
    }

    @staticmethod
    def getDefaultCropCoef(type):
        return RMZoneTypes.parameters[type]["cropCoef"]

    @staticmethod
    def getDefaultAllowedDepletion(type):
        return RMZoneTypes.parameters[type]["allowedDepletion"]

    @staticmethod
    def getDefaultRootDepth(type):
        return RMZoneTypes.parameters[type]["rootDepth"]

    @staticmethod
    def getDefaultIsTall(type):
        return RMZoneTypes.parameters[type]["isTall"]



class RMZoneSoil:
    Clay = 1
    SiltyClay = 2
    ClayLoam = 3
    Loam = 4
    SandyLoam = 5
    LoamySand = 6
    Sand = 7
    Other = 99

    parameters = {
        Clay:       {"intakeRate": 0.254,  "availableWater": 0.4318},
        SiltyClay:  {"intakeRate": 0.381,  "availableWater": 0.4318},
        ClayLoam:   {"intakeRate": 0.508,  "availableWater": 0.4572},
        Loam:       {"intakeRate": 0.889,  "availableWater": 0.4318},
        SandyLoam:  {"intakeRate": 1.016,  "availableWater": 0.3302},
        LoamySand:  {"intakeRate": 1.270,  "availableWater": 0.2286},
        Sand:       {"intakeRate": 1.524,  "availableWater": 0.0762},
        Other:      {"intakeRate": 0.889,  "availableWater": 0.4318},
    }

    @staticmethod
    def getDefaultIntakeRate(soilType):
        return RMZoneSoil.parameters[soilType]["intakeRate"]

    @staticmethod
    def getDefaultAvailableWater(soilType):
        return RMZoneSoil.parameters[soilType]["availableWater"]


class RMZoneSprinkler:
    PopupSpray = 1
    Rotors = 2
    SurfaceDrip = 3
    Bubblers = 4
    Other = 99

    parameters = {
        PopupSpray:     {"precipRate": 3.556, "appEfficiency": 0.70},
        Rotors:         {"precipRate": 0.889, "appEfficiency": 0.65},
        SurfaceDrip:    {"precipRate": 0.508, "appEfficiency": 0.80},
        Bubblers:       {"precipRate": 2.540, "appEfficiency": 0.75},
        Other:          {"precipRate": 2.540, "appEfficiency": 0.75},
    }

    @staticmethod
    def getDefaultPrecipRate(sprinklerType):
        return RMZoneSprinkler.parameters[sprinklerType]["precipRate"]

    @staticmethod
    def getDefaultAppEfficiency(sprinklerType):
        return RMZoneSprinkler.parameters[sprinklerType]["appEfficiency"]


class RMZoneSlope:
    Flat = 1
    Moderate = 2
    High = 3
    VeryHigh = 4
    Other = 99

    parameters = {
        Flat: {
            RMZoneSoil.Clay:       5.08,
            RMZoneSoil.SiltyClay:  5.84,
            RMZoneSoil.ClayLoam:   6.60,
            RMZoneSoil.Loam:       7.62,
            RMZoneSoil.SandyLoam:  8.38,
            RMZoneSoil.LoamySand:  9.14,
            RMZoneSoil.Sand:       10.16
        },
        Moderate: {
            RMZoneSoil.Clay:       3.81,
            RMZoneSoil.SiltyClay:  4.83,
            RMZoneSoil.ClayLoam:   5.60,
            RMZoneSoil.Loam:       6.35,
            RMZoneSoil.SandyLoam:  7.37,
            RMZoneSoil.LoamySand:  7.62,
            RMZoneSoil.Sand:       8.90
        },
        High: {
            RMZoneSoil.Clay:       2.54,
            RMZoneSoil.SiltyClay:  4.06,
            RMZoneSoil.ClayLoam:   4.57,
            RMZoneSoil.Loam:       5.33,
            RMZoneSoil.SandyLoam:  6.10,
            RMZoneSoil.LoamySand:  6.60,
            RMZoneSoil.Sand:       7.62
        },
        VeryHigh: {
            RMZoneSoil.Clay:       2.54,
            RMZoneSoil.SiltyClay:  3.30,
            RMZoneSoil.ClayLoam:   3.81,
            RMZoneSoil.Loam:       4.32,
            RMZoneSoil.SandyLoam:  5.08,
            RMZoneSoil.LoamySand:  5.59,
            RMZoneSoil.Sand:       6.35
        },
        Other: {
            RMZoneSoil.Clay:       5.08,
            RMZoneSoil.SiltyClay:  5.84,
            RMZoneSoil.ClayLoam:   6.60,
            RMZoneSoil.Loam:       7.62,
            RMZoneSoil.SandyLoam:  8.38,
            RMZoneSoil.LoamySand:  9.14,
            RMZoneSoil.Sand:       10.16
        }
    }

    @staticmethod
    def getDefaultAllowedSurfaceAcc(slope, soil):
        return RMZoneSlope.parameters[slope][soil]


class RMZoneExposure:
    FullSun = 1
    PartialShade = 2
    FullShade = 3
    Other = 99

    parameters = {
        FullSun:        {"exposureCoef": 1.00},
        PartialShade:   {"exposureCoef": 0.80},
        FullShade:      {"exposureCoef": 0.60},
        Other:          {"exposureCoef": 0.60},
    }

    @staticmethod
    def getDefaultExposureCoef(exposureType):
        return RMZoneExposure.parameters[exposureType]["exposureCoef"]



class RMZoneWateringFlag:
    zwfNormal = 0
    zwfStopByUser = 1
    zwfRestrictionThreshold = 2
    zwfRestrictionFreezeProtect = 3
    zwfRestrictionDay = 4
    zwfRestrictionOutOfDay = 5
    zwfWaterSurplus = 6
    zwfRainSensor = 7
    zwfRainSensorSoftware = 8
    zwfRestrictionMonth = 9
    zwfRestrictionRainDelay = 10


class RMZoneData:
    def __init__(self, uid = -1):
        self.uid = uid
        self.name = "New Zone"
        self.valveid = -1
        self.ETcoef = 1.0
        self.active = True
        self.type = RMZoneTypes.ztNone
        self.internet = True
        self.savings = 50
        self.slope = 1
        self.sun = 1
        self.soil = 1
        self.group_id = 0
        self.history = True
    def __repr__(self):
        v = vars(self)
        return ", ".join([":".join((k, str(v[k]))) for k in v if not k.startswith("_")])


class RMZoneAdvancedData:
    def __init__(self, zid = -1):
        self.zid = zid
        self.reset()

    def __repr__(self):
        v = vars(self)
        return ", ".join([":".join((k, str(v[k]))) for k in v if not k.startswith("_")])

    def reset(self):
        self.SoilIntakeRate = 0.0
        self.AvailableWater = 0.0
        self.MaxAllowedDepletion = 0.0
        self.RootDepth = 0
        self.isTallPlant = False
        self.PrecipRate = 0.0
        self.AppEfficiency = 0.0
        self.AllowedSurfaceAcc = 0.0
        self.FieldCapacity = 0.0
        self.PermWilting = 0.0
        self.MaxRuntime = 0
        self.DetailedMonthsKc = [1] * 12
        self.StartWaterLevel = 0

        # Fields used by water sense. They are not saved to DB.
        self.fFCd = 0
        self.fPWPd = 0
        self.fRAW_RZWWS = 0
        self.fRP = 0
        self.fPR_mm_min_gross = 0
        self.fInitWaterLevel = 0


class RMZone(RMZoneData, RMZoneAdvancedData):
    def __init__(self, uid = -1):
        RMZoneData.__init__(self, uid)
        RMZoneAdvancedData.__init__(self, uid)

    def getZoneCoefFromType(self):
        zoneCoef = 0.8
        if self.type == RMZoneTypes.ztGrass:
            zoneCoef = 0.8
        elif self.type == RMZoneTypes.ztFruitTrees:
            zoneCoef = 0.95
        elif self.type == RMZoneTypes.ztFlowers:
            zoneCoef = 1.0
        elif self.type == RMZoneTypes.ztVegetables:
            zoneCoef = 1.15
        elif self.type == RMZoneTypes.ztCitrus:
            zoneCoef = 0.65
        elif self.type == RMZoneTypes.ztBushes:
            zoneCoef = 1.0

        return zoneCoef

    def getFieldCapacity(self):
        return globalSettings.location.wsDays * globalSettings.location.et0Average

##-----------------------------------------------------------------------------------------------------
##
##
class RMNotification:
    cloudClient = "00000"
    zone = "10001"
    program = "10002"
    weather = "10003"
    rainSensor = "10004"
    rainDelay = "10005"
    freezeTemperature = "10006"
    rebootInWatering = "10007"
    shortDetected = "10008"
    textMode = "99999"

    actionStop = "0"
    actionStart = "1"

    __cloudClientControlFile = "/tmp/cloud-client.ctrl"
    _rainFlag = False
    _rainDelayFlag = False
    _freezeFlag = False

    @staticmethod
    def notifyCloud(code = None, action = None, parameter = None):
        if parameter is None:
            parameter = ''
        if action is None:
            action = ''

        if code == RMNotification.freezeTemperature:
            if RMNotification._freezeFlag is not action:
                RMNotification._freezeFlag = action
                string = code + "," + str(int(action)) + "," + str(parameter) + "\n"
            else:
                return
        elif code == RMNotification.rainDelay:
            isRainDelay = (globalSettings.restrictions.globalRestrictions.rainDelayDuration +
                globalSettings.restrictions.globalRestrictions.rainDelayStartTime) > rmCurrentTimestamp() \
                          and globalSettings.restrictions.globalRestrictions.rainDelayStartTime <= rmCurrentTimestamp()
            if RMNotification._rainDelayFlag != isRainDelay:
                RMNotification._rainDelayFlag = isRainDelay
                string = code + "," + str(int(isRainDelay)) + "\n"
            else:
                return
        elif code == RMNotification.rainSensor:
            if action != RMNotification._rainFlag:
                RMNotification._rainFlag = action
                string = code + "," + str(int(action)) + "\n"
            else:
                return
        elif code == RMNotification.cloudClient:
            string = code + "\n"
        else:
            if len(str(parameter)):
                string = str(code) + ',' + str(action) + "," + str(parameter) + "\n"
            else:
                string = str(code) + ',' + str(action) + "\n"

        RMNotification.__writeNotification(string)

    @staticmethod
    def notifyCloudRaw(string):
        if not string.endswith('\n'):
            string = string + '\n'
        RMNotification.__writeNotification(string)

    @staticmethod
    def __writeNotification(string):
        #log.info("NotifyCloud: %s" % string)
        try:
            if stat.S_ISFIFO(os.stat(RMNotification.__cloudClientControlFile).st_mode) > 0:
                fd = os.open(RMNotification.__cloudClientControlFile, os.O_WRONLY | os.O_NONBLOCK)
                try:
                    os.write(fd, string)
                    log.debug("Notified cloud client about change")
                except Exception, e:
                    log.debug("Can't notify cloud client about settings change %s", str(e))
                finally:
                    os.close(fd)
        except Exception, e:
            log.debug("Cloud client control FIFO not found %s", str(e))

##-----------------------------------------------------------------------------------------------------
##
##
class RMUserSchType:
    stUnknown = -1
    stDaily = 0
    stEveryn = 1
    stWeekday = 2
    stDateonce = 3
    stOddeven = 4
    stNth = 5
    stMax = 6

class RMUserSchDays:
    MON = 1
    TUE = 2
    WED = 3
    THU = 4
    FRI = 5
    SAT = 6
    SUN = 7

    MASK_MON = 1 << MON
    MASK_TUE = 1 << TUE
    MASK_WED = 1 << WED
    MASK_THU = 1 << THU
    MASK_FRI = 1 << FRI
    MASK_SAT = 1 << SAT
    MASK_SUN = 1 << SUN

class RMUserSchData:
    def __init__(self, uid = -1):
        self.uid = uid
        self.name = "New Program"
        self.type = RMUserSchType.stDaily
        self.active = True
        self.start_time = -1 # encoded as HH*100+MM
        self.st_h = -1
        self.st_m = -1
        self.start_date = -1 # unix timestamp
        self.sd_y = -1
        self.sd_m = -1
        self.sd_d = -1
        self.param = 0 # only used in stDaysInt (interval value) and stWeekDays( days since sunday (0-6)
        self.updated = -1 # unix timestamp
        self.cs_cycles = 0
        self.cs_min = 0
        self.cs_on = False # Cycles and Soak active or not.
        self.delay = 0 # Delay between zones.
        self.delay_on = False # Delay between zones is active or not.
        self.program_coef = 0.0
        self.ignoreInternetWeather = False
        self.futureField1 = 0
        self.freq_modified = 0
        self.useWaterSense = False
        #memory only parameters:
        self.simulationExpired = False

    def __repr__(self):
        v = vars(self)
        return ", ".join([":".join((k, str(v[k]))) for k in v if not k.startswith("_")])

class RMUserSchZoneLineData:
    def __init__(self, zid = -1):
        self.zid = zid
        self.duration = 0
        self.active = False
        self.coef = 1.0
        self.calc_wd = 0
        self.flag = RMZoneWateringFlag.zwfNormal

    def __repr__(self):
        v = vars(self)
        return ", ".join([":".join((k, str(v[k]))) for k in v if not k.startswith("_")])

class RMUserSchZoneData:
    def __init__(self):
        self.zid = -1
        self.pid = -1
        self.duration = 0
        self.active = True
        self.last_wd = 0 # Obsolete replaced by Available Water table

class RMPastValues:
    def __init__(self, pid = -1, timestamp = 0, used = 0, et0 = 0, qpf = 0):
        self.pid = pid
        self.timestamp = timestamp
        self.used = used
        self.et0 = et0
        self.qpf = qpf

class RMAvailableWaterValues:
    def __init__(self, day = 0, pid = 0, zid = 0, aw = 0):
        self.day = day
        self.pid = pid
        self.zid = zid
        self.aw = aw
