# DWD parser for rainmachine
# Copyright (C) 2018  Sebastian Kuhn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from RMParserFramework.rmParser import RMParser  # Mandatory include for parser definition
from RMUtilsFramework.rmLogging import log       # Optional include for logging

from lxml import etree
import zipfile

from RMUtilsFramework.rmTimeUtils import rmTimestampFromDateAsString

from io import BytesIO, SEEK_SET, SEEK_END

def _ceil_div(a, b):
    return (a + b - 1) / b

def _align_up(a, b):
    return _ceil_div(a, b) * b

class BufferedRandomReader:
    """Create random-access, read-only buffered stream adapter from a sequential
    input stream which does not support random access (i.e., ```seek()```)

    Example::

        >>> stream = BufferedRandomReader(BytesIO('abc'))
        >>> print stream.read(2)
        ab
        >>> stream.seek(0)
        0L
        >>> print stream.read()
        abc

    """

    def __init__(self, fin, chunk_size=512):
        self._fin = fin
        self._buf = BytesIO()
        self._eof = False
        self._chunk_size = chunk_size

    def tell(self):
        return self._buf.tell()

    def read(self, n=-1):
        """Read at most ``n`` bytes from the file (less if the ```read``` hits
        end-of-file before obtaining size bytes).

        If ``n`` argument is negative or omitted, read all data until end of
        file is reached. The bytes are returned as a string object. An empty
        string is returned when end of file is encountered immediately.
        """
        pos = self._buf.tell()
        end = self._buf.seek(0, SEEK_END)

        if n < 0:
            if not self._eof:
                self._buf.write(self._fin.read())
                self._eof = True
        else:
            req = pos + n - end

            if req > 0 and not self._eof: # need to grow
                bcount = _align_up(req, self._chunk_size)
                bytes  = self._fin.read(bcount)

                self._buf.write(bytes)
                self._eof = len(bytes) < bcount

        self._buf.seek(pos)

        return self._buf.read(n)

    def seek(self, offset, whence=SEEK_SET):

        if whence == SEEK_END:
            if not self._eof:
                self._buf.seek(0, SEEK_END)
                self._buf.write(self._fin.read())
                self._eof = True
            return self._buf.seek(offset, SEEK_END)

        return self._buf.seek(offset, whence)

    def close(self):
        self._fin.close()
        self._buf.close()


class DWDParser(RMParser):
    parserName = "DWD Parser"
    parserDescription = "Parser for the german \"Deutscher Wetterdienst\". To get station ID please see: https://www.dwd.de/DE/leistungen/opendata/help/stationen/mosmix_stationskatalog.cfg?view=nasPublication&nn=16102"
    parserForecast = True
    parserHistorical = True
    parserInterval = 6 * 3600
    parserDebug = False
    params = {"station": None}
    defaultParams = {"station": "10637"}

    def perform(self):
        station = self.params.get("station", None)
        if station is None or station == "":
            station = "10637"
            log.debug("No station set, using Frankfurt am Main (%s)" % station)

        url = "http://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/" + station + "/kml/MOSMIX_L_LATEST_" + station + ".kmz"

        URLParams = []

        try:
            file = self.openURL(url, URLParams)
            if file is None:
                self.lastKnownError = "Cannot read data from DWD Service."
                return
            else:
                log.debug("Successfully loaded the KML file")
                kmz = zipfile.ZipFile(BufferedRandomReader(file), 'r')
                for name in kmz.namelist():
                    kml = kmz.read(name)
                    print(name, len(kml), repr(kml[:50]))

                root = etree.fromstring(kml)

                children = list(root)
                for children in root:
                    print children.tag
                    for child in children:
                        print child.tag
                        for c in child:
                            print c.tag
                            for a in c:
                                print a.tag


                ogNSMAP = {'og': 'http://www.opengis.net/kml/2.2'}
                dwdNSMAP = {'dwd': 'https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd'}
                for element in root.findall('.//dwd:TimeStep', namespaces=dwdNSMAP):
                    print(element.tag)


        except Exception as e:
            log.error("*** Error running DWD parser")
            log.exception(e)


if __name__ == "__main__":
    p = DWDParser()
    p.perform()
