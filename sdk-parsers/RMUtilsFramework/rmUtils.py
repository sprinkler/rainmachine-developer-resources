# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import subprocess, os, sys, ctypes, fcntl
import re
from math import cos, sqrt, sin, acos, asin, log
from RMUtilsFramework.rmTimeUtils import rmGetStartOfDayUtc , rmCurrentTimestamp
from RMUtilsFramework.rmLogging import log

#-----------------------------------------------------------------------------------------------------------
#
#
class timespec(ctypes.Structure):
    _fields_ = [
        ('tv_sec', ctypes.c_long),
        ('tv_nsec', ctypes.c_long)
    ]

def getAlarmElapsedRealTime():
    ### This method is used on Android to get the UP_TIME.
    elapsedTime = -1
    try:
         alarmFile = open("/dev/alarm", 'r')
         if alarmFile:
             t = timespec()

             # ANDROID_ALARM_GET_TIME(ANDROID_ALARM_ELAPSED_REALTIME) = 0x40086134
             result = fcntl.ioctl(alarmFile.fileno(), 0x40086134, t)
             if result == 0:
                 elapsedTime = t.tv_sec

             alarmFile.close()
    except Exception, e:
        log.error(e)

    return elapsedTime

#-----------------------------------------------------------------------------------------------------------
#TODO: Use subprocess32 for timeout
#
def rmSysCmd(cmd):
    ret = -1
    try:
        output = subprocess.check_output(cmd, stderr = subprocess.STDOUT)
        ret = 0
    except subprocess.CalledProcessError as e:
        output = "Command returned error"
        ret = e.returncode
    except Exception as e:
        output = "Can't run command !"
        ret = -1

    return { "ret": ret, "output": output.split('\n') }

def rmBin(intVal, addPrefix = True, length = 10):

    if addPrefix:
        binFormat = "#0%db" % length
    else:
        binFormat = "0%db" % length

    return format(intVal, binFormat)

def rmStrToHex(string):
    return ":".join("{:02x}".format(ord(c)) for c in string)

def rmIntFromBinString(val):
    return int(val, 2)


#-----------------------------------------------------------------------------------------------------------
# Machine/App rebooting
#
def rmShutdownMachine(exitCode):
    cmd = "poweroff"

    log.info("SHUTTING DOWN MACHINE...")

    if cmd:
        try:
            log.info(cmd)
            os.system(cmd)
        except Exception, e:
            log.error(e)
    exit(exitCode)

def rmRebootMachineOrApp(machine, exitCode):
    #--------------------------------------------------
    # Restart the machine/app.
    cmd = None

    if machine:
        log.info("REBOOTING MACHINE...")
        cmd = "reboot"
    else:
        log.info("RESTARTING APP...")

        restartScript = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "restartSelf.sh"))
        params = [restartScript, `os.getpid()`] + sys.argv
        if params[-1] == "&":
            del params[-1]
        cmd = '"' + '" "'.join(params) + '" &'

    if cmd:
        try:
            log.info(cmd)
            os.system(cmd)
        except Exception, e:
            log.error(e)
    exit(exitCode)


#-----------------------------------------------------------------------------------------------------------
# Singleton meta-class
#
class RMSingleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(RMSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

#-----------------------------------------------------------------------------------------------------------
# Simple Line Matcher class that compiles and matches a regexp on a string
#
class RMLineMatcher:
    def __init__(self, regexp, handler):
        self.regexp = re.compile(regexp)
        self.handler = handler

    def match(self, line):
        result = self.regexp.match(line)
        if result:
            self.handler(result)
            return True
        return False

#-----------------------------------------------------------------------------------------------------------------------
# Conversion functions
#
# Can take a list of tuples (timestamp, value) or scalar as argument
def distanceBetweenGeographicCoordinatesAsKm(lat1, lon1, lat2, lon2):
    try:
        piOver180 = 0.01745329251
        deltaLat = (lat1 - lat2)*piOver180
        deltaLon = (lon1 - lon2)*piOver180
        avgLat = (lat1 + lat2)/2*piOver180
        return  6373 * sqrt(deltaLat**2 + (cos(avgLat)*deltaLon)**2)
    except Exception, e:
        log.error("Can't compute distance: %s" % e)
        return None

def convertKnotsToMS(value):
    if isinstance(value, list):
        value = [(v[0], __knotsToMS(v[1])) for v in value]
    else:
        value = __knotsToMS(value)

    return value

def convertFahrenheitToCelsius(value):
    if isinstance(value, list):
        value = [(v[0], __fahrenheitToCelsius(v[1])) for v in value]
    else:
        value = __fahrenheitToCelsius(value)

    return value

def convertInchesToMM(value):
    if isinstance(value, list):
        value = [(v[0], __inchesToMM(v[1])) for v in value]
    else:
        value = __inchesToMM(value)

    return value

#Calculate wind to 10 meters from 2 meters (default in RainMachine). This is a precalculated version.
def convertWindFrom2mTo10m(wind2):
    try:
        wind2 = float(wind2)
        return wind2 * 1.3370  # reverse Eq. 33
    except:
        log.debug("Can't convert wind %s from 2m to 10m value" % wind2)
        return None


def convertRadiationFromWattsToMegaJoules(radiation):
    try:
        radiation = float(radiation)
        return radiation * 0.0864
    except:
        log.debug("Can't convert radiation %s from watts to mjoules" % radiation)
        return None

def __knotsToMS(knots):
    try:
        knots = float(knots)
        return knots * 0.514444
    except:
        log.debug("Can't convert knots to m/s !")
        return None

def __fahrenheitToCelsius(temp):
    try:
        temp = float(temp)
        return (temp - 32) * 5.0/9.0
    except:
        log.debug("Can't convert fahrenheit to celsius !")
        return None

def __inchesToMM(inches):
    try:
        inches = float(inches)
        return inches * 25.4
    except:
        log.debug("Can't convert inches to mm !")
        return None


#Calculate wind from N meters to 2 meters (same as inside formula.py)
def __windFromNmTo2m(windN, height):
    try:
        windN = float(windN)
        return windN * 4.87 / math.log(67.8 * height - 5.42)  # Eq.33
    except:
        log.debug("Can't convert wind from %s to 2m value" % windN)
        return None


#Calculate wind to N meters from 2 meters
def __windFrom2mToNm(wind2, height):
    try:
        wind2 = float(wind2)
        height = float(height)
        return wind2 / 4.87 * math.log(67.8 * height - 5.42)  # reverse Eq. 33
    except:
        log.debug("Can't convert wind %s from 2m to %sm value" % (wind2, height))
        return None

