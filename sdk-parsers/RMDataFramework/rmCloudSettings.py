# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

class RMCloudSettings:
    def __init__(self):
        self.email = None
        self.enabled = False
        self.pendingEmail = None
        self._dataPath = '/rainmachine-cloud/' # where the certs/ and factory setup files are located
        self._logPath = '/rainmachine-cloud/' # where the log file is found
        self._statusFile = '/tmp/cloud-client-status'

    def asDict(self):
        return dict((key, value) for key, value in self.__dict__.iteritems() if not callable(value) and not key.startswith('_'))

    def __repr__(self):
        v = vars(self)
        return ",".join([":".join((k, str(v[k]))) for k in v if not k.startswith("_")])
