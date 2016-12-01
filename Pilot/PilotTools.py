""" A set of common tools to be used in pilot commands
"""

import sys
import time
import os
import pickle
import getopt
import imp
import json
import types
import urllib
import urllib2
import signal
import subprocess

__RCSID__ = '$Id$'

def S_OK( value = None ):
  """ Converts a value to a OK/true dictionary message
  """
  return { 'OK' : True, 'Value' : value }

def S_ERROR( msg = None ):
  """ Converts an error message to a OK/false dictionary message
  """
  return { 'OK' : False, 'Message' : msg }

def printVersion( log ):
  """
  Print the version
  """
  log.info( "Running %s" % " ".join( sys.argv ) )
  try:
    with open( "%s.run" % sys.argv[0], "w" ) as fd:
      pickle.dump( sys.argv[1:], fd )
  except OSError:
    pass
  log.info( "Version %s" % __RCSID__ )

def pythonPathCheck():
  """
  Check Python path
  """
  try:
    os.umask( 18 ) # 022
    pythonpath = os.getenv( 'PYTHONPATH', '' ).split( ':' )
    print 'Directories in PYTHONPATH:', pythonpath
    for path in pythonpath:
      if path == '':
        continue
      try:
        if os.path.normpath( path ) in sys.path:
          # In case a given directory is twice in PYTHONPATH it has to removed only once
          sys.path.remove( os.path.normpath( path ) )
      except Exception, x:
        print x
        print "[EXCEPTION-info] Failing path:", path, os.path.normpath( path )
        print "[EXCEPTION-info] sys.path:", sys.path
        raise x
  except Exception, x:
    print x
    print "[EXCEPTION-info] sys.executable:", sys.executable
    print "[EXCEPTION-info] sys.version:", sys.version
    print "[EXCEPTION-info] os.uname():", os.uname()
    raise x

def alarmTimeoutHandler( *_ ):
  """ Alarm timeout handler """
  raise Exception( 'Timeout' )

####
# Start of helper functions
####

def logERROR( msg ):
  """
  Error Logger
  """
  for line in msg.split( "\n" ):
    print "%s UTC dirac-install [ERROR] %s" % ( time.strftime( '%Y-%m-%d %H:%M:%S', time.gmtime() ), line )
  sys.stdout.flush()

def logWARN( msg ):
  """
  Warn logger
  """
  for line in msg.split( "\n" ):
    print "%s UTC dirac-install [WARN] %s" % ( time.strftime( '%Y-%m-%d %H:%M:%S', time.gmtime() ), line )
  sys.stdout.flush()

def logNOTICE( msg ):
  """
  Notice Logger
  """
  for line in msg.split( "\n" ):
    print "%s UTC dirac-install [NOTICE]  %s" % ( time.strftime( '%Y-%m-%d %H:%M:%S', time.gmtime() ), line )
  sys.stdout.flush()


def urlDownloadData(remoteFD, localFD, expectedBytes, log=None):
  """ Helper to download data form already opened URL """
  urlData = ''
  receivedBytes = 0L
  progressBar = False
  count = 1
  data = remoteFD.read( 16384 )
  while data:
    receivedBytes += len( data )
    if localFD:
      localFD.write( data )
    else:
      urlData += data
    data = remoteFD.read( 16384 )
    if count % 20 == 0 and sys.stdout.isatty():
      print '\033[1D' + ".",
      sys.stdout.flush()
      progressBar = True
    count += 1
  if progressBar and sys.stdout.isatty():
    # return cursor to the beginning of the line
    print '\033[1K',
    print '\033[1A'
  if localFD:
    localFD.close()
  remoteFD.close()
  if receivedBytes != expectedBytes and expectedBytes > 0:
    if log:
      log.error( 'URL retrieve: expected size does not match the received one' )
    else:
      logERROR( "File should be %s bytes but received %s" % ( expectedBytes, receivedBytes ) )
    return False, None
  return True, urlData

