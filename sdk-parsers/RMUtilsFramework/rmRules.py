# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>

from RMUtilsFramework.rmLogging import log
import operator


class RMRule:

    def __init__(self, variable, op, value, action, *args, **kwargs):
        self.variable = variable
        self.op = op
        self.value = value
        self.action = action
        self.args = args
        self.kwargs = kwargs

    def check(self, values):
        value = values.get(self.variable, None)
        #log.info("Trying rule for %s args: %s kwargs: %s" % (value, self.args, self.kwargs))
        if value is not None and self.op(value, self.value):
            try:
                return self.action(*self.args, **self.kwargs)
            except:
                return False

        return False

class RMRules:

    availableActions = {
        "log": log.info
    }

    availableOperators = {
        "=": operator.eq,
        ">": operator.gt,
        "<": operator.lt,
        "<=": operator.le,
        ">=": operator.ge
    }

    def __init__(self):
        self.rules = []

    def addRule(self, variable, op, value, action, *args, **kwargs):
        _op = RMRules.availableOperators[op]
        _action = RMRules.availableActions[action]
        rule = RMRule(variable, _op, value, _action, *args, **kwargs)
        self.rules.append(rule)
        return len(self.rules) - 1


    def addRuleSerialized(self, data):
        try:
            return self.addRule(data["variable"], data["operator"], data["value"], data["action"], **data["params"])
        except:
            log.info("Can't add rule: %s" % data)
        return -1


    def addAction(self, name, func):
        RMRules.availableActions[name] = func


    def addActions(self, list):
        for action in list:
            RMRules.availableActions[action[0]] = action[1]

    def getAction(self, name):
        return RMRules.availableActions.get(name, None)

    def check(self, values):
        for rule in self.rules:
            rule.check(values)



if __name__ == "__main__":
    def raindelay(delay=1):
        log.info("Set RainDelay to %s" % delay)

    rules = RMRules()
    rules.addAction("raindelay", raindelay)

    rules.addRule("temp", ">", 50, "log", "Temperature exceeded")
    rules.addRule("temp", "<=", 0, "log", "Freeze protect")
    rules.addRule("qpf", ">", 2.0, "log", "QPF exceeded")
    rules.addRule("qpf", ">", 2.0, "raindelay", delay = 2)

    rule = {
        "variable": "rain",
        "operator": ">",
        "value": 2.0,
        "action": "raindelay",
        "params": {"delay": 5}
    }
    rules.addRuleSerialized(rule)

    rules.check({"temp": 60})
    rules.check({"temp": 40})
    rules.check({"temp": 0})
    rules.check({"qpf": 2.5})
    rules.check({"rain": 3.8})