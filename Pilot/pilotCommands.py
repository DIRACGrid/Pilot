""" Definitions of a standard set of pilot commands

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

import sys
import os
import time
import stat
import socket
import urllib
import tarfile
import httplib

from pilotTools import CommandBase

__RCSID__ = "$Id$"

class GetPilotVersion( CommandBase ):
  """ Now just returns what was obtained by pilotTools.py
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( GetPilotVersion, self ).__init__( pilotParams )

  def execute(self):
    """ Just returns what was obtained by pilotTools.py
    """
    return self.pp.releaseVersion

class CheckWorkerNode( CommandBase ):
  """ Executes some basic checks
  """
  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( CheckWorkerNode, self ).__init__( pilotParams )

  def execute( self ):
    """ Get host and local user info, and other basic checks, e.g. space available
    """

    self.log.info( 'Uname      = %s' % " ".join( os.uname() ) ,True, True)
    self.log.info( 'Host Name  = %s' % socket.gethostname() ,True, True)
    self.log.info( 'Host FQDN  = %s' % socket.getfqdn() ,True, True)
    self.log.info( 'WorkingDir = %s' % self.pp.workingDir ,True, True)  # this could be different than rootPath

    fileName = '/etc/redhat-release'
    if os.path.exists( fileName ):
      f = open( fileName, 'r' )
      self.log.info( 'RedHat Release = %s' % f.read().strip() )
      f.close()

    fileName = '/etc/lsb-release'
    if os.path.isfile( fileName ):
      f = open( fileName, 'r' )
      self.log.info( 'Linux release:\n%s' % f.read().strip() )
      f.close()

    fileName = '/proc/cpuinfo'
    if os.path.exists( fileName ):
      f = open( fileName, 'r' )
      cpu = f.readlines()
      f.close()
      nCPU = 0
      for line in cpu:
        if line.find( 'cpu MHz' ) == 0:
          nCPU += 1
          freq = line.split()[3]
        elif line.find( 'model name' ) == 0:
          CPUmodel = line.split( ': ' )[1].strip()
      self.log.info( 'CPU (model)    = %s' % CPUmodel )
      self.log.info( 'CPU (MHz)      = %s x %s' % ( nCPU, freq ) )

    fileName = '/proc/meminfo'
    if os.path.exists( fileName ):
      f = open( fileName, 'r' )
      mem = f.readlines()
      f.close()
      freeMem = 0
      for line in mem:
        if line.find( 'MemTotal:' ) == 0:
          totalMem = int( line.split()[1] )
        if line.find( 'MemFree:' ) == 0:
          freeMem += int( line.split()[1] )
        if line.find( 'Cached:' ) == 0:
          freeMem += int( line.split()[1] )
      self.log.info( 'Memory (kB)    = %s' % totalMem )
      self.log.info( 'FreeMem. (kB)  = %s' % freeMem )

    ###########################################################################
    # Disk space check

    # fs = os.statvfs( rootPath )
    fs = os.statvfs( self.pp.workingDir )
    # bsize;    /* file system block size */
    # frsize;   /* fragment size */
    # blocks;   /* size of fs in f_frsize units */
    # bfree;    /* # free blocks */
    # bavail;   /* # free blocks for non-root */
    # files;    /* # inodes */
    # ffree;    /* # free inodes */
    # favail;   /* # free inodes for non-root */
    # flag;     /* mount flags */
    # namemax;  /* maximum filename length */
    diskSpace = fs[4] * fs[0] / 1024 / 1024
    self.log.info( 'DiskSpace (MB) = %s' % diskSpace )

    if diskSpace < self.pp.minDiskSpace:
      self.log.error( '%s MB < %s MB, not enough local disk space available, exiting'
                      % ( diskSpace, self.pp.minDiskSpace ) )
      sys.exit( 1 )



