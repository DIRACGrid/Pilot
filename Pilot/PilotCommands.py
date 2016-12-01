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
import stat
import socket

from Pilot.PilotTools import CommandBase

__RCSID__ = "$Id$"

class GetPilotVersion( CommandBase ):
  """ Now just return what was obtained by PilotTools.py
  """

  def __init__( self, pilotParams):
    """ c'tor
    """
    super( GetPilotVersion, self ).__init__( pilotParams)

  def getPilotVersion(self):
    """Return the pilot version """
    return self.pilotParams.releaseVersion

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
    self.log.info( 'WorkingDir = %s' % self.pilotParams.workingDir ,True, True)  # this could be different than rootPath

    fileName = '/etc/redhat-release'
    if os.path.exists( fileName ):
      fFile = open( fileName, 'r' )
      self.log.info( 'RedHat Release = %s' % fFile.read().strip() )
      fFile.close()

    fileName = '/etc/lsb-release'
    if os.path.isfile( fileName ):
      fFile = open( fileName, 'r' )
      self.log.info( 'Linux release:\n%s' % fFile.read().strip() )
      fFile.close()

    fileName = '/proc/cpuinfo'
    if os.path.exists( fileName ):
      fFile = open( fileName, 'r' )
      cpu = fFile.readlines()
      fFile.close()
      nCPU = 0
      for line in cpu:
        if line.find( 'cpu MHz' ) == 0:
          nCPU += 1
          freq = line.split()[3]
        elif line.find( 'model name' ) == 0:
          cpuModel = line.split( ': ' )[1].strip()
      self.log.info( 'CPU (model)    = %s' % cpuModel )
      self.log.info( 'CPU (MHz)      = %s x %s' % ( nCPU, freq ) )

    fileName = '/proc/meminfo'
    if os.path.exists( fileName ):
      fFile = open( fileName, 'r' )
      mem = fFile.readlines()
      fFile.close()
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

    ##############################################################################################################################
    # Disk space check

    # fs = os.statvfs( rootPath )
    fs = os.statvfs( self.pilotParams.workingDir )
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

    if diskSpace < self.pilotParams.minDiskSpace:
      self.log.error( '%s MB < %s MB, not enough local disk space available, exiting'
                      % ( diskSpace, self.pilotParams.minDiskSpace ) )
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
    self.pilotParams.rootPath = self.pilotParams.pilotRootPath
    self.installScriptName = 'dirac-install.py'
    self.installScript = ''

  def _appendOptionToInstallOption(self, optionValues, defaultoptionValue, setValue=False, specialField=None, both=False):
    """ Append an option to the configuration from the PilotPramas"""
    for option, value in self.pilotParams.optList:
      if option in optionValues:
        if specialField:
          setattr(self.pilotParams, specialField, value)
          if not both:
            continue
        if setValue:
          self.installOpts.append( '%s "%s"' % (defaultoptionValue,value))
          continue
        self.installOpts.append( '%s' % (defaultoptionValue))
        break

  def _setInstallOptions( self ):
    """ Setup installation parameters
    """
    self._appendOptionToInstallOption(['-b','--build'], '-b')
    self._appendOptionToInstallOption(['-d','--debug'], '-d')
    self._appendOptionToInstallOption(['-e','--extraPackages'], '-e', setValue=True)
    self._appendOptionToInstallOption(['-g','--grid'], '', specialField='gridVersion')
    self._appendOptionToInstallOption(['-i','--python'], '', specialField='pythonVersion')
    self._appendOptionToInstallOption(['-p','--platform'], '', specialField='platform')
    self._appendOptionToInstallOption(['-u','--url'], '-u', setValue=True)
    self._appendOptionToInstallOption(['-P','--path'], '-P', setValue=True, specialField='rootPath', both=True)
    self._appendOptionToInstallOption(['-V','--installation'], '-V', setValue=True)
    self._appendOptionToInstallOption(['-t','--server'], '-t "server"')

    if self.pilotParams.gridVersion:
      self.installOpts.append( "-g '%s'" % self.pilotParams.gridVersion )
    if self.pilotParams.pythonVersion:
      self.installOpts.append( "-i '%s'" % self.pilotParams.pythonVersion )
    if self.pilotParams.platform:
      self.installOpts.append( '-p "%s"' % self.pilotParams.platform )
    if self.pilotParams.releaseProject:
      self.installOpts.append( "-l '%s'" % self.pilotParams.releaseProject )

    # The release version to install is a requirement
    self.installOpts.append( '-r "%s"' % self.pilotParams.releaseVersion )

    self.log.debug( 'INSTALL OPTIONS [%s]' % ', '.join( map( str, self.installOpts ) ) )

  def _locateInstallationScript( self ):
    """ Locate installation script
    """
    installScript = ''
    for path in ( self.pilotParams.pilotRootPath, self.pilotParams.originalRootPath, self.pilotParams.rootPath ):
      installScript = os.path.join( path, self.installScriptName )
      if os.path.isfile( installScript ):
        break
    self.installScript = installScript

    if not os.path.isfile( installScript ):
      self.log.error( "%s requires %s to exist in one of: %s, %s, %s" % ( self.pilotParams.pilotScriptName,
                                                                          self.installScriptName,
                                                                          self.pilotParams.pilotRootPath,
                                                                          self.pilotParams.originalRootPath,
                                                                          self.pilotParams.rootPath ) )
      sys.exit( 1 )

    try:
      # change permission of the script
      os.chmod( self.installScript, stat.S_IRWXU )
    except OSError:
      pass

  def _installDIRAC( self ):
    """ launch the installation script
    """
    installCmd = "%s %s" % ( self.installScript, " ".join( self.installOpts ) )
    self.log.debug( "Installing with: %s" % installCmd )

    retCode, output = self.executeAndGetOutput( installCmd )
    self.log.info( output, header = False )

    if retCode:
      self.log.error( "Could not make a proper DIRAC installation [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    self.log.info( "%s completed successfully" % self.installScriptName )

    diracScriptsPath = os.path.join( self.pilotParams.rootPath, 'scripts' )
    platformScript = os.path.join( diracScriptsPath, "dirac-platform" )
    if not self.pilotParams.platform:
      retCode, output = self.executeAndGetOutput( platformScript )
      if retCode:
        self.log.error( "Failed to determine DIRAC platform [ERROR %d]" % retCode )
        self.exitWithError( retCode )
      self.pilotParams.platform = output
    diracBinPath = os.path.join( self.pilotParams.rootPath, self.pilotParams.platform, 'bin' )
    diracLibPath = os.path.join( self.pilotParams.rootPath, self.pilotParams.platform, 'lib' )

    for envVarName in ( 'LD_LIBRARY_PATH', 'PYTHONPATH' ):
      if envVarName in os.environ:
        os.environ[ '%s_SAVE' % envVarName ] = os.environ[ envVarName ]
        del os.environ[ envVarName ]
      else:
        os.environ[ '%s_SAVE' % envVarName ] = ""

    os.environ['LD_LIBRARY_PATH'] = "%s" % ( diracLibPath )
    sys.path.insert( 0, self.pilotParams.rootPath )
    sys.path.insert( 0, diracScriptsPath )
    if "PATH" in os.environ:
      os.environ['PATH'] = '%s:%s:%s' % ( diracBinPath, diracScriptsPath, os.getenv( 'PATH' ) )
    else:
      os.environ['PATH'] = '%s:%s' % ( diracBinPath, diracScriptsPath )
    self.pilotParams.diracInstalled = True

  def execute( self ):
    """ What is called all the time
    """
    self._setInstallOptions()
    self._locateInstallationScript()
    self._installDIRAC()



class ConfigureBasics( CommandBase ):
  """ This command completes DIRAC installation, e.g. calls dirac-configure to:
      - download, by default, the CAs
      - creates a standard or custom (defined by self.pilotParams.localConfigFile) cfg file
        to be used where all the pilot configuration is to be set, e.g.:
      - adds to it basic info like the version
      - adds to it the security configuration

      If there is more than one command calling dirac-configure, this one should be always the first one called.

      Nota Bene: Further commands should always call dirac-configure using the options -FDMH
      Nota Bene: If custom cfg file is created further commands should call dirac-configure with
                 "-O %s %s" % ( self.pilotParams.localConfigFile, self.pilotParams.localConfigFile )

      From here on, we have to pay attention to the paths. Specifically, we need to know where to look for
      - executables (scripts)
      - DIRAC python code
      If the pilot has installed DIRAC (and extensions) in the traditional way, so using the dirac-install.py script,
      simply the current directory is used, and:
      - scripts will be in $CWD/scripts.
      - DIRAC python code will be all sitting in $CWD
      - the local dirac.cfg file will be found in $CWD/etc

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

    if self.pilotParams.debugFlag:
      self.cfg.append( '-ddd' )
    if self.pilotParams.localConfigFile:
      self.cfg.append( '-O %s' % self.pilotParams.localConfigFile )

    configureCmd = "%s %s" % ( self.pilotParams.configureScript, " ".join( self.cfg ) )

    retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pilotParams.installEnv )

    if retCode:
      self.log.error( "Could not configure DIRAC basics [ERROR %d]" % retCode )
      self.exitWithError( retCode )

  def _getBasicsCFG( self ):
    """  basics (needed!)
    """
    self.cfg.append( '-S "%s"' % self.pilotParams.setup )
    if self.pilotParams.configServer:
      self.cfg.append( '-C "%s"' % self.pilotParams.configServer )
    if self.pilotParams.releaseProject:
      self.cfg.append( '-o /LocalSite/ReleaseProject=%s' % self.pilotParams.releaseProject )
    if self.pilotParams.gateway:
      self.cfg.append( '-W "%s"' % self.pilotParams.gateway )
    if self.pilotParams.userGroup:
      self.cfg.append( '-o /AgentJobRequirements/OwnerGroup="%s"' % self.pilotParams.userGroup )
    if self.pilotParams.userDN:
      self.cfg.append( '-o /AgentJobRequirements/OwnerDN="%s"' % self.pilotParams.userDN )
    self.cfg.append( '-o /LocalSite/ReleaseVersion=%s' % self.pilotParams.releaseVersion )

  def _getSecurityCFG( self ):
    """ Nothing specific by default, but need to know host cert and key location in case they are needed
    """
    if self.pilotParams.useServerCertificate:
      self.cfg.append( '--UseServerCertificate' )
      self.cfg.append( "-o /DIRAC/Security/CertFile=%s/hostcert.pem" % self.pilotParams.certsLocation )
      self.cfg.append( "-o /DIRAC/Security/KeyFile=%s/hostkey.pem" % self.pilotParams.certsLocation )

class CheckCECapabilities( CommandBase ):
  """ Used to get  CE tags.
  """
  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( CheckCECapabilities, self ).__init__( pilotParams )

    # this variable contains the options that are passed to dirac-configure, and that will fill the local dirac.cfg file
    self.cfg = []

  def execute( self ):
    """ Setup CE/Queue Tags
    """

    if self.pilotParams.useServerCertificate:
      self.cfg.append( '-o  /DIRAC/Security/UseServerCertificate=yes' )
    if self.pilotParams.localConfigFile:
      self.cfg.append( self.pilotParams.localConfigFile )  # this file is as input


    checkCmd = 'dirac-resource-get-parameters -S %s -N %s -Q %s %s' % ( self.pilotParams.site,
                                                                        self.pilotParams.ceName,
                                                                        self.pilotParams.queueName,
                                                                        " ".join( self.cfg ) )
    retCode, resourceDict = self.executeAndGetOutput( checkCmd, self.pilotParams.installEnv )
    if retCode:
      self.log.error( "Could not get resource parameters [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    try:
      import json
      resourceDict = json.loads( resourceDict )
    except ValueError:
      self.log.error( "The pilot command output is not json compatible." )
      sys.exit( 1 )
    if resourceDict.get( 'Tag' ):
      self.pilotParams.tags += resourceDict['Tag']
      self.cfg.append( '-FDMH' )

      if self.pilotParams.useServerCertificate:
        self.cfg.append( '-o  /DIRAC/Security/UseServerCertificate=yes' )

      if self.pilotParams.localConfigFile:
        self.cfg.append( '-O %s' % self.pilotParams.localConfigFile )  # this file is as output
        self.cfg.append( self.pilotParams.localConfigFile )  # this file is as input

      if self.debugFlag:
        self.cfg.append( '-ddd' )

      self.cfg.append( '-o "/Resources/Computing/CEDefaults/Tag=%s"' % ','.join( ( str( x ) for x in self.pilotParams.tags ) ) )

      configureCmd = "%s %s" % ( self.pilotParams.configureScript, " ".join( self.cfg ) )
      retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pilotParams.installEnv )
      if retCode:
        self.log.error( "Could not configure DIRAC [ERROR %d]" % retCode )
        self.exitWithError( retCode )

class CheckWNCapabilities( CommandBase ):
  """ Used to get capabilities specific to the Worker Node.
  """

  def __init__( self, pilotParams ):
    """ c'tor
    """
    super( CheckWNCapabilities, self ).__init__( pilotParams )
    self.cfg = []

  def execute( self ): #pylint: disable=R0912
    """ Discover #Processors and memory
    """

    if self.pilotParams.useServerCertificate:
      self.cfg.append( '-o /DIRAC/Security/UseServerCertificate=yes' )
    if self.pilotParams.localConfigFile:
      self.cfg.append( self.pilotParams.localConfigFile )  # this file is as input

    checkCmd = 'dirac-wms-get-wn-parameters -S %s -N %s -Q %s %s' % ( self.pilotParams.site,
                                                                      self.pilotParams.ceName,
                                                                      self.pilotParams.queueName,
                                                                      " ".join( self.cfg ) )
    retCode, result = self.executeAndGetOutput( checkCmd, self.pilotParams.installEnv )
    if retCode:
      self.log.error( "Could not get resource parameters [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    try:
      result = result.split( ' ' )
      numberOfProcessor = int( result[0] )
      maxRAM = int( result[1] )
    except ValueError:
      self.log.error( "Wrong Command output %s" % result )
      sys.exit( 1 )
    if numberOfProcessor or maxRAM:
      self.cfg.append( '-FDMH' )

      if self.pilotParams.useServerCertificate:
        self.cfg.append( '-o /DIRAC/Security/UseServerCertificate=yes' )
      if self.pilotParams.localConfigFile:
        self.cfg.append( '-O %s' % self.pilotParams.localConfigFile )  # this file is as output
        self.cfg.append( self.pilotParams.localConfigFile )  # this file is as input

      if self.debugFlag:
        self.cfg.append( '-ddd' )

      if numberOfProcessor:
        self.cfg.append( '-o "/Resources/Computing/CEDefaults/NumberOfProcessors=%d"' % numberOfProcessor )
      else:
        self.log.warn( "Could not retrieve number of processors" )
      if maxRAM:
        self.cfg.append( '-o "/Resources/Computing/CEDefaults/MaxRAM=%d"' % maxRAM )
      else:
        self.log.warn( "Could not retrieve MaxRAM" )
      configureCmd = "%s %s" % ( self.pilotParams.configureScript, " ".join( self.cfg ) )
      retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pilotParams.installEnv )
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

  def _appendOptionToCfg(self, optionValues, defaultoptionValue):
    """ Append an option to the configuration from the PilotPramas"""
    for option, value in self.pilotParams.optList:
      if option in optionValues:
        self.cfg.append( '%s "%s"' % (defaultoptionValue,value))
        break

  def execute( self ):
    """ Setup configuration parameters
    """
    self.__setFlavour()
    self.cfg.append( '-o /LocalSite/GridMiddleware=%s' % self.pilotParams.flavour )

    self.cfg.append( '-n "%s"' % self.pilotParams.site )
    self.cfg.append( '-S "%s"' % self.pilotParams.setup )

    if not self.pilotParams.ceName or not self.pilotParams.queueName:
      self.__getCEName()
    self.cfg.append( '-N "%s"' % self.pilotParams.ceName )
    self.cfg.append( '-o /LocalSite/GridCE=%s' % self.pilotParams.ceName )
    self.cfg.append( '-o /LocalSite/CEQueue=%s' % self.pilotParams.queueName )
    if self.pilotParams.ceType:
      self.cfg.append( '-o /LocalSite/LocalCE=%s' % self.pilotParams.ceType )

    self._appendOptionToCfg(['-o','--option'], '-o')
    self._appendOptionToCfg(['-s','--section'], '-s')


    if self.pilotParams.pilotReference != 'Unknown':
      self.cfg.append( '-o /LocalSite/PilotReference=%s' % self.pilotParams.pilotReference )
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

    if self.pilotParams.useServerCertificate:
      self.cfg.append( '--UseServerCertificate' )
      self.cfg.append( "-o /DIRAC/Security/CertFile=%s/hostcert.pem" % self.pilotParams.certsLocation )
      self.cfg.append( "-o /DIRAC/Security/KeyFile=%s/hostkey.pem" % self.pilotParams.certsLocation )

    # these are needed as this is not the fist time we call dirac-configure
    self.cfg.append( '-FDMH' )
    if self.pilotParams.localConfigFile:
      self.cfg.append( '-O %s' % self.pilotParams.localConfigFile )
      self.cfg.append( self.pilotParams.localConfigFile )

    if self.debugFlag:
      self.cfg.append( '-ddd' )

    configureCmd = "%s %s" % ( self.pilotParams.configureScript, " ".join( self.cfg ) )

    retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pilotParams.installEnv )

    if retCode:
      self.log.error( "Could not configure DIRAC [ERROR %d]" % retCode )
      self.exitWithError( retCode )

  def _specialFlavor_GLITE_WMS_JOBID(self):
    """ Special flavor dict function"""
    if os.environ['GLITE_WMS_JOBID'] != 'N/A':
      self.pilotParams.flavour = 'gLite'
      return os.environ['GLITE_WMS_JOBID']

  def _specialFlavor_OSG_WN_TMP(self):
    """ Special flavor dict function"""
    self.pilotParams.flavour = 'OSG'
    return None

  def _specialFlavor_BOINC_JOB_ID(self):
    """ Special flavor dict function"""
    # This is for BOINC case
    self.pilotParams.flavour = 'BOINC'
    if 'BOINC_USER_ID' in os.environ:
      self.boincUserID = os.environ['BOINC_USER_ID']
    if 'BOINC_HOST_ID' in os.environ:
      self.boincHostID = os.environ['BOINC_HOST_ID']
    if 'BOINC_HOST_PLATFORM' in os.environ:
      self.boincHostPlatform = os.environ['BOINC_HOST_PLATFORM']
    if 'BOINC_HOST_NAME' in os.environ:
      self.boincHostName = os.environ['BOINC_HOST_NAME']
    return os.environ['BOINC_JOB_ID']

  flavors = [
      {'key':'PBS_JOBID',
       'pilotRefPrefix':'sshtorque',
       'specialParsing':lambda s: s.split('.')[0],
       'flavor': 'SSHTorque'
      },
      {'key':'OAR_JOBID',
       'pilotRefPrefix':'sshoar',
       'flavor': 'SSHOAR'
      },
      {'key':'JOB_ID',
       'pilotRefPrefix':'sshge',
       'flavor': 'SSHGE',
       'dependsOn':'SGE_TASK_ID',
       'pilotRefPrefixMissingDep':'generic',
       'flavorMissingDep':'Generic'
      },
      {'key':'CONDOR_JOBID',
       'pilotRefPrefix':'sshcondor',
       'flavor': 'SSHCondor',
      },
      {'key':'HTCONDOR_JOBID',
       'pilotRefPrefix':'htcondorce',
       'flavor': 'HTCondorCE',
      },
      {'key':'LSB_BATCH_JID',
       'pilotRefPrefix':'sshlsf',
       'flavor': 'SSHLSF',
      },
      {'key':'SLURM_JOBID',
       'pilotRefPrefix':'sshslurm',
       'flavor': 'SSHSLURM',
      },
      {'key':'CREAM_JOBID',
       'flavor': 'CREAM',
      },
      {'key':'EDG_WL_JOBID',
       'flavor': 'LCG',
      },
      {'key':'GLITE_WMS_JOBID',
       'specialFunction': _specialFlavor_GLITE_WMS_JOBID,
      },
      {'key':'OSG_WN_TMP',
       'specialFunction': _specialFlavor_OSG_WN_TMP,
      },
      {'key':'GLOBUS_GRAM_JOB_CONTACT',
       'flavor': 'GLOBUS',
      },
      {'key':'SSHCE_JOBID',
       'pilotRefPrefix':'ssh',
       'flavor': 'SSH',
      },
      {'key':'GRID_GLOBAL_JOBID',
       'flavor': 'ARC',
      },
      {'key':'VMDIRAC_VERSION',
       'pilotRefPrefix':'vm',
       'flavor': 'VMDIRAC',
      },
      {'key':'BOINC_JOB_ID',
       'specialFunction': _specialFlavor_BOINC_JOB_ID,
      }]

  def __setFlavour( self ):
    """
    Set the flavour
    """
    pilotRef = 'Unknown'

    # Pilot reference is specified at submission
    if self.pilotParams.pilotReference:
      self.pilotParams.flavour = 'DIRAC'
      pilotRef = self.pilotParams.pilotReference

    for flavor in self.flavors:
      if flavor['key'] in os.environ:
        if flavor.get('specialFunction', None):
          tmp_return = getattr(self, flavor.get('specialFunction'))()
          pilotRef = tmp_return if tmp_return else pilotRef
          continue
        # Defualt special parssing is to return the value itself
        special_parsing = flavor.get('specialParsing') if flavor.get('specialParsing', None) else lambda x: x
        self.pilotParams.flavour = flavor.get('flavor')
        if flavor.get('pilotRefPrefix',None):
          pilotRef = flavor.get('pilotRefPrefix') + '//' +  self.pilotParams.ceName + '/' +  special_parsing(os.environ[flavor['key']])
        else:
          pilotRef = os.environ[flavor['key']]
        if flavor.get('dependsOn',None):
          if not flavor.get('dependsOn',None) in os.environ:
            self.pilotParams.flavour = flavor.get('flavorMissingDep')
            pilotRef = "%s//%s/%s" % (flavor.get('pilotRefPrefixMissingDep'),
                                      self.pilotParams.ceName,
                                      special_parsing(os.environ[flavor['key']]))

    self.log.debug( "Flavour: %s; pilot reference: %s " % ( self.pilotParams.flavour, pilotRef ) )

    self.pilotParams.pilotReference = pilotRef

  def __LCGgLiteOSGFlavor(self):
    """ Gets the flavor for LCG, gLite or OSG"""
    retCode, ceName = self.executeAndGetOutput('glite-brokerinfo getCE',
                                               self.pilotParams.installEnv )
    if retCode:
      self.log.warn( "Could not get CE name with 'glite-brokerinfo getCE' command [ERROR %d]" % retCode )
      if 'OSG_JOB_CONTACT' in os.environ:
        # OSG_JOB_CONTACT String specifying the endpoint to use within the job submission
        #                 for reaching the site (e.g. manager.mycluster.edu/jobmanager-pbs )
        ce = os.environ['OSG_JOB_CONTACT']
        self.pilotParams.ceName = ce.split( '/' )[0]
        if len( ce.split( '/' ) ) > 1:
          self.pilotParams.queueName = ce.split( '/' )[1]
        else:
          self.log.error( "CE Name %s not accepted" % ce )
          self.exitWithError( retCode )
      else:
        self.log.info( "Looking if queue name is already present in local cfg" )
        from DIRAC import gConfig # pylint: disable=E0401
        ceName = gConfig.getValue( 'LocalSite/GridCE', '' )
        ceQueue = gConfig.getValue( 'LocalSite/CEQueue', '' )
        if ceName and ceQueue:
          self.log.debug( "Found CE %s, queue %s" % ( ceName, ceQueue ) )
          self.pilotParams.ceName = ceName
          self.pilotParams.queueName = ceQueue
        else:
          self.log.error( "Can't find ceName nor queue... have to fail!" )
          sys.exit( 1 )
    else:
      self.log.debug( "Found CE %s" % ceName )
      self.pilotParams.ceName = ceName.split( ':' )[0]
      if len( ceName.split( '/' ) ) > 1:
        self.pilotParams.queueName = ceName.split( '/' )[1]
    # configureOpts.append( '-N "%s"' % cliParams.ceName )

  def __getCREAMFlavor(self):
    """ Gets the CREAM flavor """
    if 'CE_ID' in os.environ:
      self.log.debug( "Found CE %s" % os.environ['CE_ID'] )
      self.pilotParams.ceName = os.environ['CE_ID'].split( ':' )[0]
      if os.environ['CE_ID'].count( "/" ):
        self.pilotParams.queueName = os.environ['CE_ID'].split( '/' )[1]
      else:
        self.log.error( "Can't find queue name" )
        sys.exit( 1 )
    else:
      self.log.error( "Can't find CE name" )
      sys.exit( 1 )

  def __getCEName( self ):
    """ Try to get the CE name
    """
    # FIXME: this should not be part of the standard configuration (flavours discriminations should stay out)
    if self.pilotParams.flavour in ['LCG', 'gLite', 'OSG']:
      self.__LCGgLiteOSGFlavor()
    elif self.pilotParams.flavour == "CREAM":
      self.__getCREAMFlavor()


class ConfigureArchitecture( CommandBase ):
  """ This command simply calls dirac-platfom to determine the platform.
      Separated from the ConfigureDIRAC command for easier extensibility.
  """

  def execute( self ):
    """ This is a simple command to call the dirac-platform utility to get the platform, and add it to the configuration

        The architecture script, as well as its options can be replaced in a pilot extension
    """

    cfg = []
    if self.pilotParams.useServerCertificate:
      cfg.append( '-o  /DIRAC/Security/UseServerCertificate=yes' )
    if self.pilotParams.localConfigFile:
      cfg.append( self.pilotParams.localConfigFile )  # this file is as input

    architectureCmd = "%s %s" % ( self.pilotParams.architectureScript, " ".join( cfg ) )

    retCode, localArchitecture = self.executeAndGetOutput( architectureCmd, self.pilotParams.installEnv )
    if retCode:
      self.log.error( "There was an error updating the platform [ERROR %d]" % retCode )
      self.exitWithError( retCode )
    self.log.debug( "Architecture determined: %s" % localArchitecture )

    # standard options
    cfg = ['-FDMH']  # force update, skip CA checks, skip CA download, skip VOMS
    if self.pilotParams.useServerCertificate:
      cfg.append( '--UseServerCertificate' )
    if self.pilotParams.localConfigFile:
      cfg.append( '-O %s' % self.pilotParams.localConfigFile )  # our target file for pilots
      cfg.append( self.pilotParams.localConfigFile )  # this file is also an input
    if self.pilotParams.debugFlag:
      cfg.append( "-ddd" )

    # real options added here
    localArchitecture = localArchitecture.strip()
    cfg.append( '-S "%s"' % self.pilotParams.setup )
    cfg.append( '-o /LocalSite/Architecture=%s' % localArchitecture )

    configureCmd = "%s %s" % ( self.pilotParams.configureScript, " ".join( cfg ) )
    retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pilotParams.installEnv )
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
    if self.pilotParams.useServerCertificate:
      configFileArg = '-o /DIRAC/Security/UseServerCertificate=yes'
    if self.pilotParams.localConfigFile:
      configFileArg = '%s -R %s %s' % ( configFileArg, self.pilotParams.localConfigFile, self.pilotParams.localConfigFile )
    retCode, cpuNormalizationFactorOutput = self.executeAndGetOutput( 'dirac-wms-cpu-normalization -U %s' % configFileArg,
                                                                      self.pilotParams.installEnv )
    if retCode:
      self.log.error( "Failed to determine cpu normalization [ERROR %d]" % retCode )
      self.exitWithError( retCode )

    # HS06 benchmark
    # FIXME: this is a (necessary) hack!
    cpuNormalizationFactor = float( cpuNormalizationFactorOutput.split( '\n' )[0].replace( "Estimated CPU power is ",
                                                                                           '' ).replace( " HS06", '' ) )
    self.log.info( "Current normalized CPU as determined by 'dirac-wms-cpu-normalization' is %f" % cpuNormalizationFactor )

    configFileArg = ''
    if self.pilotParams.useServerCertificate:
      configFileArg = '-o /DIRAC/Security/UseServerCertificate=yes'
    retCode, cpuTimeOutput = self.executeAndGetOutput( 'dirac-wms-get-queue-cpu-time %s %s' % ( configFileArg,
                                                                                                self.pilotParams.localConfigFile ),
                                                       self.pilotParams.installEnv )

    if retCode:
      self.log.error( "Failed to determine cpu time left in the queue [ERROR %d]" % retCode )
      self.exitWithError( retCode )

    for line in cpuTimeOutput.split( '\n' ):
      if "CPU time left determined as" in line:
        cpuTime = int(line.replace("CPU time left determined as", '').strip())
    self.log.info( "CPUTime left (in seconds) is %s" % cpuTime )

    # HS06s = seconds * HS06
    try:
      self.pilotParams.jobCPUReq = float( cpuTime ) * float( cpuNormalizationFactor )
      self.log.info( "Queue length (which is also set as CPUTimeLeft) is %f" % self.pilotParams.jobCPUReq )
    except ValueError:
      self.log.error( 'Pilot command output does not have the correct format' )
      sys.exit( 1 )
    # now setting this value in local file
    cfg = ['-FDMH']
    if self.pilotParams.useServerCertificate:
      cfg.append( '-o  /DIRAC/Security/UseServerCertificate=yes' )
    if self.pilotParams.localConfigFile:
      cfg.append( '-O %s' % self.pilotParams.localConfigFile )  # our target file for pilots
      cfg.append( self.pilotParams.localConfigFile )  # this file is also input
    cfg.append( '-o /LocalSite/CPUTimeLeft=%s' % str( int( self.pilotParams.jobCPUReq ) ) )  # the only real option

    configureCmd = "%s %s" % ( self.pilotParams.configureScript, " ".join( cfg ) )
    retCode, _configureOutData = self.executeAndGetOutput( configureCmd, self.pilotParams.installEnv )
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
    """
    Sets in process options
    """
    localUid = os.getuid()
    try:
      import pwd
      localUser = pwd.getpwuid( localUid )[0]
    except KeyError:
      localUser = 'Unknown'
    self.log.info( 'User Name  = %s' % localUser )
    self.log.info( 'User Id    = %s' % localUid )
    self.inProcessOpts = ['-s /Resources/Computing/CEDefaults' ]
    self.inProcessOpts.append( '-o WorkingDirectory=%s' % self.pilotParams.workingDir )
    # FIXME: this is artificial
    self.inProcessOpts.append( '-o TotalCPUs=%s' % 1 )
    self.inProcessOpts.append( '-o /LocalSite/MaxCPUTime=%s' % ( int( self.pilotParams.jobCPUReq ) ) )
    self.inProcessOpts.append( '-o /LocalSite/CPUTime=%s' % ( int( self.pilotParams.jobCPUReq ) ) )
    self.inProcessOpts.append( '-o MaxRunningJobs=%s' % 1 )
    # To prevent a wayward agent picking up and failing many jobs.
    self.inProcessOpts.append( '-o MaxTotalJobs=%s' % 10 )
    self.jobAgentOpts = ['-o MaxCycles=%s' % self.pilotParams.maxCycles]

    if self.debugFlag:
      self.jobAgentOpts.append( '-o LogLevel=DEBUG' )

    if self.pilotParams.userGroup:
      self.log.debug( 'Setting DIRAC Group to "%s"' % self.pilotParams.userGroup )
      self.inProcessOpts .append( '-o OwnerGroup="%s"' % self.pilotParams.userGroup )

    if self.pilotParams.userDN:
      self.log.debug( 'Setting Owner DN to "%s"' % self.pilotParams.userDN )
      self.inProcessOpts.append( '-o OwnerDN="%s"' % self.pilotParams.userDN )

    if self.pilotParams.useServerCertificate:
      self.log.debug( 'Setting UseServerCertificate flag' )
      self.inProcessOpts.append( '-o /DIRAC/Security/UseServerCertificate=yes' )

    # The instancePath is where the agent works
    self.inProcessOpts.append( '-o /LocalSite/InstancePath=%s' % self.pilotParams.workingDir )

    # The file pilot.cfg has to be created previously by ConfigureDIRAC
    if self.pilotParams.localConfigFile:
      self.inProcessOpts.append( ' -o /AgentJobRequirements/ExtraOptions=%s' % self.pilotParams.localConfigFile )
      self.inProcessOpts.append( self.pilotParams.localConfigFile )


  def __startJobAgent( self ):
    """ Starting of the JobAgent
    """

    # Find any .cfg file uploaded with the sandbox or generated by previous commands

    diracAgentScript = "dirac-agent"
    extraCFG = []
    for i in os.listdir( self.pilotParams.rootPath ):
      cfg = os.path.join( self.pilotParams.rootPath, i )
      if os.path.isfile( cfg ) and cfg.endswith( '.cfg' ):
        extraCFG.append( cfg )

    if self.pilotParams.executeCmd:
      # Execute user command
      self.log.info( "Executing user defined command: %s" % self.pilotParams.executeCmd )
      self.exitWithError( os.system( "source bashrc; %s" % self.pilotParams.executeCmd ) / 256 )

    self.log.info( 'Starting JobAgent' )
    os.environ['PYTHONUNBUFFERED'] = 'yes'

    jobAgent = '%s WorkloadManagement/JobAgent %s %s %s' % ( diracAgentScript,
                                                             " ".join( self.jobAgentOpts ),
                                                             " ".join( self.inProcessOpts ),
                                                             " ".join( extraCFG ) )


    retCode, _output = self.executeAndGetOutput( jobAgent, self.pilotParams.installEnv )
    if retCode:
      self.log.error( "Error executing the JobAgent [ERROR %d]" % retCode )
      self.exitWithError( retCode )

    fs = os.statvfs( self.pilotParams.workingDir )
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
    """
    Sets the process options
    """
    localUid = os.getuid()
    try:
      import pwd
      localUser = pwd.getpwuid( localUid )[0]
    except KeyError:
      localUser = 'Unknown'
    self.log.info( 'User Name  = %s' % localUser )
    self.log.info( 'User Id    = %s' % localUid )
    self.inProcessOpts = ['-s /Resources/Computing/CEDefaults' ]
    self.inProcessOpts.append( '-o WorkingDirectory=%s' % self.pilotParams.workingDir )
    self.inProcessOpts.append( '-o /LocalSite/MaxCPUTime=%s' % ( int( self.pilotParams.jobCPUReq ) ) )
    self.inProcessOpts.append( '-o /LocalSite/CPUTime=%s' % ( int( self.pilotParams.jobCPUReq ) ) )
    # To prevent a wayward agent picking up and failing many jobs.
    self.inProcessOpts.append( '-o MaxTotalJobs=%s' % self.pilotParams.maxCycles )
    self.jobAgentOpts= [ '-o MaxCycles=%s' % self.pilotParams.maxCycles,
                         '-o StopAfterFailedMatches=0' ]

    if self.debugFlag:
      self.jobAgentOpts.append( '-o LogLevel=DEBUG' )

    if self.pilotParams.userGroup:
      self.log.debug( 'Setting DIRAC Group to "%s"' % self.pilotParams.userGroup )
      self.inProcessOpts .append( '-o OwnerGroup="%s"' % self.pilotParams.userGroup )

    if self.pilotParams.userDN:
      self.log.debug( 'Setting Owner DN to "%s"' % self.pilotParams.userDN )
      self.inProcessOpts.append( '-o OwnerDN="%s"' % self.pilotParams.userDN )

    if self.pilotParams.useServerCertificate:
      self.log.debug( 'Setting UseServerCertificate flag' )
      self.inProcessOpts.append( '-o /DIRAC/Security/UseServerCertificate=yes' )

    # The instancePath is where the agent works
    self.inProcessOpts.append( '-o /LocalSite/InstancePath=%s' % self.pilotParams.workingDir )

    # The file pilot.cfg has to be created previously by ConfigureDIRAC
    if self.pilotParams.localConfigFile:
      self.inProcessOpts.append( ' -o /AgentJobRequirements/ExtraOptions=%s' % self.pilotParams.localConfigFile )
      self.inProcessOpts.append( self.pilotParams.localConfigFile )


  def __startJobAgent(self):
    """ Starting of the JobAgent
    """

    # Find any .cfg file uploaded with the sandbox or generated by previous commands

    diracAgentScript = "dirac-agent"
    extraCFG = []
    for i in os.listdir( self.pilotParams.rootPath ):
      cfg = os.path.join( self.pilotParams.rootPath, i )
      if os.path.isfile( cfg ) and cfg.endswith( '.cfg' ):
        extraCFG.append( cfg )

    if self.pilotParams.executeCmd:
      # Execute user command
      self.log.info( "Executing user defined command: %s" % self.pilotParams.executeCmd )
      self.exitWithError( os.system( "source bashrc; %s" % self.pilotParams.executeCmd ) / 256 )

    self.log.info( 'Starting JobAgent' )
    os.environ['PYTHONUNBUFFERED'] = 'yes'

    pid = {}

    for i in xrange(self.pilotParams.processors):

      # One JobAgent per processor allocated to this pilot

      if self.pilotParams.ceType == 'Sudo':
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
                                    os.path.join( self.pilotParams.workingDir, 'jobagent.%02d.log' % i ),
                                    self.pilotParams.installEnv )

      if not pid[i]:
        self.log.error( "Error executing the JobAgent %d" % i )
      else:
        self.log.info( "Forked JobAgent %02d/%d with PID %d" % ( i, self.pilotParams.processors, pid[i] ) )

    # Not very subtle this. How about a time limit??
    for i in xrange(self.pilotParams.processors):
      os.waitpid(pid[i], 0)

    for i in xrange(self.pilotParams.processors):
      shutdownMessage = MultiLaunchAgent.parseJobAgentLog( os.path.join( self.pilotParams.workingDir, 'jobagent.%02d.log' % i ) )
      open( os.path.join( self.pilotParams.workingDir, 'shutdown_message.%02d' % i ), 'w' ).write( shutdownMessage )
      print shutdownMessage

    # FIX ME: this effectively picks one at random. Should be the last one to finish chronologically.
    # Not in order of being started.
    open( os.path.join( self.pilotParams.workingDir, 'shutdown_message' ), 'w' ).write( shutdownMessage )

    fs = os.statvfs( self.pilotParams.workingDir )
    diskSpace = fs[4] * fs[0] / 1024 / 1024
    self.log.info( 'DiskSpace (MB) = %s' % diskSpace )

  @classmethod
  def parseJobAgentLog(cls, logFile):
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
      fFile = open(logFile, 'r')
    except Exception as _:
      return '700 Internal VM logging failed'

    oneline = fFile.readline()

    while oneline:

      for pair in messageMappings:
        if pair[0] in oneline:
          shutdownMessage = pair[1]
          break

      oneline = fFile.readline()

    fFile.close()

    return shutdownMessage

  def execute( self ):
    """ What is called all the time
    """
    self.__setInProcessOpts()
    self.__startJobAgent()

    sys.exit( 0 )
