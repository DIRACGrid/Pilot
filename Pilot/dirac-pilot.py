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

__RCSID__ = "$Id$"

import os
import getopt
import sys
import requests

from types import ListType
REST_URL = 'https://pclhcb192.cern.ch:9910'

from pilotTools import Logger, pythonPathCheck, PilotParams, getCommand

if __name__ == "__main__":

  pythonPathCheck()

  log = Logger( 'Pilot' )

  pilotParams = PilotParams()
  if pilotParams.debugFlag:
    log.setDebug()

  pilotParams.pilotRootPath = os.getcwd()
  pilotParams.pilotScript = os.path.realpath( sys.argv[0] )
  pilotParams.pilotScriptName = os.path.basename( pilotParams.pilotScript )
  log.debug( 'PARAMETER [%s]' % ', '.join( map( str, pilotParams.optList ) ) )

  log.info( ' Getting commands from CS ' )
  access_token = open( os.environ["OA_USER_TOKEN"], 'r' )
  pilotCommands = requests.get( REST_URL + '/config/Value',
                                params = {'access_token':access_token.read(),
                                         'ValuePath':'/Operations/LHCb-Certification/Pilot/Commands/BOINC'}, verify = False )
  log.info( "Executing commands: %s" % str( pilotCommands.text ) )

  # pilotParams.retrievePilotParameters()

  if pilotParams.commandExtensions:
    log.info( "Requested command extensions: %s" % str( pilotParams.commandExtensions ) )

  for commandName in pilotCommands:
    command, module = getCommand( pilotParams, commandName, log )
    if command is not None:
      log.info( "Command %s instantiated from %s" % ( commandName, module ) )
      command.execute()
    else:
      log.error( "Command %s could not be instantiated" % commandName )
      sys.exit( -1 )

