#!/usr/bin/env python

""" The dirac-pilot.py script is a steering script to execute a series of
    pilot commands. The commands may be provided in the pilot input sandbox, and are coded in
    the pilotCommands.py module or in any <EXTENSION>Commands.py module.
    The pilot script defines two switches in order to choose a set of commands for the pilot:

     -E, --commandExtensions value
        where the value is a comma separated list of extension names. Modules
        with names <EXTENSION>Commands.py will be searched for the commands in
        the order defined in the value. By default no extensions are given
     -X, --commands value
        where value is a comma separated list of pilot commands. By default
        the list is InstallDIRAC,ConfigureDIRAC,LaunchAgent

    The pilot script by default performs initial sanity checks on WN, installs and configures
    DIRAC and runs the Job Agent to execute pending workloads in the DIRAC WMS.
    But, as said, all the actions are actually configurable.
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

__RCSID__ = "$Id$"

import os
import sys
import time

############################
# python 2 -> 3 "hacks"
try:
    from Pilot.pilotTools import Logger, pythonPathCheck, PilotParams, getCommand
except ImportError:
    from pilotTools import Logger, pythonPathCheck, PilotParams, getCommand
############################

if __name__ == "__main__":

    pilotStartTime = int(time.time())

    log = Logger("Pilot", debugFlag=True)

    pilotParams = PilotParams()
    if pilotParams.debugFlag:
        log.setDebug()
    if pilotParams.keepPythonPath:
        pythonPathCheck()
    else:
        log.info("Clearing PYTHONPATH for child processes.")
        if "PYTHONPATH" in os.environ:
            os.environ["PYTHONPATH_SAVE"] = os.environ["PYTHONPATH"]
            os.environ["PYTHONPATH"] = ""

    pilotParams.pilotStartTime = pilotStartTime
    pilotParams.pilotRootPath = os.getcwd()
    pilotParams.pilotScript = os.path.realpath(sys.argv[0])
    pilotParams.pilotScriptName = os.path.basename(pilotParams.pilotScript)
    log.debug("PARAMETER [%s]" % ", ".join(map(str, pilotParams.optList)))

    if pilotParams.commandExtensions:
        log.info(
            "Requested command extensions: %s" % str(pilotParams.commandExtensions)
        )

    log.info("Executing commands: %s" % str(pilotParams.commands))

    for commandName in pilotParams.commands:
        command, module = getCommand(pilotParams, commandName, log)
        if command is not None:
            log.info("Command %s instantiated from %s" % (commandName, module))
            command.execute()
        else:
            log.error("Command %s could not be instantiated" % commandName)
            sys.exit(-1)
