# Copyright (c) 2016 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Nicu Pavel <npavel@mini-box.com>
#          Ciprian Misaila <ciprian.misaila@mini-box.com>
"""
This is Python REST client that implements RainMachine API 4.3. The client can be used either though http or https protocols.
Example Usage:

    from rmAPIClient import *
    client = RMAPIClient(host="127.0.0.1", port="18080", protocol=RMAPIClientProtocol.HTTP)
    print client.zones.get()
    print client.programs.get()


More example usages are implemented in each submodule as __main__ function.
"""
# To generate the documentation:
# PYTHONPATH=. pdoc API4Client --all-submodules --html-dir /tmp/rmclient/ && cd /tmp/rmclient/API4Client/ && cat * > readme.md
# import os
# for module in os.listdir(os.path.dirname(__file__)):
#     if module == '__init__.py' or module[-3:] != '.py':
#         continue
#     __import__(module[:-3], locals(), globals())
# del module