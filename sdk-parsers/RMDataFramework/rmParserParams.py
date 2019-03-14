# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

from cStringIO import StringIO
import pickle

def RMParserParams_adaptToSQLite(params):
    if params == None:
        return None

    outputStream = StringIO()
    pickler = pickle.Pickler(outputStream)
    pickler.dump(params)
    return outputStream.getvalue()

def RMParserParams_convertFromSQLite(data):
    if data == None:
        return None

    inputStream = StringIO(data)
    unpickler = pickle.Unpickler(inputStream)
    return unpickler.load()

