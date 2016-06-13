# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

import json
from pprint import pprint

def rmJsonParseString(s):
    data = json.loads(s)
    if data is None:
        return None
    return __rmConvertJsonData(data)


def __rmConvertJsonData(data):
    if data is None:
        return None

    if isinstance(data, dict):
        return dict([__rmConvertJsonData(key), __rmConvertJsonData(value)] for key, value in data.iteritems())

    if isinstance(data, list):
        return [__rmConvertJsonData(value) for value in data]

    if isinstance(data, unicode):
        return data.encode('utf_8')

    return data