def urlRetriveTimeout( url, fileName='', log=None, timeout = 0 ):
  """
  Retrieve remote url to local file, with timeout wrapper
  """
  # NOTE: Not thread-safe, since all threads will catch same alarm.
  #       This is OK for dirac-install, since there are no threads.

  if timeout:
    signal.signal( signal.SIGALRM, alarmTimeoutHandler )
    # set timeout alarm
    signal.alarm( timeout + 5 )
  try:
    # if "http_proxy" in os.environ and os.environ['http_proxy']:
    #   proxyIP = os.environ['http_proxy']
    #   proxy = urllib2.ProxyHandler( {'http': proxyIP} )
    #   opener = urllib2.build_opener( proxy )
    #   #opener = urllib2.build_opener()
    #  urllib2.install_opener( opener )
    remoteFD = urllib2.urlopen( url )
    expectedBytes = long(0)
    # Sometimes repositories do not return Content-Length parameter
    try:
      expectedBytes = long( remoteFD.info()[ 'Content-Length' ] )
    except Exception as x:
      msg = 'Content-Length parameter not returned, skipping expectedBytes check'
      logger = log.warn if log else logWARN
      logger(msg)
      expectedBytes = long(0)
    localFD = open( fileName, "wb" ) if fileName else None
    result, urlData = urlDownloadData(remoteFD, localFD, expectedBytes, log)
    if not result:
      return None
  except urllib2.HTTPError, x:
    if x.code == 404:
      msg =  "%s does not exist" % url
      logger = log.error if log else logERROR
      logger(msg)
      if timeout:
        signal.alarm( 0 )
      return None
  except urllib2.URLError:
    msg =  'Timeout after %s seconds on transfer request for "%s"' % ( str( timeout ), url )
    logger = log.error if log else logERROR
    logger(msg)
  except Exception, x:
    msg =  'Timeout after %s seconds on transfer request for "%s"' % ( str( timeout ), url )
    logger = log.error if log else logERROR
    logger(msg)
    if timeout:
      signal.alarm( 0 )
    raise x

  if timeout:
    signal.alarm( 0 )

  if fileName:
    return True
  else:
    return urlData


class ObjectLoader( object ):
  """ Simplified class for loading objects from a DIRAC installation.

      Example:

      ol = ObjectLoader()
      object, modulePath = ol.loadObject( 'pilot', 'LaunchAgent' )
  """

  def __init__( self, baseModules, log ):
    """ init
    """
    self.__rootModules = baseModules
    self.log = log

  def loadModule( self, modName, hideExceptions = False ):
    """ Auto search which root module has to be used
    """
    for rootModule in self.__rootModules:
      impName = modName
      if rootModule:
        impName = "%s.%s" % ( rootModule, impName )
      self.log.debug( "Trying to load %s" % impName )
      module, parentPath = self.__recurseImport( impName, hideExceptions = hideExceptions )
      #Error. Something cannot be imported. Return error
      if module is None:
        return None, None
      #Huge success!
      else:
        return module, parentPath
      #Nothing found, continue
    #Return nothing found
    return None, None


  def __recurseImport( self, modName, parentModule = None, hideExceptions = False ):
    """ Internal function to load modules
    """
    if isinstance( modName, types.StringTypes):
      modName = modName.split( '.' )
    try:
      if parentModule:
        impData = imp.find_module( modName[0], parentModule.__path__ )
      else:
        impData = imp.find_module( modName[0] )
      impModule = imp.load_module( modName[0], *impData )
      if impData[0]:
        impData[0].close()
    except ImportError, excp:
      if str( excp ).find( "No module named %s" % modName[0] ) == 0:
        return None, None
      errMsg = "Can't load %s in %s" % ( ".".join( modName ), parentModule.__path__[0] )
      if not hideExceptions:
        self.log.exception( errMsg )
      return None, None
    if len( modName ) == 1:
      return impModule, parentModule.__path__[0]
    return self.__recurseImport( modName[1:], impModule,
                                 hideExceptions = hideExceptions )


  def loadObject( self, package, moduleName, command ):
    """ Load an object from inside a module
    """
    loadModuleName = '%s.%s' % ( package, moduleName )
    module, parentPath = self.loadModule( loadModuleName )
    if module is None:
      return None, None

    try:
      commandObj = getattr( module, command )
      return commandObj, os.path.join( parentPath, moduleName )
    except AttributeError, e:
      self.log.error( 'Exception: %s' % str(e) )
      return None, None

