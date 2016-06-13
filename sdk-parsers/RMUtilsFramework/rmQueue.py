# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import sys, os
sys.path.insert(0, ".")

from RMUtilsFramework.rmLogging import log

class RMQueue:
    """
    FIFO Queue custom implementation
    """

    QUEUE_GC_THRESHOLD = 50

    def __init__(self, elements = None):
        self.top = 0
        self.q = elements or []

    def __len__(self):
        return len(self.q) - self.top

    def put(self, element):
        self.q.append(element)

    def extend(self, elements):
        self.q.extend(elements)

    def get(self):
        q = self.q
        element = q[self.top]
        self.top += 1
        if self.top > self.QUEUE_GC_THRESHOLD and self.top >  len(q)/2:
            del q[:self.top]
            self.top = 0
        return element

    def peak(self):
        return self.q[self.top]

    def empty(self):
        if self.__len__() == 0:
            return True
        return False

    def clear(self):
        del self.q[:]

    def begin(self):
        return self.top

    def end(self):
        return len(self.q) - self.top

    def dump(self):
        return self.q[self.top:len(self.q)]



if __name__ == "__main__":

    q = RMQueue(["one", "two", "three"])
    log.debug("Queue %s" % q.dump())

    q.put("four")
    q.get()
    q.put("five")

    log.debug("Queue %s" % q.dump())
    log.debug("First Element is now: %s" % q.peak())

    q.clear()
    log.debug("Cleared Queue %s" % q.dump())



