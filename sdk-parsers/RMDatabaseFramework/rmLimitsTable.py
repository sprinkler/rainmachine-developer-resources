# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from rmDatabase import RMTable

class RMLimitsTable(RMTable):
    def initialize(self):
        self.database.execute("CREATE TABLE IF NOT EXISTS limits (ID INTEGER PRIMARY KEY AUTOINCREMENT, "\
                                            "scope VARCHAR(16) NOT NULL, "\
                                            "name VARCHAR(64) NOT NULL, "\
                                            "min DECIMAL DEFAULT NULL, "\
                                            "max DECIMAL DEFAULT NULL, "\
                                            "UNIQUE(scope, name)"\
                                            ")")
        self.database.commit()

    def addRecord(self, scope, name, min, max = None):
        if(self.database.isOpen()):
            self.database.execute("INSERT INTO limits (scope, name, min, max) VALUES(?, ?, ?, ?)", (scope, name, min, max, ))
            self.database.commit()

    def addRecords(self, records):
        if(self.database.isOpen()):
            self.database.executeMany("INSERT INTO limits (scope, name, min, max) VALUES(?, ?, ?, ?)", records)
            self.database.commit()

    def getRecord(self, scope, name, minDefault = None, maxDefault = None):
        if(self.database.isOpen()):
            results = self.database.execute("SELECT min, max FROM limits WHERE scope=? AND name=?", (scope, name, )).fetchone()
            if(results):
                return results[0], results[1]
        return minDefault, maxDefault