class InstallDIRAC( CommandBase ):
  """ Basically, this is used to call dirac-install with the passed parameters.

      It requires dirac-install script to be sitting in the same directory.
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( InstallDIRAC, self ).__init__( pilotParams )
    self.installOpts = []
    self.pp.rootPath = self.pp.pilotRootPath
    self.installScriptName = 'dirac-install.py'
    self.installScript = ''

  def _setInstallOptions( self ):
    """ Setup installation parameters
    """
    for o, v in self.pp.optList:
      if o in ( '-b', '--build' ):
        self.installOpts.append( '-b' )
      elif o == '-d' or o == '--debug':
        self.installOpts.append( '-d' )
      elif o == '-e' or o == '--extraPackages':
        self.installOpts.append( '-e "%s"' % v )
      elif o == '-g' or o == '--grid':
        self.pp.gridVersion = v
      elif o == '-i' or o == '--python':
        self.pp.pythonVersion = v
      elif o == '-p' or o == '--platform':
        self.pp.platform = v
      elif o == '-u' or o == '--url':
        self.installOpts.append( '-u "%s"' % v )
      elif o in ( '-P', '--path' ):
        self.installOpts.append( '-P "%s"' % v )
        self.pp.rootPath = v
      elif o in ( '-V', '--installation' ):
        self.installOpts.append( '-V "%s"' % v )
      elif o == '-t' or o == '--server':
        self.installOpts.append( '-t "server"' )

    if self.pp.gridVersion:
      self.installOpts.append( "-g '%s'" % self.pp.gridVersion )
    if self.pp.pythonVersion:
      self.installOpts.append( "-i '%s'" % self.pp.pythonVersion )
    if self.pp.platform:
      self.installOpts.append( '-p "%s"' % self.pp.platform )
    if self.pp.releaseProject:
      self.installOpts.append( "-l '%s'" % self.pp.releaseProject )

    # The release version to install is a requirement
    self.installOpts.append( '-r "%s"' % self.pp.releaseVersion )

    self.log.debug( 'INSTALL OPTIONS [%s]' % ', '.join( map( str, self.installOpts ) ) )

  def _locateInstallationScript( self ):
    """ Locate installation script
    """
    installScript = ''
    for path in ( self.pp.pilotRootPath, self.pp.originalRootPath, self.pp.rootPath ):
      installScript = os.path.join( path, self.installScriptName )
      if os.path.isfile( installScript ):
        break
    self.installScript = installScript

    if not os.path.isfile( installScript ):
      self.log.error( "%s requires %s to exist in one of: %s, %s, %s" % ( self.pp.pilotScriptName,
                                                                          self.installScriptName,
                                                                          self.pp.pilotRootPath,
                                                                          self.pp.originalRootPath,
                                                                          self.pp.rootPath ) )
      sys.exit( 1 )

    try:
      # change permission of the script
      os.chmod( self.installScript, stat.S_IRWXU )
    except OSError:
      pass

  def _installDIRAC( self ):
    """ Install DIRAC or its extension, then parse the environment file created, and use it for subsequent calls
    """
    # Installing
    installCmd = "%s %s" % ( self.installScript, " ".join( self.installOpts ) )
    self.log.debug( "Installing with: %s" % installCmd )

    # At this point self.pp.installEnv may coincide with os.environ
    # If extensions want to pass in a modified environment, it's easy to set self.pp.installEnv in an extended command
    retCode, output = self.executeAndGetOutput( installCmd, self.pp.installEnv )
    self.log.info( output, header = False )

    if retCode:
      self.log.error( "Could not make a proper DIRAC installation [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    self.log.info( "%s completed successfully" % self.installScriptName )

    # Parsing the bashrc then adding its content to the installEnv
    # at this point self.pp.installEnv may still coincide with os.environ
    retCode, output = self.executeAndGetOutput( 'bash -c "source bashrc && env"', self.pp.installEnv )
    if retCode:
      self.log.error( "Could not parse the bashrc file [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    for line in output.split('\n'):
      try:
        var, value = [vx.strip() for vx in line.split( '=', 1 )]
        if var == '_' or 'SSH' in var or '{' in value or '}' in value: # Avoiding useless/confusing stuff
          continue
        self.pp.installEnv[var] = value
      except (IndexError, ValueError):
        continue
    # At this point self.pp.installEnv should contain all content of bashrc, sourced "on top" of (maybe) os.environ
    self.pp.diracInstalled = True

  def execute( self ):
    """ What is called all the time
    """
    self._setInstallOptions()
    self._locateInstallationScript()
    self._installDIRAC()

class ReplaceDIRACCode( CommandBase ):
  """ This command will replace DIRAC code with the one taken from a different location.
      This command is mostly for testing purposes, and should NOT be added in default configurations.

      It uses -Y/--replaceDIRACCode option for specifying a TGZ archive with a URL which can be opened by
      urllib.urlopen (on a webserver or a local .tgz file downloaded with the pilot directory.)
      
      The TGZ file should be created by something equivalent to this
        cd /cvmfs/lhcb.cern.ch/lib/lhcb/DIRAC/DIRAC_v6r17p33
        tar zcvf /tmp/DIRACdev.tgz *
      so the DIRAC directory itself AND the scripts directory at the same level are included and will be 
      unpacked in the ReplacementCode directory, which itself is added to PYTHONPATH. You must ensure that
      the executable bits for scripts are retained when making the TGZ archive (they should be by default.)

      You can include other packages (eg LHCbDIRAC) which should be found by Python, by including them at
      that same top level when making the TGZ file.
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( ReplaceDIRACCode, self ).__init__( pilotParams )

  def execute(self):
    """ Download/untar a TGZ archive file
    """
    if not self.pp.replaceDIRACCode:
      self.log.warn( "No -Y/--replaceDIRACCode given so no action by ReplaceDIRACCode pilot command!" )
      return

    os.mkdir( os.getcwd() + os.path.sep + 'ReplacementCode' )
    
    # Fetch and unpack the TGZ file
    tar = tarfile.open( mode = "r|gz", fileobj = urllib.urlopen( self.pp.replaceDIRACCode ) )
    tar.extractall( os.getcwd() + os.path.sep + 'ReplacementCode' )
    tar.close()

    # Add the ReplacementCode directory to the Python path
    self.pp.installEnv['PYTHONPATH'] = os.getcwd() + os.path.sep + 'ReplacementCode' + ':' + self.pp.installEnv['PYTHONPATH']
    self.pp.installEnv['PATH'] = os.getcwd() + os.path.sep + 'ReplacementCode' + os.path.sep + 'scripts:' + self.pp.installEnv['PATH']

    self.log.info( "TGZ file %s unpacked. PYTHONPATH updated to be %s and PATH updated to be %s" % 
                         ( self.pp.replaceDIRACCode, self.pp.installEnv['PYTHONPATH'], self.pp.installEnv['PATH'] ) )

