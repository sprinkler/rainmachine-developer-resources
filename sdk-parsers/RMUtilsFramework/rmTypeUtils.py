# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>

def rmStrToUnicode(value):
    if value is None:
        return value
    if isinstance(value, str):
        return unicode(str)
    return value

def rmUnicodeToStr(value):
    if value is None:
        return value
    if isinstance(value, unicode):
        return str.encode("utf_8")
    return value

def rmTextToDict(text):
    result = {}

    if text:
        blocks = text.split(";")
        for block in blocks:
            chunks = block.split("=")
            if(len(chunks) == 1):
                result[chunks[0].strip()] = None
            elif(len(chunks) == 2):
                result[chunks[0].strip()] = chunks[1].strip()

    return result