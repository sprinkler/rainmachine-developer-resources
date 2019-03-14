# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMUtilsFramework.rmTimeUtils import rmCurrentTimestamp, rmTimestampToDateAsString

class RMForecastInfo:
    def __init__(self, id, timestamp = None, processed = False):
        self.id = id
        self.timestamp = timestamp
        self.processed = processed

        if self.timestamp is None:
            self.timestamp = rmCurrentTimestamp()

    def __eq__(self, other):
        if other == None:
            return False
        return self.id == other.id

    def __hash__(self):
        return self.id

    def __repr__(self):
        return "(id=" + `self.id` + ", time=" + rmTimestampToDateAsString(self.timestamp) + ", processed=" + `self.processed` + ")"