class ConfigureBasics( CommandBase ):
  """ This command completes DIRAC installation.

  It calls dirac-configure to:

      * download, by default, the CAs
      * creates a standard or custom (defined by self.pp.localConfigFile) cfg file
        to be used where all the pilot configuration is to be set, e.g.:
      * adds to it basic info like the version
      * adds to it the security configuration

  If there is more than one command calling dirac-configure, this one should be always the first one called.

  .. note:: Further commands should always call dirac-configure using the options -FDMH
  .. note:: If custom cfg file is created further commands should call dirac-configure with
             "-O %s %s" % ( self.pp.localConfigFile, self.pp.localConfigFile )

  From here on, we have to pay attention to the paths. Specifically, we need to know where to look for

      * executables (scripts)
      * DIRAC python code

  If the pilot has installed DIRAC (and extensions) in the traditional way, so using the dirac-install.py script,
  simply the current directory is used, and:

      * scripts will be in $CWD/scripts.
      * DIRAC python code will be all sitting in $CWD
      * the local dirac.cfg file will be found in $CWD/etc

  For a more general case of non-traditional installations, we should use the PATH and PYTHONPATH as set by the
  installation phase. Executables and code will be searched there.
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( ConfigureBasics, self ).__init__( pilotParams )
    self.cfg = []


  def execute( self ):
    """ What is called all the times.

        VOs may want to replace/extend the _getBasicsCFG and _getSecurityCFG functions
    """

    self._getBasicsCFG()
    self._getSecurityCFG()

    if self.pp.debugFlag:
      self.cfg.append( '-ddd' )
    if self.pp.localConfigFile:
      self.cfg.append( '-O %s' % self.pp.localConfigFile )

    configureCmd = "%s %s" % ( self.pp.configureScript, " ".join( self.cfg ) )

    retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pp.installEnv )

    if retCode:
      self.log.error( "Could not configure DIRAC basics [ERROR %d]" % retCode )
      self.exitWithError( retCode )

  def _getBasicsCFG( self ):
    """  basics (needed!)
    """
    self.cfg.append( '-S "%s"' % self.pp.setup )
    if self.pp.configServer:
      self.cfg.append( '-C "%s"' % self.pp.configServer )
    if self.pp.releaseProject:
      self.cfg.append( '-e "%s"' % self.pp.releaseProject )
      self.cfg.append( '-o /LocalSite/ReleaseProject=%s' % self.pp.releaseProject )
    if self.pp.gateway:
      self.cfg.append( '-W "%s"' % self.pp.gateway )
    if self.pp.userGroup:
      self.cfg.append( '-o /AgentJobRequirements/OwnerGroup="%s"' % self.pp.userGroup )
    if self.pp.userDN:
      self.cfg.append( '-o /AgentJobRequirements/OwnerDN="%s"' % self.pp.userDN )
    self.cfg.append( '-o /LocalSite/ReleaseVersion=%s' % self.pp.releaseVersion )

  def _getSecurityCFG( self ):
    """ Nothing specific by default, but need to know host cert and key location in case they are needed
    """
    if self.pp.useServerCertificate:
      self.cfg.append( '--UseServerCertificate' )
      self.cfg.append( "-o /DIRAC/Security/CertFile=%s/hostcert.pem" % self.pp.certsLocation )
      self.cfg.append( "-o /DIRAC/Security/KeyFile=%s/hostkey.pem" % self.pp.certsLocation )

class CheckCECapabilities( CommandBase ):
  """ Used to get CE tags and other relevant parameters.
  """
  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( CheckCECapabilities, self ).__init__( pilotParams )

    # this variable contains the options that are passed to dirac-configure, and that will fill the local dirac.cfg file
    self.cfg = []

  def execute( self ):
    """ Setup CE/Queue Tags and other relevant parameters.
    """

    if self.pp.useServerCertificate:
      self.cfg.append( '-o  /DIRAC/Security/UseServerCertificate=yes' )
    if self.pp.localConfigFile:
      self.cfg.append( self.pp.localConfigFile )  # this file is as input

    # Get the resource description as defined in its configuration
    checkCmd = 'dirac-resource-get-parameters -S %s -N %s -Q %s %s' % ( self.pp.site,
                                                                        self.pp.ceName,
                                                                        self.pp.queueName,
                                                                        " ".join( self.cfg ) )
    retCode, resourceDict = self.executeAndGetOutput( checkCmd, self.pp.installEnv )
    if retCode:
      self.log.error( "Could not get resource parameters [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    try:
      import json
      resourceDict = json.loads( resourceDict )
    except ValueError:
      self.log.error( "The pilot command output is not json compatible." )
      sys.exit( 1 )

    self.pp.queueParameters = resourceDict

    cfg = []

    # Pick up all the relevant resource parameters that will be used in the job matching
    for ceParam in [ "WholeNode", "NumberOfProcessors" ]:
      if ceParam in resourceDict:
        cfg.append( '-o /Resources/Computing/CEDefaults/%s=%s' % ( ceParam, resourceDict[ ceParam ] ) )

     # Tags must be added to already defined tags if any
    if resourceDict.get( 'Tag' ):
      self.pp.tags += resourceDict['Tag']

    if self.pp.tags:
      cfg.append( '-o "/Resources/Computing/CEDefaults/Tag=%s"' % ','.join( ( str( x ) for x in self.pp.tags ) ) )

    # RequiredTags are like Tags.
    if resourceDict.get( 'RequiredTag' ):
      self.pp.reqtags += resourceDict['RequiredTag']

    if self.pp.reqtags:
      cfg.append('-o "/Resources/Computing/CEDefaults/RequiredTag=%s"' %
                      ','.join((str(x) for x in self.pp.reqtags)))

    # If there is anything to be added to the local configuration, let's do it
    if self.pp.useServerCertificate:
      cfg.append( '-o /DIRAC/Security/UseServerCertificate=yes' )

    if self.pp.localConfigFile:
      cfg.append( '-O %s' % self.pp.localConfigFile )  # this file is as output
      cfg.append( self.pp.localConfigFile )  # this file is as input


    if cfg:
      cfg.append( '-FDMH' )

      if self.debugFlag:
        cfg.append( '-ddd' )

      configureCmd = "%s %s" % (self.pp.configureScript, " ".join(cfg))
      retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pp.installEnv )
      if retCode:
        self.log.error( "Could not configure DIRAC [ERROR %d]" % retCode )
        self.exitWithError( retCode )

    else:
      self.log.debug("No CE parameters (tags) defined for %s/%s" % (self.pp.ceName, self.pp.queueName))

class CheckWNCapabilities( CommandBase ):
  """ Used to get capabilities specific to the Worker Node. This command must be called
      after the CheckCECapabilities command
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( CheckWNCapabilities, self ).__init__( pilotParams )
    self.cfg = []

  def execute( self ):
    """ Discover NumberOfProcessors and RAM
    """

    if self.pp.useServerCertificate:
      self.cfg.append( '-o /DIRAC/Security/UseServerCertificate=yes' )
    if self.pp.localConfigFile:
      self.cfg.append( self.pp.localConfigFile )  # this file is as input
    # Get the worker node parameters
    checkCmd = 'dirac-wms-get-wn-parameters -S %s -N %s -Q %s %s' % (self.pp.site,
                                                                     self.pp.ceName,
                                                                     self.pp.queueName,
                                                                      " ".join( self.cfg ) )
    retCode, result = self.executeAndGetOutput( checkCmd, self.pp.installEnv )
    if retCode:
      self.log.error( "Could not get resource parameters [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    numberOfProcessors = 0
    try:
      result = result.split( ' ' )
      numberOfProcessors = int( result[0] )
      maxRAM = int( result[1] )
    except ValueError:
      self.log.error( "Wrong Command output %s" % result )
      sys.exit( 1 )

    cfg = []
    # If NumberOfProcessors or MaxRAM are defined in the resource configuration, these
    # values are preferred
    numberOfProcessors = self.pp.queueParameters.get(
        'NumberOfProcessors', numberOfProcessors)
    # if maxNumberOfProcessors is asked in pilotWrapper
    if self.pp.maxNumberOfProcessors:
      self.log.debug("Overriding with a requested number of processors")
      numberOfProcessors = self.pp.maxNumberOfProcessors

    if not numberOfProcessors:
      self.log.warn("Could not retrieve number of processors, assuming 1")
      numberOfProcessors = 1
    self.cfg.append(
        '-o "/Resources/Computing/CEDefaults/NumberOfProcessors=%d"' % int(numberOfProcessors))

    maxRAM = self.pp.queueParameters.get('MaxRAM', maxRAM)
    if maxRAM:
      try:
        self.cfg.append(
            '-o "/Resources/Computing/CEDefaults/MaxRAM=%d"' % int(maxRAM))
      except ValueError:
        self.log.warn("MaxRAM is not an integer, will not fill it")
    else:
      self.log.warn(
          "Could not retrieve MaxRAM, this parameter won't be filled")

    if cfg:
      cfg.append( '-FDMH' )

      if self.pp.useServerCertificate:
        cfg.append( '-o /DIRAC/Security/UseServerCertificate=yes' )
      if self.pp.localConfigFile:
        cfg.append( '-O %s' % self.pp.localConfigFile )  # this file is as output
        cfg.append( self.pp.localConfigFile )  # this file is as input

      if self.debugFlag:
        cfg.append('-ddd')

      configureCmd = "%s %s" % (self.pp.configureScript, " ".join(cfg))
      retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pp.installEnv )
      if retCode:
        self.log.error( "Could not configure DIRAC [ERROR %d]" % retCode )
        self.exitWithError( retCode )


