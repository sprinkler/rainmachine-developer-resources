from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging
from RMUtilsFramework.rmTimeUtils import *
from xml.etree import ElementTree as e   # Your parser needed libraries

class AustraliaBOM(RMParser):
    parserName = "Australia BoM"         # Your parser name
    parserDescription = " Commonwealth of Australia Bureau of Meteorology" # A description for this parser

    parserEnabled = True
    parserInterval = 3600                    # Your parser running interval in seconds
    parserDebug = True                      # Don't show extra debug messages
    params = {"city": "Toowoomba" }         # Internal params that can be changed with API call /parser/{id}/params

    def isEnabledForLocation(self, timezone, lat, long):
        return AustraliaBOM.parserEnabled

    # The function that will be executed must have this name
    def perform(self):
        # downloading data from a URL convenience function since other python libraries can be used
        URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDQ11295.xml"
        data = self.openURL(URL)

        if data is None:
            self.lastKnownError = "Error: No data received from server"
            return

        #xmldata = e.parse("/tmp/IDQ11295.xml")

        xmldata = e.parse(data)

        for node in xmldata.getroot().getiterator(tag = "area"):
            if node.attrib['description'] != self.params["city"]:
                continue

            for subnode in node.getiterator(tag = "forecast-period"):
                subnodeDate = subnode.get("start-time-utc")
                subnodeTimestamp = rmTimestampFromDateAsString(subnodeDate, '%Y-%m-%dT%H:%M:%SZ')
                log.info("%s" % subnodeDate)
                for element in subnode.getiterator(tag = "element"):
                    mint = None
                    maxt = None
                    qpfMin = None
                    qpfMax = None
                    qpfAvg = None

                    type = element.get("type")
                    if type == "air_temperature_minimum":
                        try:
                            mint = self.__toFloat(element.text)
                            log.info("\tMin Temp: %s" % mint)
                            self.addValue(RMParser.dataType.MINTEMP, subnodeTimestamp, mint)
                        except:
                            log.debug("Cannot get minimum temperature")
                    elif type == "air_temperature_maximum":
                        try:
                            maxt = self.__toFloat(element.text)
                            self.addValue(RMParser.dataType.MAXTEMP, subnodeTimestamp, maxt)
                            log.info("\tMax Temp: %s" % maxt)
                        except:
                            log.debug("Cannot get max temperature")
                    elif type == "precipitation_range":
                        try:
                            qpfMin, _, qpfMax, _ = element.text.split() # will result in ['15', 'to', '35', 'mm']
                            qpfAvg = (self.__toFloat(qpfMin) + self.__toFloat(qpfMax))/2
                            log.info("\tQPF Avg: %s" % qpfAvg)
                            self.addValue(RMParser.dataType.QPF, subnodeTimestamp, qpfAvg)
                        except:
                            log.debug("Cannot get precipitation forecast")


            if self.parserDebug:
                log.debug(self.result)


    def __toFloat(self, value):
        if value is None:
            return value
        return float(value)

if __name__  == '__main__':
    p = AustraliaBOM()
    p.perform()