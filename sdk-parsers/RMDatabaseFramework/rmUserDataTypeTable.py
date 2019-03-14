# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMDataFramework.rmParserUserData import *
from RMDataFramework.rmParserConfig import RMParserConfig

from rmDatabase import RMTable

class RMUserDataTypeTable(RMTable):
    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS userDataType ("\
                            "ID INTEGER PRIMARY KEY AUTOINCREMENT, "\
                            "name VARCHAR(64) NOT NULL UNIQUE"\
                            ")")
        self.database.commit()

    def addRecords(self, names):
        records = []
        for name in names:
            record = self.addRecord(name)
            if record != None:
                records.append(record)
        return records

    def addRecord(self, name):
        if name not in RMParserUserData.cachedNames:
            if self.database.isOpen():
                record = self.getRecord(name)
                if not record:
                    self.database.execute("INSERT INTO userDataType (name) VALUES(?)", (name, ))
                    self.database.commit()

                    record = RMParserUserDataTypeEntry(self.database.lastRowId(), name)

                    RMParserUserData.cachedIDs[record.id] = record
                    RMParserUserData.cachedNames[record.name] = record
                return record
        else:
            return RMParserUserData.cachedNames[name]

        return None

    def getRecord(self, name):
        if self.database.isOpen():
            result = self.database.execute("SELECT ID FROM userDataType WHERE name=?", (name, ))
            if result:
                row = result.fetchone()
                if row:
                    return RMParserUserDataTypeEntry(row[0], name)
        return None

    def buildCache(self):
        if self.database.isOpen():
            result = self.database.execute("SELECT ID, name FROM userDataType")
            for row in result:
                record = RMParserUserDataTypeEntry(row[0], row[1])
                RMParserUserData.cachedIDs[record.id] = record
                RMParserUserData.cachedNames[record.name] = record