def getCommand( params, commandName, log ):
  """ Get an instantiated command object for execution.
      Commands are looked in the following modules in the order:

      1. <CommandExtension>Commands
      2. PilotCommands
      3. <Extension>.WorkloadManagementSystem.PilotAgent.<CommandExtension>Commands
      4. <Extension>.WorkloadManagementSystem.PilotAgent.PilotCommands
      5. DIRAC.WorkloadManagementSystem.PilotAgent.<CommandExtension>Commands
      6. DIRAC.WorkloadManagementSystem.PilotAgent.PilotCommands

      Note that commands in 3.-6. can only be used of the the DIRAC installation
      has been done. DIRAC extensions are taken from -e ( --extraPackages ) option
      of the pilot script.
  """
  extensions = params.commandExtensions
  modules = [ m + 'Commands' for m in extensions + ['pilot'] ]
  commandObject = None

  # Look for commands in the modules in the current directory first
  for module in modules:
    try:
      impData = imp.find_module( module )
      commandModule = imp.load_module( module, *impData )
      commandObject = getattr( commandModule, commandName )
    except Exception as _e:
      pass
    if commandObject:
      return commandObject( params ), module

  if params.diracInstalled:
    diracExtensions = []
    for ext in params.extensions:
      if not ext.endswith( 'DIRAC' ):
        diracExtensions.append( ext + 'DIRAC' )
      else:
        diracExtensions.append( ext )
    diracExtensions += ['DIRAC']
    ol = ObjectLoader( diracExtensions, log )
    for module in modules:
      commandObject, modulePath = ol.loadObject( 'WorkloadManagementSystem.PilotAgent',
                                                 module,
                                                 commandName )
      if commandObject:
        return commandObject( params ), modulePath

  # No command could be instantitated
  return None, None

class Logger( object ):
  """ Basic logger object, for use inside the pilot. Just using print.
  """

  def __init__( self, name = 'Pilot', debugFlag = False, pilotOutput = 'pilot.out' ):
    self.debugFlag = debugFlag
    self.name = name
    self.out = pilotOutput

  def __outputMessage( self, msg, level, header ):
    """ Outputs a message based on the level """
    if self.out:
      with open( self.out, 'a' ) as outputFile:
        for _line in msg.split( "\n" ):
          if header:
            outLine = "%s UTC %s [%s] %s" % ( time.strftime( '%Y-%m-%d %H:%M:%S', time.gmtime() ),
                                              level,
                                              self.name,
                                              _line )
            print outLine
            if self.out:
              outputFile.write( outLine + '\n' )
          else:
            print _line
            outputFile.write( _line + '\n' )

    sys.stdout.flush()

  def setDebug( self ):
    """ Set the debug flag"""
    self.debugFlag = True

  def debug( self, msg, header = True):
    """ Prints the debug message"""
    if self.debugFlag:
      self.__outputMessage( msg, "DEBUG", header )

  def error( self, msg, header = True ):
    """ Error printing"""
    self.__outputMessage( msg, "ERROR", header )

  def warn( self, msg, header = True ):
    """ Warn printing """
    self.__outputMessage( msg, "WARN", header )

  def info( self, msg, header = True ):
    """ Info printing """
    self.__outputMessage( msg, "INFO", header )


class ExtendedLogger( Logger ):
  """ The logger object, for use inside the pilot. It prints messages.
      But can be also used to send messages to the queue
  """
  def __init__( self, name = 'Pilot', debugFlag = False, pilotOutput = 'pilot.out', isPilotLoggerOn = False ):
    """ c'tor
    If flag PilotLoggerOn is not set, the logger will behave just like
    the original Logger object, that means it will just print logs locally on the screen
    """
    super(ExtendedLogger, self).__init__(name, debugFlag, pilotOutput)
    if isPilotLoggerOn:
      #the import here was suggest F.S cause PilotLogger imports stomp
      #which is not yet in the DIRAC externals
      #so up to now we want to turn it off
      from Pilot.PilotLogger import PilotLogger
      self.pilotLogger = PilotLogger()
    else:
      self.pilotLogger = None
    self.isPilotLoggerOn = isPilotLoggerOn

  def debug( self, msg, header = True, sendPilotLog = False ):
    """ Debug logger"""
    super(ExtendedLogger, self).debug(msg,header)
    if self.isPilotLoggerOn:
      if sendPilotLog:
        self.pilotLogger.sendMessage(msg, status = "debug")

  def error( self, msg, header = True, sendPilotLog = False ):
    """ Error logger """
    super(ExtendedLogger, self).error(msg,header)
    if self.isPilotLoggerOn:
      if sendPilotLog:
        self.pilotLogger.sendMessage(msg, status = "error")

  def warn( self, msg, header = True, sendPilotLog = False):
    """ Warn logger """
    super(ExtendedLogger, self).warn(msg,header)
    if self.isPilotLoggerOn:
      if sendPilotLog:
        self.pilotLogger.sendMessage(msg, status ="warning")

  def info( self, msg, header = True, sendPilotLog = False ):
    """ Info logger """
    super(ExtendedLogger, self).info(msg,header)
    if self.isPilotLoggerOn:
      if sendPilotLog:
        self.pilotLogger.sendMessage(msg, status = "info")

  def sendMessage( self, msg,  source, phase, status ='info',localFile = None, sendPilotLog = False ):
    """ Sends a message """
    # pass
    if self.isPilotLoggerOn:
      if sendPilotLog:
        self.pilotLogger.sendMessage(messageContent = msg,
                                     source=source,
                                     phase = phase,
                                     status=status,
                                     localOutputFile = localFile)