class ConfigureSite( CommandBase ):
  """ Command to configure DIRAC sites using the pilot options
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( ConfigureSite, self ).__init__( pilotParams )

    # this variable contains the options that are passed to dirac-configure, and that will fill the local dirac.cfg file
    self.cfg = []

    self.boincUserID = ''
    self.boincHostID = ''
    self.boincHostPlatform = ''
    self.boincHostName = ''

  def execute( self ):
    """ Setup configuration parameters
    """
    self.__setFlavour()
    self.cfg.append( '-o /LocalSite/GridMiddleware=%s' % self.pp.flavour )

    self.cfg.append( '-n "%s"' % self.pp.site )
    self.cfg.append( '-S "%s"' % self.pp.setup )

    if not self.pp.ceName or not self.pp.queueName:
      self.__getCEName()
    self.cfg.append( '-N "%s"' % self.pp.ceName )
    self.cfg.append( '-o /LocalSite/GridCE=%s' % self.pp.ceName )
    self.cfg.append( '-o /LocalSite/CEQueue=%s' % self.pp.queueName )
    if self.pp.ceType:
      self.cfg.append( '-o /LocalSite/LocalCE=%s' % self.pp.ceType )

    for o, v in self.pp.optList:
      if o == '-o' or o == '--option':
        self.cfg.append( '-o "%s"' % v )
      elif o == '-s' or o == '--section':
        self.cfg.append( '-s "%s"' % v )


    if self.pp.pilotReference != 'Unknown':
      self.cfg.append( '-o /LocalSite/PilotReference=%s' % self.pp.pilotReference )
    # add options for BOINc
    # FIXME: this should not be part of the standard configuration
    if self.boincUserID:
      self.cfg.append( '-o /LocalSite/BoincUserID=%s' % self.boincUserID )
    if self.boincHostID:
      self.cfg.append( '-o /LocalSite/BoincHostID=%s' % self.boincHostID )
    if self.boincHostPlatform:
      self.cfg.append( '-o /LocalSite/BoincHostPlatform=%s' % self.boincHostPlatform )
    if self.boincHostName:
      self.cfg.append( '-o /LocalSite/BoincHostName=%s' % self.boincHostName )

    if self.pp.useServerCertificate:
      self.cfg.append( '--UseServerCertificate' )
      self.cfg.append( "-o /DIRAC/Security/CertFile=%s/hostcert.pem" % self.pp.certsLocation )
      self.cfg.append( "-o /DIRAC/Security/KeyFile=%s/hostkey.pem" % self.pp.certsLocation )

    # these are needed as this is not the fist time we call dirac-configure
    self.cfg.append( '-FDMH' )
    if self.pp.localConfigFile:
      self.cfg.append( '-O %s' % self.pp.localConfigFile )
      self.cfg.append( self.pp.localConfigFile )

    if self.debugFlag:
      self.cfg.append( '-ddd' )

    configureCmd = "%s %s" % ( self.pp.configureScript, " ".join( self.cfg ) )

    retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pp.installEnv )

    if retCode:
      self.log.error( "Could not configure DIRAC [ERROR %d]" % retCode )
      self.exitWithError( retCode )

  def __setFlavour( self ):

    pilotRef = 'Unknown'
    self.pp.flavour = 'Generic'

    # If pilot reference is specified at submission, then set flavour to DIRAC
    # unless overridden by presence of batch system environment variables
    if self.pp.pilotReference:
      self.pp.flavour = 'DIRAC'
      pilotRef = self.pp.pilotReference

    # Take the reference from the Torque batch system
    if 'PBS_JOBID' in os.environ:
      self.pp.flavour = 'SSHTorque'
      pilotRef = 'sshtorque://' + self.pp.ceName + '/' + os.environ['PBS_JOBID'].split('.')[0]

    # Take the reference from the OAR batch system
    if 'OAR_JOBID' in os.environ:
      self.pp.flavour = 'SSHOAR'
      pilotRef = 'sshoar://' + self.pp.ceName + '/' + os.environ['OAR_JOBID']

    # Grid Engine
    if 'JOB_ID' in os.environ and 'SGE_TASK_ID' in os.environ:
      self.pp.flavour = 'SSHGE'
      pilotRef = 'sshge://' + self.pp.ceName + '/' + os.environ['JOB_ID']
    # Generic JOB_ID
    elif 'JOB_ID' in os.environ:
      self.pp.flavour = 'Generic'
      pilotRef = 'generic://' + self.pp.ceName + '/' + os.environ['JOB_ID']

    # Condor
    if 'CONDOR_JOBID' in os.environ:
      self.pp.flavour = 'SSHCondor'
      pilotRef = 'sshcondor://' + self.pp.ceName + '/' + os.environ['CONDOR_JOBID']

    # HTCondor
    if 'HTCONDOR_JOBID' in os.environ:
      self.pp.flavour = 'HTCondorCE'
      pilotRef = 'htcondorce://' + self.pp.ceName + '/' + os.environ['HTCONDOR_JOBID']

    # LSF
    if 'LSB_BATCH_JID' in os.environ:
      self.pp.flavour = 'SSHLSF'
      pilotRef = 'sshlsf://' + self.pp.ceName + '/' + os.environ['LSB_BATCH_JID']

    #  SLURM batch system
    if 'SLURM_JOBID' in os.environ:
      self.pp.flavour = 'SSHSLURM'
      pilotRef = 'sshslurm://' + self.pp.ceName + '/' + os.environ['SLURM_JOBID']

    # This is the CREAM direct submission case
    if 'CREAM_JOBID' in os.environ:
      self.pp.flavour = 'CREAM'
      pilotRef = os.environ['CREAM_JOBID']

    if 'OSG_WN_TMP' in os.environ:
      self.pp.flavour = 'OSG'

    # GLOBUS Computing Elements
    if 'GLOBUS_GRAM_JOB_CONTACT' in os.environ:
      self.pp.flavour = 'GLOBUS'
      pilotRef = os.environ['GLOBUS_GRAM_JOB_CONTACT']

    # Direct SSH tunnel submission
    if 'SSHCE_JOBID' in os.environ:
      self.pp.flavour = 'SSH'
      pilotRef = 'ssh://' + self.pp.ceName + '/' + os.environ['SSHCE_JOBID']

    # ARC case
    if 'GRID_GLOBAL_JOBID' in os.environ:
      self.pp.flavour = 'ARC'
      pilotRef = os.environ['GRID_GLOBAL_JOBID']

    # VMDIRAC case
    if 'VMDIRAC_VERSION' in os.environ:
      self.pp.flavour = 'VMDIRAC'
      pilotRef = 'vm://' + self.pp.ceName + '/' + os.environ['JOB_ID']

    # This is for BOINC case
    if 'BOINC_JOB_ID' in os.environ:
      self.pp.flavour = 'BOINC'
      pilotRef = os.environ['BOINC_JOB_ID']

    if self.pp.flavour == 'BOINC':
      if 'BOINC_USER_ID' in os.environ:
        self.boincUserID = os.environ['BOINC_USER_ID']
      if 'BOINC_HOST_ID' in os.environ:
        self.boincHostID = os.environ['BOINC_HOST_ID']
      if 'BOINC_HOST_PLATFORM' in os.environ:
        self.boincHostPlatform = os.environ['BOINC_HOST_PLATFORM']
      if 'BOINC_HOST_NAME' in os.environ:
        self.boincHostName = os.environ['BOINC_HOST_NAME']

    # Pilot reference is given explicitly in environment
    if 'PILOT_UUID' in os.environ:
      pilotRef = os.environ['PILOT_UUID']

    # Pilot reference is specified at submission
    if self.pp.pilotReference:
      pilotRef = self.pp.pilotReference

    self.log.debug( "Flavour: %s; pilot reference: %s " % ( self.pp.flavour, pilotRef ) )

    self.pp.pilotReference = pilotRef

  def __getCEName( self ):
    """ Try to get the CE name
    """
    # FIXME: this should not be part of the standard configuration (flavours discriminations should stay out)
    if self.pp.flavour in ['LCG', 'OSG']:
      retCode, CEName = self.executeAndGetOutput( 'glite-brokerinfo getCE',
                                                  self.pp.installEnv )
      if retCode:
        self.log.warn( "Could not get CE name with 'glite-brokerinfo getCE' command [ERROR %d]" % retCode )
        if 'OSG_JOB_CONTACT' in os.environ:
          # OSG_JOB_CONTACT String specifying the endpoint to use within the job submission
          #                 for reaching the site (e.g. manager.mycluster.edu/jobmanager-pbs )
          CE = os.environ['OSG_JOB_CONTACT']
          self.pp.ceName = CE.split( '/' )[0]
          if len( CE.split( '/' ) ) > 1:
            self.pp.queueName = CE.split( '/' )[1]
          else:
            self.log.error( "CE Name %s not accepted" % CE )
            self.exitWithError( retCode )
        else:
          self.log.info( "Looking if queue name is already present in local cfg" )
          from DIRAC import gConfig
          ceName = gConfig.getValue( 'LocalSite/GridCE', '' )
          ceQueue = gConfig.getValue( 'LocalSite/CEQueue', '' )
          if ceName and ceQueue:
            self.log.debug( "Found CE %s, queue %s" % ( ceName, ceQueue ) )
            self.pp.ceName = ceName
            self.pp.queueName = ceQueue
          else:
            self.log.error( "Can't find ceName nor queue... have to fail!" )
            sys.exit( 1 )
      else:
        self.log.debug( "Found CE %s" % CEName )
        self.pp.ceName = CEName.split( ':' )[0]
        if len( CEName.split( '/' ) ) > 1:
          self.pp.queueName = CEName.split( '/' )[1]
      # configureOpts.append( '-N "%s"' % cliParams.ceName )

    elif self.pp.flavour == "CREAM":
      if 'CE_ID' in os.environ:
        self.log.debug( "Found CE %s" % os.environ['CE_ID'] )
        self.pp.ceName = os.environ['CE_ID'].split( ':' )[0]
        if os.environ['CE_ID'].count( "/" ):
          self.pp.queueName = os.environ['CE_ID'].split( '/' )[1]
        else:
          self.log.error( "Can't find queue name" )
          sys.exit( 1 )
      else:
        self.log.error( "Can't find CE name" )
        sys.exit( 1 )



class ConfigureArchitecture( CommandBase ):
  """ This command simply calls dirac-platfom to determine the platform.
      Separated from the ConfigureDIRAC command for easier extensibility.
  """

  def execute( self ):
    """ This is a simple command to call the dirac-platform utility to get the platform, and add it to the configuration

        The architecture script, as well as its options can be replaced in a pilot extension
    """

    cfg = []
    if self.pp.useServerCertificate:
      cfg.append( '-o  /DIRAC/Security/UseServerCertificate=yes' )
    if self.pp.localConfigFile:
      cfg.append( self.pp.localConfigFile )  # this file is as input

    architectureCmd = "%s %s" % ( self.pp.architectureScript, " ".join( cfg ) )

    retCode, localArchitecture = self.executeAndGetOutput( architectureCmd, self.pp.installEnv )
    if retCode:
      self.log.error( "There was an error updating the platform [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    self.log.debug( "Architecture determined: %s" % localArchitecture )

    # standard options
    cfg = ['-FDMH']  # force update, skip CA checks, skip CA download, skip VOMS
    if self.pp.useServerCertificate:
      cfg.append( '--UseServerCertificate' )
    if self.pp.localConfigFile:
      cfg.append( '-O %s' % self.pp.localConfigFile )  # our target file for pilots
      cfg.append( self.pp.localConfigFile )  # this file is also an input
    if self.pp.debugFlag:
      cfg.append( "-ddd" )

    # real options added here
    localArchitecture = localArchitecture.strip()
    cfg.append( '-S "%s"' % self.pp.setup )
    cfg.append( '-o /LocalSite/Architecture=%s' % localArchitecture )

    configureCmd = "%s %s" % ( self.pp.configureScript, " ".join( cfg ) )
    retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pp.installEnv )
    if retCode:
      self.log.error( "Configuration error [ERROR %d]" % retCode )
      self.exitWithError( retCode )

    return localArchitecture



class ConfigureCPURequirements( CommandBase ):
  """ This command determines the CPU requirements. Needs to be executed after ConfigureSite
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( ConfigureCPURequirements, self ).__init__( pilotParams )

  def execute( self ):
    """ Get job CPU requirement and queue normalization
    """
    # Determining the CPU normalization factor and updating pilot.cfg with it
    configFileArg = ''
    if self.pp.useServerCertificate:
      configFileArg = '-o /DIRAC/Security/UseServerCertificate=yes'
    if self.pp.localConfigFile:
      configFileArg = '%s -R %s %s' % ( configFileArg, self.pp.localConfigFile, self.pp.localConfigFile )
    retCode, cpuNormalizationFactorOutput = self.executeAndGetOutput(
        'dirac-wms-cpu-normalization -U %s' % configFileArg, self.pp.installEnv)
    if retCode:
      self.log.error( "Failed to determine cpu normalization [ERROR %d]" % retCode )
      self.exitWithError( retCode )

    # HS06 benchmark
    # FIXME: this is a (necessary) hack!
    cpuNormalizationFactor = float( cpuNormalizationFactorOutput.split( '\n' )[0].replace( "Estimated CPU power is ",
                                                                                           '' ).replace( " HS06", '' ) )
    self.log.info(
        "Current normalized CPU as determined by 'dirac-wms-cpu-normalization' is %f" %
        cpuNormalizationFactor)

    configFileArg = ''
    if self.pp.useServerCertificate:
      configFileArg = '-o /DIRAC/Security/UseServerCertificate=yes'
    retCode, cpuTimeOutput = self.executeAndGetOutput( 'dirac-wms-get-queue-cpu-time %s %s' % ( configFileArg,
                                                                                                self.pp.localConfigFile ),
                                                       self.pp.installEnv )

    if retCode:
      self.log.error( "Failed to determine cpu time left in the queue [ERROR %d]" % retCode )
      self.exitWithError( retCode )

    for line in cpuTimeOutput.split( '\n' ):
      if "CPU time left determined as" in line:
        # FIXME: this is horrible
        cpuTime = int(line.replace("CPU time left determined as", '').strip())
    self.log.info( "CPUTime left (in seconds) is %s" % cpuTime )

    # HS06s = seconds * HS06
    try:
      # determining the CPU time left (in HS06s)
      self.pp.jobCPUReq = float( cpuTime ) * float( cpuNormalizationFactor )
      self.log.info( "Queue length (which is also set as CPUTimeLeft) is %f" % self.pp.jobCPUReq )
    except ValueError:
      self.log.error( 'Pilot command output does not have the correct format' )
      sys.exit( 1 )
    # now setting this value in local file
    cfg = ['-FDMH']
    if self.pp.useServerCertificate:
      cfg.append( '-o  /DIRAC/Security/UseServerCertificate=yes' )
    if self.pp.localConfigFile:
      cfg.append( '-O %s' % self.pp.localConfigFile )  # our target file for pilots
      cfg.append( self.pp.localConfigFile )  # this file is also input
    cfg.append( '-o /LocalSite/CPUTimeLeft=%s' % str( int( self.pp.jobCPUReq ) ) )  # the only real option

    configureCmd = "%s %s" % ( self.pp.configureScript, " ".join( cfg ) )
    retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pp.installEnv )
    if retCode:
      self.log.error( "Failed to update CFG file for CPUTimeLeft [ERROR %d]" % retCode )
      self.exitWithError( retCode )


