# Copyright (c) 2014 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>


import os
import thread
from threading import Thread, Event
from Queue import Queue, Empty

from RMUtilsFramework.rmLogging import log

from pprint import pprint

#----------------------------------------------------------------------------------------
#
#
#
class RMCommand:

    def __init__(self, name, synch):
        self.name = name

        self.command = None
        self.args = None
        self.kwargs = None

        self.result = None

        self.event = None
        if synch:
            self.event = Event()

    def __repr__(self):
        return "(" + \
                "name=" + `self.name` + \
                "command=" + `self.command` + \
                "args=" + `self.args` + \
                "kwargs=" + `self.kwargs` + \
                "result=" + `self.result` + \
                ")"

    def wait(self, timeout = None):
        if self.event:
            self.event.wait(timeout)

    def notifyFinished(self):
        if self.event:
            self.event.set()

#----------------------------------------------------------------------------------------
#
#
#
class RMCommandThread(Thread):

    #----------------------------------------------------------------------------------------
    #
    #
    #
    instance = None

    @staticmethod
    def createInstance():
        if RMCommandThread.instance is None:
            RMCommandThread.instance = RMCommandThread()
            RMCommandThread.instance.start()
        return RMCommandThread.instance.isAlive()

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def __init__(self):

        Thread.__init__(self)

        self.waitTimeout = 3600
        self.messageQueue = Queue()

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def runsOnThisThread(self):
        return thread.get_ident() == self.ident

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def executeCommand(self, command):
        log.debug("Schedule execute command: %s" % `command.name`)
        log.debug(command)
        self.messageQueue.put(command)
        if command.event:
            command.wait()
            log.debug(command)
            log.debug("Command finished %s" % `command.name`)
            return command.result

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def start(self):

        self.startEvent = Event()

        Thread.start(self)

        self.startEvent.wait(None)
        del self.startEvent

    def run(self):

        try:
            self.doPreRun()
        except Exception, e:
            log.error(e)

        try:
            self.startEvent.set()
        except Exception, e:
            log.error(e)

        try:
            self.doRun()
        except Exception, e:
            log.error(e)

        try:
            self.doPostRun()
        except Exception, e:
            log.error(e)

    def stop(self):
        cmd = RMCommand("shutdown", False)
        self.messageQueue.put(cmd)

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def doPreRun(self):
        pass


    #----------------------------------------------------------------------------------------
    #
    #
    #
    def doRun(self):
        #-------------------------------------------------------------------------
        # Handle the events / commands.
        command = None
        while True:
            try:
                if not self.doHandleMessages():
                    break
            except Exception, e:
                log.error(e)

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def doPostRun(self):
        pass

    #----------------------------------------------------------------------------------------
    #
    #
    #
    def doHandleMessages(self, limit = None):
        if not limit is None:
            messageCount = 0

        while True:
            try:
                command = self.messageQueue.get(True, self.waitTimeout)
                if command.name == "shutdown":
                    return False
                else:
                    self.doExecuteCommand(command)

                    if not limit is None:
                        messageCount += 1
                        if limit <= messageCount:
                            break

            except Empty, e:
                break
            except Exception, e:
                log.error(e)

        return True

    def doExecuteCommand(self, command):
        log.debug(command.name)
        try:
            if command.args is None and command.kwargs is None:
                command.result = command.command()
            elif command.kwargs is None:
                command.result = command.command(*command.args)
            elif command.args is None:
                command.result = command.command(**command.kwargs)
            else:
                command.result = command.command(*command.args, **command.kwargs)
        except Exception, e:
            log.error(command.name)
            log.error(e)

        command.notifyFinished()
