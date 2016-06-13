# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


from cStringIO import StringIO
import pickle

class RMParserUserDataTypeEntry:
    def __init__(self, id = None, name = None):
        self.id = id
        self.name = name

    def __repr__(self):
        return "(" + `self.id` + ", " + `self.name` + ")"

class RMParserUserData(object):
    cachedIDs = {}      # id -> RMParserUserDataTypeEntry
    cachedNames = {}    # name -> RMParserUserDataTypeEntry

    def __init__(self):
        self.data = {}

    def __repr__(self):
        text = ""
        for key in self.data:
            if len(text) > 0:
                text = text + "|"
            text = text + `key` + "=" + `self.data[key]`
        return text

    def setValue(self, key,  value):
        if key in RMParserUserData.cachedNames:
            self.data[RMParserUserData.cachedNames[key].id] = value

    def getValue(self, key):
        if key in RMParserUserData.cachedNames:
            key = RMParserUserData.cachedNames[key].id
            if key in self.data:
                return self.data[key]
        return None

def RMUserData_adaptToSQLite(userData):
    if userData == None:
        return None

    outputStream = StringIO()
    pickler = pickle.Pickler(outputStream)
    pickler.dump(userData)
    return outputStream.getvalue()

def RMUserData_convertFromSQLite(data):
    if data == None:
        return None

    inputStream = StringIO(data)
    unpickler = pickle.Unpickler(inputStream)
    return unpickler.load()


