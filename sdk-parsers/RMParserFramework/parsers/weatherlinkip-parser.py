# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>


from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log
from RMDataFramework.rmWeatherData import RMWeatherConditions
from RMDataFramework.rmUserSettings import globalSettings
from RMUtilsFramework.rmTimeUtils import *
from RMUtilsFramework.rmUtils import convertKnotsToMS, convertFahrenheitToCelsius, convertInchesToMM

import datetime, time
import socket
import struct
import binascii

class WeatherLinkIP(RMParser):
    parserName = "DavisWeatherLinkIP Parser"
    parserDescription = "Davis Weather Station with WeatherLink IP (local network access)"
    parserForecast = True
    parserHistorical = False
    parserEnabled = True
    parserDebug = False
    parserInterval = 6 * 3600
    params = {
        "stationAddress": "192.168.0.1",
        "stationPort": 22222,
        "useSolarRadiation": True,
        "useStationEvapoTranpiration": True
    }

    def isEnabledForLocation(self, timezone, lat, long):
        if WeatherLinkIP.parserEnabled:
            address = self.params.get("stationAddress", None)
            return address is not None
        return False


    def perform(self):
        s = self.settings
        address = self.getParamAsString(self.params.get("stationAddress"))
        port = self.params.get("stationPort", 22222)

        if address is None:
            self.lastKnownError = "No Station IP address specified"
            log.error(self.lastKnownError)
            return False

        try:
            wlsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            wlsocket.connect((address, port))
            wlsocket.settimeout(5)
            wlsocket.sendall(b"LOOP 1\n")
            log.info("Sent LOOP command")
        except Exception:
            self.lastKnownError = "Cannot connect to station IP: %s port %s." % (address, port)
            log.error(self.lastKnownError)
            return False

        retries = 5
        while retries > 0:
            try:
                raw_data = wlsocket.recv(1024)
            except socket.timeout, e:
                log.info("Recv timeout (%s) retrying." % e)
                time.sleep(2)
                wlsocket.sendall(b"LOOP 1\n")
                log.info("Sent LOOP command")
                retries -= 1
                continue
            except socket.error, e:
                log.info("Recv error (%s)." % e)
                self.lastKnownError = "No response from station"
                break
            else:
                log.info("Parsing Response")
                self.parsePacket(raw_data)
                break

        wlsocket.close()

        if self.parserDebug:
            log.info(self.result)


    #-----------------------------------------------------------------------------------------------
    #
    # Parse LOOP data.
    #
    def parsePacket(self, raw_data):
        self.lastKnownError = ""
        if raw_data is None or len(raw_data) < 99:
            self.lastKnownError = "Invalid data response"
            return False

        timestamp = rmCurrentTimestamp()
        if self.parserDebug:
            hex_string = binascii.hexlify(raw_data).decode('utf-8')
            log.info("Raw Data LOOP %s" % hex_string)
        try:
            ack = struct.unpack('c', raw_data[0:1])[0]
            L = struct.unpack('c', raw_data[1:2])[0]
            O1 = struct.unpack('c', raw_data[2:3])[0]
            O2 = struct.unpack('c', raw_data[3:4])[0]
            pkt_type = struct.unpack('B', raw_data[5:6])[0]
            next_record = struct.unpack('H', raw_data[6:8])[0]
        except Exception:
            self.lastKnownError = "Invalid data format"
            return False

        if L != 'L' and O1 != 'O' and O2 != 'O':
            self.lastKnownError = "Unknown packet encoding"
            return False

        pressure = struct.unpack('H', raw_data[8:10])[0] / 1000
        pressure *= 3.386 # inHg to kPa
        log.info("Barometer: %s" % pressure)
        self.addValue(RMParser.dataType.PRESSURE, timestamp, pressure)

        outside_temp = struct.unpack('h', raw_data[13:15])[0] / 10
        outside_temp =  convertFahrenheitToCelsius(outside_temp)
        log.info("Outside Temp: %s" % outside_temp)
        self.addValue(RMParser.dataType.TEMPERATURE, timestamp, outside_temp)

        #wind_speed = struct.unpack('B', raw_data[15:16])[0]
        #wind_dir = struct.unpack('H', raw_data[17:19])[0]
        ten_min_avg_wind_spd = struct.unpack('B', raw_data[16:17])[0]
        ten_min_avg_wind_spd /= 2.237 # mph to mps
        log.info("Wind Speed (10min avg): %s" % ten_min_avg_wind_spd)

        out_hum = struct.unpack('B', raw_data[34:35])[0]
        log.info("Humidity: %s" % out_hum)
        self.addValue(RMParser.dataType.RH, timestamp, out_hum)

        #rain_rate = struct.unpack('H', raw_data[42:44])[0] * 0.01
        if self.params["useSolarRadiation"]:
            solar_radiation = struct.unpack('H', raw_data[45:47])[0]
            log.info("Solar Radiation: %s" % solar_radiation)
            self.addValue(RMParser.dataType.SOLARRADIATION, timestamp, solar_radiation)

        day_rain = struct.unpack('H', raw_data[51:53])[0] * 0.01
        day_rain = convertInchesToMM(day_rain)
        log.info("Day Rain: %s", day_rain)
        self.addValue(RMParser.dataType.RAIN, timestamp, day_rain)

        if self.params["useStationEvapoTranpiration"]:
            day_et = struct.unpack('H', raw_data[57:59])[0] / 1000
            day_et = convertInchesToMM(day_et)
            log.info("Day EvapoTranspiration: %s" % day_et)

        #xmtr_battery_status = struct.unpack('?', raw_data[87:88])[0]
        #console_battery_volts = ((struct.unpack('h', raw_data[88:90])[0] * 300) / 512) / 100.0

        forecast_icon = struct.unpack('c', raw_data[90:91])[0]
        rainmachine_icon = self.conditionConvert(ord(forecast_icon))
        log.info("Condition: %s -> %s" % (ord(forecast_icon), rainmachine_icon))
        self.addValue(RMParser.dataType.CONDITION, timestamp, rainmachine_icon)
        #crc  = struct.unpack('h', raw_data[98:100])[0]

        return True


    def conditionConvert(self, forecast_icons):
        if forecast_icons == 2:
            return RMParser.conditionType.MostlyCloudy
        elif forecast_icons == 3 or forecast_icons == 7:
            return  RMParser.conditionType.LightRain
        elif forecast_icons == 8:
            return RMParser.conditionType.Fair
        elif forecast_icons == 6:
            return RMParser.conditionType.PartlyCloudy
        elif forecast_icons == 18:
            return  RMParser.conditionType.Snow
        elif forecast_icons == 19:
            return  RMParser.conditionType.RainSnow
        else:
            return  RMParser.conditionType.Unknown


    def getParamAsString(self, param):
        try:
            param = param.strip()
        except Exception:
            return None

        if not param:
            return None

        return param

if __name__ == "__main__":
    parser = WeatherLinkIP()
    parser.perform()