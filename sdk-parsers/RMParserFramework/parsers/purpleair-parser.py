# purpleair_parser.py
# Custom PurpleAir weather service for RainMachine
# Released under the MIT License
# https://github.com/medmunds/rainmachine-weather-purpleair/LICENSE

import json
import sys
import time
import urllib
from math import exp

from RMParserFramework.rmParser import RMParser
from RMUtilsFramework.rmLogging import log


PROJECT = "rainmachine-weather-purpleair"
VERSION = "2.01"
ABOUT_URL = "https://github.com/medmunds/rainmachine-weather-purpleair"

log.info("Loaded %s v%s", PROJECT, VERSION)

# Identify ourselves when querying PurpleAir's API
USER_AGENT = "{project}/{version} ({about_url})".format(project=PROJECT, version=VERSION, about_url=ABOUT_URL)


class PurpleAir(RMParser):
    parserName = "PurpleAir Parser"
    parserDescription = "Obtain temperature from PurpleAir sensor"
    parserForecast = False
    parserHistorical = True
    parserInterval = 60 * 60  # seconds (no point reporting more than once an hour)
    parserDebug = False
    purpleAirUrl = "https://api.purpleair.com/v1"  # no trailing slash!
    params = {
        "sensorId": None,
        "keyForPrivateSensor": None,
        "apiKey": None,
    }
    defaultParams = {
        "sensorId": None,
        "keyForPrivateSensor": None,
        "apiKey": None,
    }
    maxAgeMinutes = 60  # ignore data older than this

    def isEnabledForLocation(self, timezone, lat, long):
        return self.parserEnabled

    def perform(self):
        # Older RainMachine models (e.g., Mini-8) have outdated root certificates,
        # which don't work with https://api.purpleair.com. There's not really
        # any way to make them work unless RainMachine updates the system.
        if sys.version_info < (2, 7, 12):
            self.lastKnownError = "does not work on outdated RainMachine platform"
            log.error(self.lastKnownError)
            return

        api_key = self.params.get("apiKey", None)
        if not api_key:
            self.lastKnownError = "must set PurpleAir apiKey"
            log.error(self.lastKnownError)
            return

        sensor_id = self.params.get("sensorId", None)
        if not sensor_id:
            # TBD: could probably query nearby PurpleAir sensors
            #   by providing a bounding box (nwlng, nwlat, selng, selat)
            #   to https://api.purpleair.com/#api-sensors-get-sensors-data
            #   based on self.settings.location.latitude and .longitude
            self.lastKnownError = "must set PurpleAir sensorId"
            log.error(self.lastKnownError)
            return

        private_sensor_key = self.params.get("keyForPrivateSensor", None)

        data = self.fetch_sensor_data(api_key, sensor_id, private_sensor_key)
        if data is not None:
            cleaned = self.clean_sensor_data(data)
            if cleaned is not None:
                self.add_sensor_data(cleaned)

    def fetch_sensor_data(self, api_key, sensor_id, private_sensor_key=None):
        url = "%s/sensors/%s" % (self.purpleAirUrl, urllib.quote(str(sensor_id), safe=""))
        params = {
            "fields": "sensor_index,name,last_seen,humidity,temperature,pressure",
        }
        if private_sensor_key:
            # read_key is only required to access private sensors
            params["read_key"] = private_sensor_key
        response = self.openURL(url, params,
                                headers={"user-agent": USER_AGENT, "X-API-Key": api_key})
        if response is None:
            # For errors from urllib2.urlopen, openURL logs the actual error,
            # sets lastKnownError to generic "Error: Can not open url",
            # and returns None. Improve that error (slightly):
            self.lastKnownError = "error querying PurpleAir sensor '%s'; check logs" % sensor_id
            log.error(self.lastKnownError)
            return None

        body = response.read()
        try:
            data = json.loads(body)
        except ValueError as err:
            self.lastKnownError = "error loading json response"
            log.exception(self.lastKnownError, exc_info=err)
            return None
        else:
            log.info("data retrieved for sensor %s", sensor_id)
            return data

    def clean_sensor_data(self, data):
        try:
            result = data["sensor"]
        except KeyError as err:
            self.lastKnownError = "unexpected response format"
            log.exception(self.lastKnownError, exc_info=err)
            return None

        try:
            # https://api.purpleair.com/#api-sensors-get-sensor-data
            # TBD: verify result["sensor_index"] matches self.params["sensorId"]?
            timestamp = result["last_seen"]  # "UNIX time stamp of the last time the server received data from the device"
            temp_f = float(result["temperature"])  # "Temperature inside of the sensor housing (F)"
            humidity = float(result["humidity"])  # 0..100 "Relative humidity inside of the sensor housing (%)"
            pressure_millibars = float(result["pressure"])  # "Current pressure in Millibars"
        except (KeyError, TypeError, ValueError) as err:
            self.lastKnownError = "unexpected response format"
            log.exception(self.lastKnownError, exc_info=err)
            return None

        # Filter out responses that are too old (e.g., offline sensors).
        # (Another approach would be to check result["AGE"], which is in minutes.)
        data_age_minutes = (time.time() - timestamp) / 60
        if data_age_minutes > self.maxAgeMinutes:
            self.lastKnownError = "ignoring old data (%d minutes)" % data_age_minutes
            log.warning(self.lastKnownError)
            return None

        # Convert from PurpleAir's to RainMachine's preferred units
        temp_c = f_to_c(temp_f)
        pressure_kpa = millibars_to_kpa(pressure_millibars)

        temp_c, humidity = self.correct_for_purpleair_heating(temp_c, humidity)

        return {
            "timestamp": timestamp,
            RMParser.dataType.TEMPERATURE: temp_c,
            RMParser.dataType.RH: humidity,
            RMParser.dataType.PRESSURE: pressure_kpa,
        }

    def add_sensor_data(self, cleaned):
        timestamp = cleaned.pop("timestamp")
        for data_type, value in cleaned.items():
            self.addValue(data_type, timestamp, value)
            log.debug("added '%s': %0.1f at %d" % (data_type, value, timestamp))

    @staticmethod
    def correct_for_purpleair_heating(temp_c_pa, humidity_pa):
        """
        Return adjusted temp_c and humidity after correcting
        for internal heating caused by PurpleAir's electronics.
        """
        # Source (temperature): https://api.purpleair.com/#api-sensors-get-sensor-data
        # "On average, [internal temperature] is 8F higher than ambient conditions."
        #
        # Source (humidity): Dr. Peter Jackson of University of Northern British Columbia,
        # based on two year colocation study of 150+ Purple Air sensors in Prince George, BC.
        # Discussion in PurpleAir community thread:
        # https://www.facebook.com/groups/purpleair/posts/722201454903597/?comment_id=722399368217139
        # (Note that Dr. Jackson's data suggested a -5.24C temperature correction;
        # this seems excessive, at least in my location.)
        temp_c = temp_c_pa - 4.4444  # (delta 8F = 4.4444C)
        humidity = (humidity_pa * saturation_vapour_pressure(temp_c_pa)
                    / saturation_vapour_pressure(temp_c))
        return temp_c, humidity


def f_to_c(temp_f):
    return (temp_f - 32.0) * 5.0 / 9.0


def millibars_to_kpa(pressure_millibars):
    return pressure_millibars / 10.0


def saturation_vapour_pressure(temp_c):
    """
    Approximate saturation vapour pressure of liquid water, in kPa,
    at the given temperature.
    """
    # Buck Equation is accurate across most meteorological temperatures.
    # https://en.wikipedia.org/wiki/Arden_Buck_equation
    # https://en.wikipedia.org/wiki/Vapour_pressure_of_water#Accuracy_of_different_formulations
    return 0.61121 * exp(
        (18.678 - (temp_c / 234.5)) *
        (temp_c / (257.14 + temp_c))
    )
