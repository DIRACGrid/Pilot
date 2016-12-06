""" Extension of a standard set of pilot commands

    Each commands is represented by a class inheriting CommandBase class.
    The command class constructor takes PilotParams object which is a data
    structure which keeps common parameters across all the pilot commands.

    The constructor must call the superclass constructor with the PilotParams
    object and the command name as arguments, e.g. ::

        class InstallDIRAC( CommandBase ):

          def __init__( self, pilotParams ):
            CommandBase.__init__(self, pilotParams, 'Install')
            ...

    The command class must implement execute() method for the actual command
    execution.
"""
import os
import stat
import httplib

from Pilot.PilotTools import CommandBase

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
    """ Setup list of Nagios probes and optional PUT URL from pilot.json
    """

    try:
      self.nagiosProbes = [str( pv ).strip()
                           for pv in self.pilotParams.pilotJSON['Setups'][self.pilotParams.setup]['NagiosProbes'].split(',')]
    except KeyError:
      try:
        self.nagiosProbes = [str( pv ).strip() for pv in self.pilotParams.pilotJSON['Setups']['Defaults']['NagiosProbes'].split(',')]
      except KeyError:
        pass

    try:
      self.nagiosPutURL = str( self.pilotParams.pilotJSON['Setups'][self.pilotParams.setup]['NagiosPutURL'] )
    except KeyError:
      try:
        self.nagiosPutURL = str( self.pilotParams.pilotJSON['Setups']['Defaults']['NagiosPutURL'] )
      except KeyError:
        pass

    self.log.debug( 'NAGIOS PROBES [%s]' % ', '.join( self.nagiosProbes ) )

  def _runNagiosProbes( self ):
    """ Run the probes one by one
    """

    for probeCmd in self.nagiosProbes:
      self.log.debug( "Running Nagios probe %s" % probeCmd )

      try:
        # Make sure the probe is executable
        os.chmod( probeCmd, stat.S_IXUSR + os.stat( probeCmd ).st_mode )

      except OSError:
        self.log.error( 'File %s is missing! Skipping test' % probeCmd )
        retCode = 2
        output  = 'Probe file %s missing from pilot!' % probeCmd

      else:
        # FIXME: need a time limit on this in case the probe hangs
        retCode, output = self.executeAndGetOutput( './' + probeCmd )

      if retCode == 0:
        self.log.info( 'Return code = 0: %s' % output.split('\n',1)[0] )
        # retStatus = 'info'
      elif retCode == 1:
        self.log.warn( 'Return code = 1: %s' % output.split('\n',1)[0] )
        # retStatus = 'warning'
      else:
        # retCode could be 2 (error) or 3 (unknown) or something we haven't thought of
        self.log.error( 'Return code = %d: %s' % ( retCode, output.split('\n',1)[0] ) )
        # retStatus = 'error'

      # report results to pilot logger too. Like this:
      #   "NagiosProbes", probeCmd, retStatus, str(retCode) + ' ' + output.split('\n',1)[0]

      if self.nagiosPutURL:
        # Alternate logging of results to HTTPS PUT service too
        hostPort = self.nagiosPutURL.split('/')[2]
        path = '/' + '/'.join( self.nagiosPutURL.split('/')[3:] ) + self.pilotParams.ceName + '/' + probeCmd

        self.log.info( 'Putting %s Nagios output to https://%s%s' % ( probeCmd, hostPort, path ) )

        try:
          connection = httplib.HTTPSConnection( host      = hostPort,
                                                timeout   = 30,
                                                key_file  = os.environ['X509_USER_PROXY'],
                                                cert_file = os.environ['X509_USER_PROXY'] )

          connection.request( 'PUT', path, str(retCode) + '\n' + output )

        except Exception as e:
          self.log.error( 'PUT of %s Nagios output fails with %s' % ( probeCmd, str(e) ) )

        else:
          result = connection.getresponse()

          if result.status / 100 == 2:
            self.log.info( 'PUT of %s Nagios output succeeds with %d %s' % ( probeCmd, result.status, result.reason ) )
          else :
            self.log.error( 'PUT of %s Nagios output fails with %d %s' % ( probeCmd, result.status, result.reason ) )

  def execute( self ):
    """ Standard entry point to a pilot command
    """
    self._setNagiosOptions()
    self._runNagiosProbes()