class CommandBase( object ):
  """ CommandBase is the base class for every command in the pilot commands toolbox
  """

  def __init__( self, pilotParams, dummy='' ):
    """
    Defines the logger and the pilot parameters
    """
    self.pilotParams = pilotParams
    self.log = ExtendedLogger(
        name = self.__class__.__name__,
        debugFlag = False,
        pilotOutput = 'pilot.out',
        isPilotLoggerOn = self.pilotParams.pilotLogging
        )
    #self.log = Logger( self.__class__.__name__ )
    self.debugFlag = False
    for option, _ in self.pilotParams.optList:
      if option == '-d' or option == '--debug':
        self.log.setDebug()
        self.debugFlag = True
    self.log.debug( "\n\n Initialized command %s" % self.__class__ )

  def executeAndGetOutput( self, cmd, environDict = None ):
    """ Execute a command on the worker node and get the output
    """

    self.log.info( "Executing command %s" % cmd )
    try:
      # spawn new processes, connect to their input/output/error pipes, and obtain their return codes.
      _p = subprocess.Popen( "%s" % cmd, shell = True, env=environDict, stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE, close_fds = False )

      # standard output
      outData = _p.stdout.read().strip()
      for line in outData:
        sys.stdout.write( line )
      sys.stdout.write( '\n' )

      for line in _p.stderr:
        sys.stdout.write( line )
      sys.stdout.write( '\n' )

      # return code
      returnCode = _p.wait()
      self.log.debug( "Return code of %s: %d" % ( cmd, returnCode ) )

      return (returnCode, outData)
    except ImportError:
      self.log.error( "Error importing subprocess" )

  def exitWithError( self, errorCode ):
    """ Wrapper around sys.exit()
    """
    self.log.info( "List of child processes of current PID:" )
    retCode, _outData = self.executeAndGetOutput( "ps --forest -o pid,%%cpu,%%mem,tty,stat,time,cmd -g %d" % os.getpid() )
    if retCode:
      self.log.error( "Failed to issue ps [ERROR %d] " % retCode )
    sys.exit( errorCode )

  def forkAndExecute( self, cmd, logFile, environDict = None ):
    """ Fork and execute a command on the worker node
    """

    self.log.info( "Fork and execute command %s" % cmd )
    pid = os.fork()

    if pid != 0:
      # Still in the parent, return the subprocess ID
      return pid

    # The subprocess stdout/stderr will be written to logFile
    with open(logFile, 'a+', 0) as fpLogFile:

      try:
        _p = subprocess.Popen( "%s" % cmd, shell = True, env=environDict, close_fds = False, stdout = fpLogFile, stderr = fpLogFile )

        # return code
        returnCode = _p.wait()
        self.log.debug( "Return code of %s: %d" % ( cmd, returnCode ) )
      except Exception as _:
        returnCode = 99

    sys.exit(returnCode)

