""" Temporary until this is included in pilotCommands.py
"""

import sys
import os
import stat
import socket

from pilotTools import CommandBase, retrieveUrlTimeout

__RCSID__ = "$Id$"

class NagiosProbes( CommandBase ):
  """ Run one or more Nagios probe scripts that follow the Nagios Plugin API:
       https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html
  
      Each probe is a script or executable present in the pilot directory, which is
      executed to gather its return code and stdout messages. Probe name = filename.
      
      Probes must not expect any command line arguments but can gather information about
      the current machine from expected environment variables etc.
  
      The results are reported through the Pilot Logger.
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( NagiosProbes, self ).__init__( pilotParams )
    self.nagiosProbes = []
    self.nagiosPutURL = None

  def _setNagiosOptions( self ):
    """ Setup installation parameters
    """
    for o, v in self.pp.optList:
      if o == '--nagiosProbes':
        self.nagiosProbes.append( v )
      elif o == '--nagiosPutURL':
        self.nagiosPutURL = v
        
    # FIXME: Also need to look for list from pilot.json NagiosProbes

    self.log.debug( 'NAGIOS PROBES [%s]' % ', '.join( self.nagiosProbes )

  def _runNagiosProbes( self ):
    """ Run the probes one by one
    """

    for probeCmd in self.nagiosProbes:
     self.log.debug( "Running Nagios probe %s" % probeCmd )

     retCode, output = self.executeAndGetOutput( probeCmd )
     self.log.info( 'Return = %d: %s' % ( retCode, output), header = False )
     
     # report results to pilot logger too:
     #   NagiosProbes, probeCmd, Retcode mapped to status, message
     
     if self.NagiosPutURL:
       # Alternate logging of results to depo service too
       # (Using a real proxy won't work with curl!!! Need to do this another way)
       self.executeAndGetOutput( 'echo ' + str(retCode) + ' ' + output + ' | curl --capath /etc/grid-security/certificates --cert $X509_USER_PROXY --location --upload-file - ' + self.nagiosPutURL + self.pp.ceName + '/' + probeCmd )

  def execute( self ):
    """ Standard entry point to a pilot command
    """
    self._setNagiosOptions()
    self._runNagiosProbes()
