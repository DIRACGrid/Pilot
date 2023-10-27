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

from __future__ import absolute_import, division, print_function

import os
import sys
import time

############################
# python 2 -> 3 "hacks"

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

try:
    from Pilot.pilotTools import (
        Logger,
        PilotParams,
        RemoteLogger,
        getCommand,
        pythonPathCheck,
    )
except ImportError:
    from pilotTools import (
        Logger,
        PilotParams,
        RemoteLogger,
        getCommand,
        pythonPathCheck,
    )
############################

if __name__ == "__main__":
    pilotStartTime = int(time.time())

    sys.stdout, oldstdout = StringIO(), sys.stdout
    # so PilotParams are writing to a StingIO buffer now.
    pilotParams = PilotParams()
    sys.stdout, buffer = oldstdout, sys.stdout
    bufContent = buffer.getvalue()
    buffer.close()
    # print the buffer, so we have a "classic' logger back in sync.
    sys.stdout.write(bufContent)
    # now the remote logger.
    if pilotParams.pilotLogging:
        # In a remote logger enabled Dirac version we would have some classic logger content from a wrapper,
        # which we passed in:
        receivedContent = ""
        if not sys.stdin.isatty():
            receivedContent = sys.stdin.read()
        log = RemoteLogger(
            pilotParams.loggerURL, "Pilot", pilotUUID=pilotParams.pilotUUID, debugFlag=pilotParams.debugFlag
        )
        log.info("Remote logger activated")
        log.buffer.write(receivedContent)
        log.buffer.flush()
        log.buffer.write(bufContent)
    else:
        log = Logger("Pilot", debugFlag=pilotParams.debugFlag)

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
        log.info("Requested command extensions: %s" % str(pilotParams.commandExtensions))

    log.info("Executing commands: %s" % str(pilotParams.commands))

    if pilotParams.pilotLogging:
        # It's safer to cancel the timer here. Each command has got its own logger object with a timer cancelled by the
        # finaliser. No need for a timer in the "else" code segment below.
        try:
            log.buffer.cancelTimer()
            log.debug("Timer canceled")
            log.buffer.flush()
        except Exception as exc:
            log.error(str(exc))
    for commandName in pilotParams.commands:
        command, module = getCommand(pilotParams, commandName)
        if command is not None:
            command.log.info("Command %s instantiated from %s" % (commandName, module))
            command.execute()
        else:
            log.error("Command %s could not be instantiated" % commandName)
            # send the last message and abandon ship.
            if pilotParams.pilotLogging:
                log.buffer.flush()
            sys.exit(-1)
