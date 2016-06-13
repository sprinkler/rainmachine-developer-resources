# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


class RMParserConfig:
    def __init__(self, dbID = None, fileName = None, name = None, enabled = False):
        self.dbID = dbID
        self.fileName = fileName
        self.name = name
        self.enabled = enabled
        self.userDataTypes = None

        self.runtimeLastForecastInfo = None
        self.failCounter = 0
        self.lastFailTimestamp = 0

    def __repr__(self):
        return "(" + `self.dbID` + ", " + `self.fileName` + ", " + `self.name` + ", " + `self.enabled` + ", " + `self.userDataTypes` + ")"