class LaunchAgent( CommandBase ):
  """ Prepare and launch the job agent
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( LaunchAgent, self ).__init__( pilotParams )
    self.inProcessOpts = []
    self.jobAgentOpts = []

  def __setInProcessOpts( self ):

    localUid = os.getuid()
    try:
      import pwd
      localUser = pwd.getpwuid( localUid )[0]
    except KeyError:
      localUser = 'Unknown'
    self.log.info( 'User Name  = %s' % localUser )
    self.log.info( 'User Id    = %s' % localUid )
    self.inProcessOpts = ['-s /Resources/Computing/CEDefaults' ]
    self.inProcessOpts.append( '-o WorkingDirectory=%s' % self.pp.workingDir )
    # FIXME: this is artificial
    self.inProcessOpts.append( '-o TotalCPUs=%s' % 1 )
    self.inProcessOpts.append( '-o /LocalSite/MaxCPUTime=%s' % ( int( self.pp.jobCPUReq ) ) )
    self.inProcessOpts.append( '-o /LocalSite/CPUTime=%s' % ( int( self.pp.jobCPUReq ) ) )
    self.inProcessOpts.append( '-o MaxRunningJobs=%s' % 1 )
    # To prevent a wayward agent picking up and failing many jobs.
    self.inProcessOpts.append( '-o MaxTotalJobs=%s' % 10 )
    self.jobAgentOpts = ['-o MaxCycles=%s' % self.pp.maxCycles]

    if self.debugFlag:
      self.jobAgentOpts.append( '-o LogLevel=DEBUG' )
    else:
      self.jobAgentOpts.append( '-o LogLevel=INFO' )

    if self.pp.userGroup:
      self.log.debug( 'Setting DIRAC Group to "%s"' % self.pp.userGroup )
      self.inProcessOpts .append( '-o OwnerGroup="%s"' % self.pp.userGroup )

    if self.pp.userDN:
      self.log.debug( 'Setting Owner DN to "%s"' % self.pp.userDN )
      self.inProcessOpts.append( '-o OwnerDN="%s"' % self.pp.userDN )

    if self.pp.useServerCertificate:
      self.log.debug( 'Setting UseServerCertificate flag' )
      self.inProcessOpts.append( '-o /DIRAC/Security/UseServerCertificate=yes' )

    # The instancePath is where the agent works
    self.inProcessOpts.append( '-o /LocalSite/InstancePath=%s' % self.pp.workingDir )

    # The file pilot.cfg has to be created previously by ConfigureDIRAC
    if self.pp.localConfigFile:
      self.inProcessOpts.append( ' -o /AgentJobRequirements/ExtraOptions=%s' % self.pp.localConfigFile )
      self.inProcessOpts.append( self.pp.localConfigFile )


  def __startJobAgent( self ):
    """ Starting of the JobAgent (or of a user-defined command)
    """

    diracAgentScript = "dirac-agent"

    # Find any .cfg file uploaded with the sandbox or generated by previous commands
    # and add it in input of the JobAgent run
    extraCFG = []
    for i in os.listdir( self.pp.rootPath ):
      cfg = os.path.join( self.pp.rootPath, i )
      if os.path.isfile( cfg ) and cfg.endswith( '.cfg' ):
        extraCFG.append( cfg )

    if self.pp.executeCmd:
      # Execute user command
      self.log.info( "Executing user defined command: %s" % self.pp.executeCmd )
      self.exitWithError( os.system( "source bashrc; %s" % self.pp.executeCmd ) / 256 )

    self.log.info( 'Starting JobAgent' )
    os.environ['PYTHONUNBUFFERED'] = 'yes'

    jobAgent = '%s WorkloadManagement/JobAgent %s %s %s' % ( diracAgentScript,
                                                             " ".join( self.jobAgentOpts ),
                                                             " ".join( self.inProcessOpts ),
                                                             " ".join( extraCFG ) )


    retCode, _output = self.executeAndGetOutput( jobAgent, self.pp.installEnv )
    if retCode:
      self.log.error( "Error executing the JobAgent [ERROR %d]" % retCode )
      self.exitWithError( retCode )

    fs = os.statvfs( self.pp.workingDir )
    diskSpace = fs[4] * fs[0] / 1024 / 1024
    self.log.info( 'DiskSpace (MB) = %s' % diskSpace )

  def execute( self ):
    """ What is called all the time
    """
    self.__setInProcessOpts()
    self.__startJobAgent()

    sys.exit( 0 )

class MultiLaunchAgent( CommandBase ):
  """ Prepare and launch multiple agents
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( MultiLaunchAgent, self ).__init__( pilotParams )
    self.inProcessOpts = []
    self.jobAgentOpts = []

  def __setInProcessOpts( self ):

    localUid = os.getuid()
    try:
      import pwd
      localUser = pwd.getpwuid( localUid )[0]
    except KeyError:
      localUser = 'Unknown'
    self.log.info( 'User Name  = %s' % localUser )
    self.log.info( 'User Id    = %s' % localUid )
    self.inProcessOpts = ['-s /Resources/Computing/CEDefaults' ]
    self.inProcessOpts.append( '-o WorkingDirectory=%s' % self.pp.workingDir )
    self.inProcessOpts.append( '-o /LocalSite/MaxCPUTime=%s' % ( int( self.pp.jobCPUReq ) ) )
    self.inProcessOpts.append( '-o /LocalSite/CPUTime=%s' % ( int( self.pp.jobCPUReq ) ) )
    # To prevent a wayward agent picking up and failing many jobs.
    self.inProcessOpts.append( '-o MaxTotalJobs=%s' % self.pp.maxCycles )
    self.jobAgentOpts= [ '-o MaxCycles=%s' % self.pp.maxCycles,
                         '-o StopAfterFailedMatches=0' ]

    if self.debugFlag:
      self.jobAgentOpts.append( '-o LogLevel=DEBUG' )

    if self.pp.userGroup:
      self.log.debug( 'Setting DIRAC Group to "%s"' % self.pp.userGroup )
      self.inProcessOpts .append( '-o OwnerGroup="%s"' % self.pp.userGroup )

    if self.pp.userDN:
      self.log.debug( 'Setting Owner DN to "%s"' % self.pp.userDN )
      self.inProcessOpts.append( '-o OwnerDN="%s"' % self.pp.userDN )

    if self.pp.useServerCertificate:
      self.log.debug( 'Setting UseServerCertificate flag' )
      self.inProcessOpts.append( '-o /DIRAC/Security/UseServerCertificate=yes' )

    # The instancePath is where the agent works
    self.inProcessOpts.append( '-o /LocalSite/InstancePath=%s' % self.pp.workingDir )

    # The file pilot.cfg has to be created previously by ConfigureDIRAC
    if self.pp.localConfigFile:
      self.inProcessOpts.append( ' -o /AgentJobRequirements/ExtraOptions=%s' % self.pp.localConfigFile )
      self.inProcessOpts.append( self.pp.localConfigFile )


  def __startJobAgent(self):
    """ Starting of the JobAgent
    """

    # Find any .cfg file uploaded with the sandbox or generated by previous commands

    diracAgentScript = "dirac-agent"
    extraCFG = []
    for i in os.listdir( self.pp.rootPath ):
      cfg = os.path.join( self.pp.rootPath, i )
      if os.path.isfile( cfg ) and cfg.endswith( '.cfg' ):
        extraCFG.append( cfg )

    if self.pp.executeCmd:
      # Execute user command
      self.log.info( "Executing user defined command: %s" % self.pp.executeCmd )
      self.exitWithError( os.system( "source bashrc; %s" % self.pp.executeCmd ) / 256 )

    self.log.info( 'Starting JobAgent' )
    os.environ['PYTHONUNBUFFERED'] = 'yes'

    pid = {}

    for i in xrange(self.pp.processors):

      # One JobAgent per processor allocated to this pilot

      if self.pp.ceType == 'Sudo':
        # Available within the SudoComputingElement as BaseUsername in the ceParameters
        sudoOpts = '-o /LocalSite/BaseUsername=%s%02dp00' % ( os.environ['USER'], i )
      else:
        sudoOpts = ''

      jobAgent = ('%s WorkloadManagement/JobAgent %s %s %s %s'
                  % ( diracAgentScript,
                      " ".join( self.jobAgentOpts ),
                      " ".join( self.inProcessOpts ),
                      sudoOpts,
                      " ".join( extraCFG )))

      pid[i] = self.forkAndExecute( jobAgent,
                                    os.path.join( self.pp.workingDir, 'jobagent.%02d.log' % i ),
                                    self.pp.installEnv )

      if not pid[i]:
        self.log.error( "Error executing the JobAgent %d" % i )
      else:
        self.log.info( "Forked JobAgent %02d/%d with PID %d" % ( i, self.pp.processors, pid[i] ) )

    # Not very subtle this. How about a time limit??
    for i in xrange(self.pp.processors):
      os.waitpid(pid[i], 0)

    for i in xrange(self.pp.processors):
      shutdownMessage = self.__parseJobAgentLog( os.path.join( self.pp.workingDir, 'jobagent.%02d.log' % i ) )
      open( os.path.join( self.pp.workingDir, 'shutdown_message.%02d' % i ), 'w' ).write( shutdownMessage )
      print shutdownMessage

    # FIX ME: this effectively picks one at random. Should be the last one to finish chronologically.
    # Not in order of being started.
    open( os.path.join( self.pp.workingDir, 'shutdown_message' ), 'w' ).write( shutdownMessage )

    fs = os.statvfs( self.pp.workingDir )
    diskSpace = fs[4] * fs[0] / 1024 / 1024
    self.log.info( 'DiskSpace (MB) = %s' % diskSpace )

  def __parseJobAgentLog(self, logFile):
    """ Parse the JobAgent log and return shutdown message
    """

    # catch-all in case nothing matches
    shutdownMessage = '700 Failed, probably JobAgent or Application problem'

    # log file patterns to look for and corresponding messages
    messageMappings = [

        # Variants of: "100 Shutdown as requested by the VM's host/hypervisor"
        ######################################################################
        # There are other errors from the TimeLeft handling, but we let those go
        # to the 600 Failed default
        ['INFO: JobAgent will stop with message "No time left for slot', '100 No time left for slot'],

        # Variants of: "200 Intended work completed ok"
        ###############################################
        # Our work is done. More work available in the queue? Who knows!
        ['INFO: JobAgent will stop with message "Filling Mode is Disabled', '200 Filling Mode is Disabled'],
        ['NOTICE:  Cycle was successful', '200 Success'],

        #
        # !!! Codes 300-699 trigger Vac/Vcycle backoff procedure !!!
        #

        # Variants of: "300 No more work available from task queue"
        ###########################################################
        # We asked, but nothing more from the matcher.
        ['INFO: JobAgent will stop with message "Nothing to do for more than', '300 Nothing to do'],
        ['Job request OK: No match found', '300 Nothing to do'],

        # Variants of: "400 Site/host/VM is currently banned/disabled from receiving more work"
        #######################################################################################

        # Variants of: "500 Problem detected with environment/VM/contextualization provided by the site"
        ################################################################################################
        # This detects using an RFC proxy to talk to legacy-only DIRAC
        ['Error while handshaking [("Remote certificate hasn', '500 Certificate/proxy not acceptable'],

        # Variants of: "600 Grid-wide problem with job agent or application within VM"
        ##############################################################################
        ['ERROR: Pilot version does not match the production version', '600 Cannot match jobs with this pilot version'],

        # Variants of: "700 Error related to job agent or application within VM"
        ########################################################################
        # Some of the ways the JobAgent/Application can stop with errors.
        # Otherwise we just get the default 700 Failed message.
        ['INFO: JobAgent will stop with message "Job Rescheduled', '600 Problem so job rescheduled'],
        ['INFO: JobAgent will stop with message "Matcher Failed', '600 Matcher Failed'],
        ['INFO: JobAgent will stop with message "JDL Problem', '600 JDL Problem'],
        ['INFO: JobAgent will stop with message "Payload Proxy Not Found', '600 Payload Proxy Not Found'],
        ['INFO: JobAgent will stop with message "Problem Rescheduling Job', '600 Problem Rescheduling Job'],
        ['INFO: JobAgent will stop with message "Payload execution failed with error code', '600 Payload execution failed with error'],

    ]

    try:
      f = open(logFile, 'r')
    except:
      return '700 Internal VM logging failed'

    oneline = f.readline()

    while oneline:

      for pair in messageMappings:
        if pair[0] in oneline:
           shutdownMessage = pair[1]
           break

      oneline = f.readline()

    f.close()

    return shutdownMessage

  def execute( self ):
    """ What is called all the time
    """
    self.__setInProcessOpts()
    self.__startJobAgent()

    sys.exit( 0 )

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
      self.nagiosProbes = [str( pv ).strip() for pv in self.pp.pilotJSON['Setups'][self.pp.setup]['NagiosProbes'].split(',')]
    except KeyError:
      try:
        self.nagiosProbes = [str( pv ).strip() for pv in self.pp.pilotJSON['Setups']['Defaults']['NagiosProbes'].split(',')]
      except KeyError:
        pass

    try:
      self.nagiosPutURL = str( self.pp.pilotJSON['Setups'][self.pp.setup]['NagiosPutURL'] )
    except KeyError:
      try:
        self.nagiosPutURL = str( self.pp.pilotJSON['Setups']['Defaults']['NagiosPutURL'] )
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
        retStatus = 'info'
      elif retCode == 1:
        self.log.warn( 'Return code = 1: %s' % output.split('\n',1)[0] )
        retStatus = 'warning'
      else:
        # retCode could be 2 (error) or 3 (unknown) or something we haven't thought of
        self.log.error( 'Return code = %d: %s' % ( retCode, output.split('\n',1)[0] ) )
        retStatus = 'error'

      # report results to pilot logger too. Like this:
      #   "NagiosProbes", probeCmd, retStatus, str(retCode) + ' ' + output.split('\n',1)[0]

      if self.nagiosPutURL:
        # Alternate logging of results to HTTPS PUT service too
        hostPort = self.nagiosPutURL.split('/')[2]
        path = '/' + '/'.join( self.nagiosPutURL.split('/')[3:] ) + self.pp.ceName + '/' + probeCmd

        self.log.info( 'Putting %s Nagios output to https://%s%s' % ( probeCmd, hostPort, path ) )

        try:
          connection = httplib.HTTPSConnection( host      = hostPort,
                                                timeout   = 30,
                                                key_file  = os.environ['X509_USER_PROXY'],
                                                cert_file = os.environ['X509_USER_PROXY'] )

          connection.request( 'PUT', path, str(retCode) + ' ' + str( int( time.time() ) ) + '\n' + output )

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