class PilotParams( object ):
  """ Class that holds the structure with all the parameters to be used across all the commands
  """

  rootPath = os.getcwd()
  originalRootPath = os.getcwd()
  pilotRootPath = os.getcwd()
  workingDir = os.getcwd()

  MAX_CYCLES = 10
  name = ""
  extensions = []
  tags = []
  site = ""
  setup = ""
  configServer = ""
  installation = ""
  ceName = ""
  ceType = ""
  gridCEType = ""
  queueName = ""
  platform = ""
  minDiskSpace = 2560 #MB
  jobCPUReq = 900
  pythonVersion = '27'
  userGroup = ""
  userDN = ""
  flavour = 'DIRAC'
  optList = {}
  debugFlag = False
  local = False

  commandExtensions = []
  commands = ['CheckWorkerNode', 'InstallDIRAC', 'ConfigureBasics',
              'CheckCECapabilities', 'CheckWNCapabilities',
              'ConfigureSite', 'ConfigureArchitecture', 'ConfigureCPURequirements', 'LaunchAgent']

  gridVersion = ''
  pilotReference = ''
  releaseVersion = ''
  releaseProject = ''
  gateway = ""
  useServerCertificate = False
  pilotScriptName = ''
  # DIRAC client installation environment
  diracInstalled = False
  diracExtensions = []

  # If DIRAC is preinstalled this file will receive the updates of the local configuration
  localConfigFile = ''
  executeCmd = False
  configureScript = 'dirac-configure'
  architectureScript = 'dirac-platform'

  pilotCFGFile = 'pilot.json'
  pilotLogging = False

  maxCycles = MAX_CYCLES
  # Some commands can define environment necessary to execute subsequent commands
  installEnv = os.environ

  certsLocation = '%s/etc/grid-security' % workingDir
  processors = 1

  # Pilot command options
  cmdOpts = ( ( 'b', 'build', 'Force local compilation' ),
              ( 'd', 'debug', 'Set debug flag' ),
              ( 'e:', 'extraPackages=', 'Extra packages to install (comma separated)' ),
              ( 'E:', 'commandExtensions=', 'Python module with extra commands' ),
              ( 'X:', 'commands=', 'Pilot commands to execute commands' ),
              ( 'g:', 'grid=', 'lcg tools package version' ),
              ( 'h', 'help', 'Show this help' ),
              ( 'i:', 'python=', 'Use python<26|27> interpreter' ),
              ( 'l:', 'project=', 'Project to install' ),
              ( 'p:', 'platform=', 'Use <platform> instead of local one' ),
              ( 'u:', 'url=', 'Use <url> to download tarballs' ),
              ( 'r:', 'release=', 'DIRAC release to install' ),
              ( 'n:', 'name=', 'Set <Site> as Site Name' ),
              ( 'D:', 'disk=', 'Require at least <space> MB available' ),
              ( 'M:', 'MaxCycles=', 'Maximum Number of JobAgent cycles to run' ),
              ( 'N:', 'Name=', 'CE Name' ),
              ( 'Q:', 'Queue=', 'Queue name' ),
              ( 'y:', 'CEType=', 'CE Type (normally InProcess)' ),
              ( 'a:', 'gridCEType=', 'Grid CE Type (CREAM etc)' ),
              ( 'S:', 'setup=', 'DIRAC Setup to use' ),
              ( 'C:', 'configurationServer=', 'Configuration servers to use' ),
              ( 'T:', 'CPUTime', 'Requested CPU Time' ),
              ( 'G:', 'Group=', 'DIRAC Group to use' ),
              ( 'O:', 'OwnerDN', 'Pilot OwnerDN (for private pilots)' ),
              ( 'U',  'Upload', 'Upload compiled distribution (if built)' ),
              ( 'V:', 'installation=', 'Installation configuration file' ),
              ( 'W:', 'gateway=', 'Configure <gateway> as DIRAC Gateway during installation' ),
              ( 's:', 'section=', 'Set base section for relative parsed options' ),
              ( 'o:', 'option=', 'Option=value to add' ),
              ( 'c', 'cert', 'Use server certificate instead of proxy' ),
              ( 'C:', 'certLocation=', 'Specify server certificate location' ),
              ( 'F:', 'pilotCFGFile=', 'Specify pilot CFG file' ),
              ( 'R:', 'reference=', 'Use this pilot reference' ),
              ( 'x:', 'execute=', 'Execute instead of JobAgent' ),
              ( 'z:', 'pilotLogging', 'Activate pilot logging system' ),
            )

  def __init__( self ):
    """ c'tor

        param names and defaults are defined here
    """
    self.log = Logger( self.__class__.__name__ )



    # Set number of allocatable processors from MJF if available
    try:
      self.processors = int(urllib.urlopen(os.path.join(os.environ['JOBFEATURES'], 'allocated_cpu')).read())
    except Exception  as _:
      self.processors = 1


    # Possibly get Setup and JSON URL/filename from command line
    self.__initCommandLine1()

    # Get main options from the JSON file
    self.__initJSON()

    # Command line can override options from JSON
    self.__initCommandLine2()


  def __parseOption(self, optionValues, field, lambda_func=None, compare=False):
    """ Append an option to the configuration from the PilotPramas"""
    for option, value in self.optList:
      if option in optionValues:
        if lambda_func:
          try:
            value = lambda_func(value)
            if compare:
              value = min(value, self.MAX_CYCLES)
          except Exception  as _:
            pass
        setattr(self, field, value)
        break

  def __initCommandLine1( self ):
    """ Parses and interpret options on the command line: first pass
    """

    self.optList, __args__ = getopt.getopt( sys.argv[1:],
                                            "".join( [ opt[0] for opt in self.cmdOpts ] ),
                                            [ opt[1] for opt in self.cmdOpts ] )
    self.__parseOption(['-N','--Name'], 'ceName')
    self.__parseOption(['-a','--gridCEType'], 'gridCEType')
    self.__parseOption(['-d','--debug'], 'debugFlag', lambda_func=lambda x: True)
    self.__parseOption(['-S','--setup'], 'setup')
    self.__parseOption(['-F','--pilotCFGFile'], 'gridCEType')


  def __initCommandLine2( self ):
    """ Parses and interpret options on the command line: second pass
    """

    self.optList, __args__ = getopt.getopt( sys.argv[1:],
                                            "".join( [ opt[0] for opt in self.cmdOpts ] ),
                                            [ opt[1] for opt in self.cmdOpts ] )
    self.__parseOption(['-E', '--commandExtensions'], 'commandExtensions', lambda_func=lambda x: x.split(','))
    self.__parseOption(['-X', '--commands'], 'commands', lambda_func=lambda x: x.split(','))
    self.__parseOption(['-e', '--extraPackages'], 'extensions', lambda_func=lambda x: x.split(','))
    self.__parseOption(['-n', '--name'], 'site')
    self.__parseOption(['-y', '--CEType'], 'ceType')
    self.__parseOption(['-Q', '--Queue'], 'queueName')
    self.__parseOption(['-R', '--reference'], 'pilotReference')
    self.__parseOption(['-C', '--configurationServer'], 'configServer')
    self.__parseOption(['-G', '--Group'], 'userGroup')
    self.__parseOption(['-x', '--execute'], 'executeCmd')
    self.__parseOption(['-O', '--OwnerDN'], 'userDN')
    self.__parseOption(['-V', '--installation'], 'installation')
    self.__parseOption(['-p', '--platform'], 'platform')
    self.__parseOption(['-D', '--disk'], 'minDiskSpace', lambda_func=int)
    self.__parseOption(['-r', '--release'], 'releaseVersion', lambda_func=lambda x: x.split(',',1)[0])
    self.__parseOption(['-l', '--project'], 'releaseProject')
    self.__parseOption(['-W', '--gateway'], 'gateway')
    self.__parseOption(['-c', '--cert'], 'useServerCertificate', lambda_func=lambda x: True)
    self.__parseOption(['-C', '--certLocation'], 'certsLocation')
    self.__parseOption(['-M', '--MaxCycles'], 'maxCycles', lambda_func=int, compare=True)
    self.__parseOption(['-T', '--CPUTime'], 'jobCPUReq')
    self.__parseOption(['-P', '--processors'], 'site',lambda_func=int)
    self.__parseOption(['-z', '--pilotLogging'], 'pilotLogging', lambda_func=lambda x: True)


  def __parseCeName(self, pilotCFGFileContent):
    """ Parse CeName from Json """
    if self.ceName:
      # Try to get the site name and grid CEType from the CE name
      # GridCEType is like "CREAM" or "HTCondorCE" not "InProcess" etc
      try:
        setattr(self, 'name', str( pilotCFGFileContent['CEs'][self.ceName]['Site'] ))
      except Exception  as _:
        pass
      if not self.gridCEType:
        # We don't override a grid CEType given on the command line!
        try:
          self.gridCEType = str( pilotCFGFileContent['CEs'][self.ceName]['GridCEType'] )
        except Exception  as _:
          pass

  def __parseCommands(self, pilotCFGFileContent):
    """ Parse commands from Json"""
    # Commands first
    try:
      self.commands = [str( pv ) for pv in pilotCFGFileContent['Setups'][self.setup]['Commands'][self.gridCEType]]
    except Exception  as _:
      try:
        self.commands = [str( pv ) for pv in pilotCFGFileContent['Setups'][self.setup]['Commands']['Defaults']]
      except Exception  as _:
        try:
          self.commands = [str( pv ) for pv in pilotCFGFileContent['Setups']['Defaults']['Commands'][self.gridCEType]]
        except Exception  as _:
          try:
            self.commands = [str( pv ) for pv in pilotCFGFileContent['Defaults']['Commands']['Defaults']]
          except Exception  as _:
            pass

  def __parseCommandsExtension(self, pilotCFGFileContent):
    """ Parse commands extensions from Json"""
    # Now the other options we handle
    try:
      self.commandExtensions = [str( pv ) for pv in pilotCFGFileContent['Setups'][self.setup]['CommandExtensions']]
    except Exception  as _:
      try:
        self.commandExtensions = [str( pv ) for pv in pilotCFGFileContent['Setups']['Defaults']['CommandExtensions']]
      except Exception  as _:
        pass

    try:
      self.configServer = str( pilotCFGFileContent['Setups'][self.setup]['ConfigurationServer'] )
    except Exception  as _:
      try:
        self.configServer = str( pilotCFGFileContent['Setups']['Defaults']['ConfigurationServer'] )
      except Exception  as _:
        pass

  def __initJSON( self ):
    """Retrieve pilot parameters from the content of json file. The file should be something like:

    {
      'DefaultSetup':'xyz',

      'Setups'      :{
                      'SetupName':{
                                    'Commands'           :{
                                                           'GridCEType1' : ['cmd1','cmd2',...],
                                                           'GridCEType2' : ['cmd1','cmd2',...],
                                                           'Defaults'    : ['cmd1','cmd2',...]
                                                          },
                                    'Extensions'         :['ext1','ext2',...],
                                    'ConfigurationServer':'url',
                                    'Version'            :['xyz']
                                    'Project'            :['xyz']
                                  },

                      'Defaults' :{
                                    'Commands'           :{
                                                            'GridCEType1' : ['cmd1','cmd2',...],
                                                            'GridCEType2' : ['cmd1','cmd2',...],
                                                            'Defaults'    : ['cmd1','cmd2',...]
                                                          },
                                    'Extensions'         :['ext1','ext2',...],
                                    'ConfigurationServer':'url',
                                    'Version'            :['xyz']
                                    'Project'            :['xyz']
                                  }
                     }

      'CEs'         :{
                      'ce1.domain':{
                                    'Site'      :'XXX.yyyy.zz',
                                    'GridCEType':'AABBCC'
                                   },
                      'ce2.domain':{
                                    'Site'      :'ZZZ.yyyy.xx',
                                    'GridCEType':'CCBBAA'
                                   }
                     }
    }

    The file must contains at least the Defaults section. Missing values are taken from the Defaults setup. """

    with open ( self.pilotCFGFile, 'r' ) as fp:
      pilotCFGFileContent = json.load( fp )

    self.__parseCeName(pilotCFGFileContent)

    if not self.setup:
      # We don't use the default to override an explicit value from command line!
      try:
        self.setup = str( pilotCFGFileContent['DefaultSetup'] )
      except Exception  as _:
        pass
    self.__parseCommands(pilotCFGFileContent)

    self.__parseCommandsExtension(pilotCFGFileContent)

    # Version might be a scalar or a list. We just want the first one.
    try:
      value = pilotCFGFileContent['Setups'][self.setup]['Version']
    except Exception  as _:
      try:
        value = pilotCFGFileContent['Setups']['Defaults']['Version']
      except Exception  as _:
        value = None

    if isinstance(value, basestring):
      self.releaseVersion = str( value )
    elif value:
      self.releaseVersion = str( value[0] )

    try:
      self.releaseProject = str( pilotCFGFileContent['Setups'][self.setup]['Project'] )
    except Exception  as _:
      try:
        self.releaseProject = str( pilotCFGFileContent['Setups']['Defaults']['Project'] )
      except Exception  as _:
        pass
