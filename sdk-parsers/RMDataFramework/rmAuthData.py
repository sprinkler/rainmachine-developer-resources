# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from RMUtilsFramework.rmTimeUtils import rmTimestampToUtcDateAsString, rmCurrentTimestamp

class RMAuthToken:
    def __init__(self, token = None, expiration = None):
        self.token = token
        self.expiration = expiration

    def __repr__(self):
        if self.expiration:
            return "(token=" + `self.token` + ", expiration=None, expiresIn=None)"
        return "(token=" + `self.token` + \
               ", expiration=" + rmTimestampToUtcDateAsString(self.expiration, "%a, %d %b %Y %H:%M:%S GMT") + \
               ", expiresIn=" + self.expiresIn() + ")" + \
               ")"

    def expiresIn(self):
        if self.expiration:
            return self.expiration - rmCurrentTimestamp()
        return None