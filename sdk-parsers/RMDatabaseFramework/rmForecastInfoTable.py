# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from time import time

from RMDataFramework.rmForecastInfo import RMForecastInfo
from rmDatabase import RMTable

class RMForecastTable(RMTable):
    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS forecast (ID INTEGER PRIMARY KEY AUTOINCREMENT, "\
                                            "timestamp NUMERIC NOT NULL, "\
                                            "processed BOOLEAN NOT NULL DEFAULT 0"\
                                            ")")
        self.database.commit()

    def addRecordEx(self, forecast):
        if(forecast.id == None and self.database.isOpen()):
            self.database.execute("INSERT INTO forecast (timestamp, processed) VALUES(?, ?)", (forecast.timestamp, forecast.processed, ))
            self.database.commit()
            forecast.id = self.database.lastRowId()
        return forecast

    def addRecord(self, timestamp = None):
        if(self.database.isOpen()):
            if(timestamp == None):
                timestamp = int(time())
            self.database.execute("INSERT INTO forecast (timestamp) VALUES(?)", (timestamp, ))
            self.database.commit()
            return RMForecastInfo(self.database.lastRowId(), timestamp)
        return None

    def markRecordsAsProcessed(self, ids):
        if(self.database.isOpen()):
            ids = ",".join([str(id) for id in ids])
            self.database.execute("UPDATE forecast SET processed=1 WHERE ID IN(%s)" % ids)
            self.database.commit()

    def markAllRecordsAsNotProcessed(self):
        if(self.database.isOpen()):
            self.database.execute("UPDATE forecast SET processed=0 WHERE ID IN (SELECT DISTINCT forecastID FROM parserData)")
            self.database.commit()

    def getUnprocessedRecords(self):
        if(self.database.isOpen()):
            results = []
            records = self.database.execute("SELECT * FROM forecast WHERE processed=0")
            for row in records:
                results.append(RMForecastInfo(row[0], row[1], row[2]))
            return results
        return None

    def getLastForecast(self):
        if(self.database.isOpen()):
            row = self.database.execute("SELECT * FROM forecast ORDER BY ID DESC LIMIT 1").fetchone()
            if row:
                return RMForecastInfo(row[0], row[1], row[2])
        return None

    def fixCorruptedData(self, lastForecastID, lastForecastTimestamp):
        if not lastForecastID is None and not lastForecastTimestamp is None and self.database.isOpen():
            row = self.database.execute("SELECT * FROM forecast WHERE ID>=?", (lastForecastID, )).fetchone()
            if not row:
                # Something got corrupted. Let's insert a "recovery" forecast.
                self.database.execute("INSERT INTO forecast (ID, timestamp, processed) VALUES(?, ?, 1)", (lastForecastID, lastForecastTimestamp))
                self.database.execute("UPDATE forecast SET processed=1")
                self.database.commit()
                return True
        return False

    def clear(self, commit):
        if(self.database.isOpen()):
            self.database.execute("DELETE FROM forecast")
            if commit:
                self.database.commit()