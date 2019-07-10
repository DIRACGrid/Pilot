""" A set of common tools to be used in pilot commands
"""

__RCSID__ = '$Id$'

import sys
import time
import os
import pickle
import getopt
import imp
import json
import urllib
import urllib2
import signal
import subprocess

from PilotLogger import PilotLogger


def printVersion(log):

  log.info("Running %s" % " ".join(sys.argv))
  try:
    with open("%s.run" % sys.argv[0], "w") as fd:
      pickle.dump(sys.argv[1:], fd)
  except OSError:
    pass
  log.info("Version %s" % __RCSID__)


def pythonPathCheck():

  try:
    os.umask(18)  # 022
    pythonpath = os.getenv('PYTHONPATH', '').split(':')
    print 'Directories in PYTHONPATH:', pythonpath
    for p in pythonpath:
      if p == '':
        continue
      try:
        if os.path.normpath(p) in sys.path:
          # In case a given directory is twice in PYTHONPATH it has to removed only once
          sys.path.remove(os.path.normpath(p))
      except Exception as x:
        print x
        print "[EXCEPTION-info] Failing path:", p, os.path.normpath(p)
        print "[EXCEPTION-info] sys.path:", sys.path
        raise x
  except Exception as x:
    print x
    print "[EXCEPTION-info] sys.executable:", sys.executable
    print "[EXCEPTION-info] sys.version:", sys.version
    print "[EXCEPTION-info] os.uname():", os.uname()
    raise x


def alarmTimeoutHandler(*args):
  raise Exception('Timeout')


def retrieveUrlTimeout(url, fileName, log, timeout=0):
  """
   Retrieve remote url to local file, with timeout wrapper
  """
  urlData = ''
  if timeout:
    signal.signal(signal.SIGALRM, alarmTimeoutHandler)
    # set timeout alarm
    signal.alarm(timeout + 5)
  try:
    remoteFD = urllib2.urlopen(url)
    expectedBytes = 0
    # Sometimes repositories do not return Content-Length parameter
    try:
      expectedBytes = long(remoteFD.info()['Content-Length'])
    except Exception as x:
      expectedBytes = 0
    data = remoteFD.read()
    if fileName:
      with open(fileName + '-local', "wb") as localFD:
        localFD.write(data)
    else:
      urlData += data
    remoteFD.close()
    if len(data) != expectedBytes and expectedBytes > 0:
      log.error('URL retrieve: expected size does not match the received one')
      return False

    if timeout:
      signal.alarm(0)
    if fileName:
      return True
    return urlData

  except urllib2.HTTPError as x:
    if x.code == 404:
      log.error("URL retrieve: %s does not exist" % url)
      if timeout:
        signal.alarm(0)
      return False
  except urllib2.URLError:
    log.error('Timeout after %s seconds on transfer request for "%s"' % (str(timeout), url))
    return False
  except Exception as x:
    if x == 'Timeout':
      log.error('Timeout after %s seconds on transfer request for "%s"' % (str(timeout), url))
    if timeout:
      signal.alarm(0)
    raise x


class ObjectLoader(object):
  """ Simplified class for loading objects from a DIRAC installation.

      Example:

      ol = ObjectLoader()
      object, modulePath = ol.loadObject( 'pilot', 'LaunchAgent' )
  """

  def __init__(self, baseModules, log):
    """ init
    """
    self.__rootModules = baseModules
    self.log = log

  def loadModule(self, modName, hideExceptions=False):
    """ Auto search which root module has to be used
    """
    for rootModule in self.__rootModules:
      impName = modName
      if rootModule:
        impName = "%s.%s" % (rootModule, impName)
      self.log.debug("Trying to load %s" % impName)
      module, parentPath = self.__recurseImport(impName, hideExceptions=hideExceptions)
      # Error. Something cannot be imported. Return error
      if module is None:
        return None, None
      # Huge success!
      return module, parentPath
      # Nothing found, continue
    # Return nothing found
    return None, None

  def __recurseImport(self, modName, parentModule=None, hideExceptions=False):
    """ Internal function to load modules
    """
    if isinstance(modName, basestring):
      modName = modName.split('.')
    try:
      if parentModule:
        impData = imp.find_module(modName[0], parentModule.__path__)
      else:
        impData = imp.find_module(modName[0])
      impModule = imp.load_module(modName[0], *impData)
      if impData[0]:
        impData[0].close()
    except ImportError as excp:
      if str(excp).find("No module named %s" % modName[0]) == 0:
        return None, None
      errMsg = "Can't load %s in %s" % (".".join(modName), parentModule.__path__[0])
      if not hideExceptions:
        self.log.exception(errMsg)
      return None, None
    if len(modName) == 1:
      return impModule, parentModule.__path__[0]
    return self.__recurseImport(modName[1:], impModule,
                                hideExceptions=hideExceptions)

  def loadObject(self, package, moduleName, command):
    """ Load an object from inside a module
    """
    loadModuleName = '%s.%s' % (package, moduleName)
    module, parentPath = self.loadModule(loadModuleName)
    if module is None:
      return None, None
    try:
      commandObj = getattr(module, command)
      return commandObj, os.path.join(parentPath, moduleName)
    except AttributeError as e:
      self.log.error('Exception: %s' % str(e))
      return None, None


def getCommand(params, commandName, log):
  """ Get an instantiated command object for execution.
      Commands are looked in the following modules in the order:

      1. <CommandExtension>Commands
      2. pilotCommands
      3. <Extension>.WorkloadManagementSystem.PilotAgent.<CommandExtension>Commands
      4. <Extension>.WorkloadManagementSystem.PilotAgent.pilotCommands
      5. DIRAC.WorkloadManagementSystem.PilotAgent.<CommandExtension>Commands
      6. DIRAC.WorkloadManagementSystem.PilotAgent.pilotCommands

      Note that commands in 3.-6. can only be used of the the DIRAC installation
      has been done. DIRAC extensions are taken from -e ( --extraPackages ) option
      of the pilot script.
  """
  extensions = params.commandExtensions
  modules = [m + 'Commands' for m in extensions + ['pilot']]
  commandObject = None

  # Look for commands in the modules in the current directory first
  for module in modules:
    try:
      impData = imp.find_module(module)
      commandModule = imp.load_module(module, *impData)
      commandObject = getattr(commandModule, commandName)
    except Exception:
      pass
    if commandObject:
      return commandObject(params), module

  if params.diracInstalled:
    diracExtensions = []
    for ext in params.extensions:
      if not ext.endswith('DIRAC'):
        diracExtensions.append(ext + 'DIRAC')
      else:
        diracExtensions.append(ext)
    diracExtensions += ['DIRAC']
    ol = ObjectLoader(diracExtensions, log)
    for module in modules:
      commandObject, modulePath = ol.loadObject('WorkloadManagementSystem.PilotAgent',
                                                module,
                                                commandName)
      if commandObject:
        return commandObject(params), modulePath

  # No command could be instantitated
  return None, None


class Logger(object):
  """ Basic logger object, for use inside the pilot. Just using print.
  """

  def __init__(self, name='Pilot', debugFlag=False, pilotOutput='pilot.out'):
    self.debugFlag = debugFlag
    self.name = name
    self.out = pilotOutput

  def __outputMessage(self, msg, level, header):
    if self.out:
      with open(self.out, 'a') as outputFile:
        for _line in msg.split("\n"):
          if header:
            outLine = "%s UTC %s [%s] %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
                                             level,
                                             self.name,
                                             _line)
            print outLine
            if self.out:
              outputFile.write(outLine + '\n')
          else:
            print _line
            outputFile.write(_line + '\n')

    sys.stdout.flush()

  def setDebug(self):
    self.debugFlag = True

  def debug(self, msg, header=True):
    if self.debugFlag:
      self.__outputMessage(msg, "DEBUG", header)

  def error(self, msg, header=True):
    self.__outputMessage(msg, "ERROR", header)

  def warn(self, msg, header=True):
    self.__outputMessage(msg, "WARN", header)

  def info(self, msg, header=True):
    self.__outputMessage(msg, "INFO", header)


class ExtendedLogger(Logger):
  """ The logger object, for use inside the pilot. It prints messages.
      But can be also used to send messages to the queue
  """

  def __init__(self,
               name='Pilot',
               debugFlag=False,
               pilotOutput='pilot.out',
               isPilotLoggerOn=True,
               setup='DIRAC-Certification'):
    """ c'tor
    If flag PilotLoggerOn is not set, the logger will behave just like
    the original Logger object, that means it will just print logs locally on the screen
    """
    super(ExtendedLogger, self).__init__(name, debugFlag, pilotOutput)
    if isPilotLoggerOn:
      self.pilotLogger = PilotLogger(setup=setup)
    else:
      self.pilotLogger = None
    self.isPilotLoggerOn = isPilotLoggerOn

  def debug(self, msg, header=True, sendPilotLog=False):
    super(ExtendedLogger, self).debug(msg, header)
    if self.isPilotLoggerOn and sendPilotLog:
        self.pilotLogger.sendMessage(msg, status="debug")

  def error(self, msg, header=True, sendPilotLog=False):
    super(ExtendedLogger, self).error(msg, header)
    if self.isPilotLoggerOn and sendPilotLog:
        self.pilotLogger.sendMessage(msg, status="error")

  def warn(self, msg, header=True, sendPilotLog=False):
    super(ExtendedLogger, self).warn(msg, header)
    if self.isPilotLoggerOn and sendPilotLog:
        self.pilotLogger.sendMessage(msg, status="warning")

  def info(self, msg, header=True, sendPilotLog=False):
    super(ExtendedLogger, self).info(msg, header)
    if self.isPilotLoggerOn and sendPilotLog:
        self.pilotLogger.sendMessage(msg, status="info")

  def sendMessage(self, msg, source, phase, status='info', sendPilotLog=True):
    if self.isPilotLoggerOn and sendPilotLog:
        self.pilotLogger.sendMessage(messageContent=msg,
                                     source=source,
                                     phase=phase,
                                     status=status)


class CommandBase(object):
  """ CommandBase is the base class for every command in the pilot commands toolbox
  """

  def __init__(self, pilotParams, dummy=''):
    """ c'tor

        Defines the logger and the pilot parameters
    """
    self.pp = pilotParams
    self.log = ExtendedLogger(
        name=self.__class__.__name__,
        debugFlag=False,
        pilotOutput='pilot.out',
        isPilotLoggerOn=self.pp.pilotLogging,
        setup=self.pp.setup
    )
    # self.log = Logger( self.__class__.__name__ )
    self.debugFlag = False
    for o, _ in self.pp.optList:
      if o == '-d' or o == '--debug':
        self.log.setDebug()
        self.debugFlag = True
    self.log.debug("\n\n Initialized command %s" % self.__class__)

  def executeAndGetOutput(self, cmd, environDict=None):
    """ Execute a command on the worker node and get the output
    """

    self.log.info("Executing command %s" % cmd)
    try:
      # spawn new processes, connect to their input/output/error pipes, and obtain their return codes.
      import subprocess
      _p = subprocess.Popen("%s" % cmd, shell=True, env=environDict, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, close_fds=False)

      # standard output
      outData = _p.stdout.read().strip()
      for line in outData:
        sys.stdout.write(line)
      sys.stdout.write('\n')

      for line in _p.stderr:
        sys.stdout.write(line)
      sys.stdout.write('\n')

      # return code
      returnCode = _p.wait()
      self.log.debug("Return code of %s: %d" % (cmd, returnCode))

      return (returnCode, outData)
    except ImportError:
      self.log.error("Error importing subprocess")

  def exitWithError(self, errorCode):
    """ Wrapper around sys.exit()
    """
    self.log.info("List of child processes of current PID:")
    retCode, _outData = self.executeAndGetOutput("ps --forest -o pid,%%cpu,%%mem,tty,stat,time,cmd -g %d" % os.getpid())
    if retCode:
      self.log.error("Failed to issue ps [ERROR %d] " % retCode)
    sys.exit(errorCode)

  def forkAndExecute(self, cmd, logFile, environDict=None):
    """ Fork and execute a command on the worker node
    """

    self.log.info("Fork and execute command %s" % cmd)
    pid = os.fork()

    if pid != 0:
      # Still in the parent, return the subprocess ID
      return pid

    # The subprocess stdout/stderr will be written to logFile
    with open(logFile, 'a+', 0) as fpLogFile:

      try:
        _p = subprocess.Popen(
            "%s" %
            cmd,
            shell=True,
            env=environDict,
            close_fds=False,
            stdout=fpLogFile,
            stderr=fpLogFile)

        # return code
        returnCode = _p.wait()
        self.log.debug("Return code of %s: %d" % (cmd, returnCode))
      except BaseException:
        returnCode = 99

    sys.exit(returnCode)


class PilotParams(object):
  """ Class that holds the structure with all the parameters to be used across all the commands
  """

  MAX_CYCLES = 10

  def __init__(self):
    """ c'tor

        param names and defaults are defined here
    """
    self.log = Logger(self.__class__.__name__, debugFlag=True)
    self.rootPath = os.getcwd()
    self.originalRootPath = os.getcwd()
    self.pilotRootPath = os.getcwd()
    self.workingDir = os.getcwd()

    self.optList = {}
    self.keepPythonPath = False
    self.debugFlag = False
    self.local = False
    self.pilotJSON = None
    self.commandExtensions = []
    self.commands = ['CheckWorkerNode', 'InstallDIRAC', 'ConfigureBasics',
                     'CheckCECapabilities', 'CheckWNCapabilities',
                     'ConfigureSite', 'ConfigureArchitecture', 'ConfigureCPURequirements', 'LaunchAgent']
    self.commandOptions = {}
    self.extensions = []
    self.tags = []
    self.reqtags = []
    self.site = ""
    self.setup = ""
    self.configServer = ""
    self.installation = ""
    self.ceName = ""
    self.ceType = ""
    self.queueName = ""
    self.gridCEType = ""
    self.platform = ""
    # in case users want to specify the max number of processors requested, per pilot
    self.maxNumberOfProcessors = 0
    self.minDiskSpace = 2560  # MB
    self.pythonVersion = '27'
    self.userGroup = ""
    self.userDN = ""
    self.maxCycles = self.MAX_CYCLES
    self.flavour = 'DIRAC'
    self.gridVersion = ''
    self.pilotReference = ''
    self.releaseVersion = ''
    self.releaseProject = ''
    self.gateway = ""
    self.useServerCertificate = False
    self.pilotScriptName = ''
    self.genericOption = ''
    # DIRAC client installation environment
    self.diracInstalled = False
    self.diracExtensions = []
    # Some commands can define environment necessary to execute subsequent commands
    self.installEnv = os.environ
    # If DIRAC is preinstalled this file will receive the updates of the local configuration
    self.localConfigFile = ''
    self.executeCmd = False
    self.configureScript = 'dirac-configure'
    self.architectureScript = 'dirac-platform'
    self.certsLocation = '%s/etc/grid-security' % self.workingDir
    self.pilotCFGFile = 'pilot.json'
    self.pilotLogging = False
    self.modules = ''  # see dirac-install "-m" option documentation

    # Parameters that can be determined at runtime only
    self.queueParameters = {}  # from CE description
    self.jobCPUReq = 900  # HS06s, here just a random value

    # Set number of allocatable processors from MJF if available
    try:
      self.pilotProcessors = int(urllib.urlopen(os.path.join(os.environ['JOBFEATURES'], 'allocated_cpu')).read())
    except BaseException:
      self.pilotProcessors = 1

    # Pilot command options
    self.cmdOpts = (('', 'requiredTag=', 'extra required tags for resource description'),
                    ('a:', 'gridCEType=', 'Grid CE Type (CREAM etc)'),
                    ('b', 'build', 'Force local compilation'),
                    ('c', 'cert', 'Use server certificate instead of proxy'),
                    ('d', 'debug', 'Set debug flag'),
                    ('e:', 'extraPackages=', 'Extra packages to install (comma separated)'),
                    ('g:', 'grid=', 'lcg tools package version'),
                    ('', 'dirac-os', 'use DIRACOS'),
                    ('h', 'help', 'Show this help'),
                    ('i:', 'python=', 'Use python<26|27> interpreter'),
                    ('k', 'keepPP', 'Do not clear PYTHONPATH on start'),
                    ('l:', 'project=', 'Project to install'),
                    ('n:', 'name=', 'Set <Site> as Site Name'),
                    ('o:', 'option=', 'Option=value to add'),
                    ('p:', 'platform=', 'Use <platform> instead of local one'),
                    ('m:', 'maxNumberOfProcessors=',
                     'specify a max number of processors to use'),
                    ('', 'modules=', 'for installing non-released code (see dirac-install "-m" option documentation)'),
                    ('r:', 'release=', 'DIRAC release to install'),
                    ('s:', 'section=', 'Set base section for relative parsed options'),
                    ('t:', 'tag=', 'extra tags for resource description'),
                    ('u:', 'url=', 'Use <url> to download tarballs'),
                    ('x:', 'execute=', 'Execute instead of JobAgent'),
                    ('y:', 'CEType=', 'CE Type (normally InProcess)'),
                    ('z', 'pilotLogging', 'Activate pilot logging system'),
                    ('C:', 'configurationServer=', 'Configuration servers to use'),
                    ('D:', 'disk=', 'Require at least <space> MB available'),
                    ('E:', 'commandExtensions=', 'Python modules with extra commands'),
                    ('F:', 'pilotCFGFile=', 'Specify pilot CFG file'),
                    ('G:', 'Group=', 'DIRAC Group to use'),
                    ('K:', 'certLocation=', 'Specify server certificate location'),
                    ('M:', 'MaxCycles=', 'Maximum Number of JobAgent cycles to run'),
                    ('N:', 'Name=', 'CE Name'),
                    ('O:', 'OwnerDN=', 'Pilot OwnerDN (for private pilots)'),
                    ('P:', 'pilotProcessors=', 'Number of processors allocated to this pilot'),
                    ('Q:', 'Queue=', 'Queue name'),
                    ('R:', 'reference=', 'Use this pilot reference'),
                    ('S:', 'setup=', 'DIRAC Setup to use'),
                    ('T:', 'CPUTime=', 'Requested CPU Time'),
                    ('U', 'Upload', 'Upload compiled distribution (if built)'),
                    ('V:', 'installation=', 'Installation configuration file'),
                    ('W:', 'gateway=', 'Configure <gateway> as DIRAC Gateway during installation'),
                    ('X:', 'commands=', 'Pilot commands to execute'),
                    ('Z:', 'commandOptions=', 'Options parsed by command modules')
                    )

    # Possibly get Setup and JSON URL/filename from command line
    self.__initCommandLine1()

    # Get main options from the JSON file
    self.__initJSON()

    # Command line can override options from JSON
    self.__initCommandLine2()

  def __initCommandLine1(self):
    """ Parses and interpret options on the command line: first pass
    """

    self.optList, __args__ = getopt.getopt(sys.argv[1:],
                                           "".join([opt[0] for opt in self.cmdOpts]),
                                           [opt[1] for opt in self.cmdOpts])
    self.log.debug("Options list: %s" % self.optList)
    for o, v in self.optList:
      if o == '-N' or o == '--Name':
        self.ceName = v
      elif o == '-a' or o == '--gridCEType':
        self.gridCEType = v
      elif o == '-d' or o == '--debug':
        self.debugFlag = True
      elif o in ('-S', '--setup'):
        self.setup = v
      elif o == '-F' or o == '--pilotCFGFile':
        self.pilotCFGFile = v

  def __initCommandLine2(self):
    """ Parses and interpret options on the command line: second pass
    """

    self.optList, __args__ = getopt.getopt(sys.argv[1:],
                                           "".join([opt[0] for opt in self.cmdOpts]),
                                           [opt[1] for opt in self.cmdOpts])
    for o, v in self.optList:
      if o == '-E' or o == '--commandExtensions':
        self.commandExtensions = v.split(',')
      elif o == '-X' or o == '--commands':
        self.commands = v.split(',')
      elif o == '-Z' or o == '--commandOptions':
        for i in v.split(','):
          self.commandOptions[i.split('=', 1)[0].strip()] = i.split('=', 1)[1].strip()
      elif o == '-e' or o == '--extraPackages':
        self.extensions = v.split(',')
      elif o == '-n' or o == '--name':
        self.site = v
      elif o == '-y' or o == '--CEType':
        self.ceType = v
      elif o == '-Q' or o == '--Queue':
        self.queueName = v
      elif o == '-R' or o == '--reference':
        self.pilotReference = v
      elif o == '-k' or o == '--keepPP':
        self.keepPythonPath = True
      elif o in ('-C', '--configurationServer'):
        self.configServer = v
      elif o in ('-G', '--Group'):
        self.userGroup = v
      elif o in ('-x', '--execute'):
        self.executeCmd = v
      elif o in ('-O', '--OwnerDN'):
        self.userDN = v
      elif o in ('-V', '--installation'):
        self.installation = v
      elif o == '-p' or o == '--platform':
        self.platform = v
      elif o == '-m' or o == '--maxNumberOfProcessors':
        self.maxNumberOfProcessors = int(v)
      elif o == '-D' or o == '--disk':
        try:
          self.minDiskSpace = int(v)
        except ValueError:
          pass
      elif o == '-r' or o == '--release':
        self.releaseVersion = v.split(',', 1)[0]
      elif o in ('-l', '--project'):
        self.releaseProject = v
      elif o in ('-W', '--gateway'):
        self.gateway = v
      elif o == '-c' or o == '--cert':
        self.useServerCertificate = True
      elif o == '-C' or o == '--certLocation':
        self.certsLocation = v
      elif o == '-M' or o == '--MaxCycles':
        try:
          self.maxCycles = min(self.MAX_CYCLES, int(v))
        except ValueError:
          pass
      elif o in ('-T', '--CPUTime'):
        self.jobCPUReq = v
      elif o == '-P' or o == '--pilotProcessors':
        try:
          self.pilotProcessors = int(v)
        except BaseException:
          pass
      elif o == '-z' or o == '--pilotLogging':
        self.pilotLogging = True
      elif o in ('-o', '--option'):
        self.genericOption = v
      elif o in ('-t', '--tag'):
        self.tags.append(v)
      elif o == '--requiredTag':
        self.reqtags.append(v)
      elif o == '--modules':
        self.modules = v

  def __initJSON(self):
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
    self.log.debug("JSON file loaded: %s" % self.pilotCFGFile)
    with open(self.pilotCFGFile, 'r') as fp:
      # We save the parsed JSON in case pilot commands need it
      # to read their own options
      self.pilotJSON = json.load(fp)

    self.log.debug("CE name: %s" % self.ceName)
    if self.ceName:
      # Try to get the site name and grid CEType from the CE name
      # GridCEType is like "CREAM" or "HTCondorCE" not "InProcess" etc
      try:
        self.site = str(self.pilotJSON['CEs'][self.ceName]['Site'])
      except KeyError:
        pass
      try:
        if not self.gridCEType:
          # We don't override a grid CEType given on the command line!
          self.gridCEType = str(self.pilotJSON['CEs'][self.ceName]['GridCEType'])
      except KeyError:
        pass

    self.log.debug("Setup: %s" % self.setup)
    if not self.setup:
      # We don't use the default to override an explicit value from command line!
      try:
        self.setup = str(self.pilotJSON['DefaultSetup'])
      except KeyError:
        pass

    # Commands first
    # FIXME: pilotSynchronizer() should publish these as comma-separated lists. We are ready for that.
    try:
      if isinstance(self.pilotJSON['Setups'][self.setup]['Commands'][self.gridCEType], basestring):
        self.commands = [str(pv).strip() for pv in self.pilotJSON['Setups']
                         [self.setup]['Commands'][self.gridCEType].split(',')]
      else:
        self.commands = [str(pv).strip() for pv in self.pilotJSON['Setups'][self.setup]['Commands'][self.gridCEType]]
    except KeyError:
      try:
        if isinstance(self.pilotJSON['Setups'][self.setup]['Commands']['Defaults'], basestring):
          self.commands = [str(pv).strip() for pv in self.pilotJSON['Setups']
                           [self.setup]['Commands']['Defaults'].split(',')]
        else:
          self.commands = [str(pv).strip() for pv in self.pilotJSON['Setups'][self.setup]['Commands']['Defaults']]
      except KeyError:
        try:
          if isinstance(self.pilotJSON['Setups']['Defaults']['Commands'][self.gridCEType], basestring):
            self.commands = [str(pv).strip() for pv in self.pilotJSON['Setups']
                             ['Defaults']['Commands'][self.gridCEType].split(',')]
          else:
            self.commands = [str(pv).strip() for pv in self.pilotJSON['Setups']
                             ['Defaults']['Commands'][self.gridCEType]]
        except KeyError:
          try:
            if isinstance(self.pilotJSON['Defaults']['Commands']['Defaults'], basestring):
              self.commands = [str(pv).strip() for pv in self.pilotJSON['Defaults']['Commands']['Defaults'].split(',')]
            else:
              self.commands = [str(pv).strip() for pv in self.pilotJSON['Defaults']['Commands']['Defaults']]
          except KeyError:
            pass
    self.log.debug("Commands: %s" % self.commands)

    # CommandExtensions
    # pilotSynchronizer() can publish this as a comma separated list. We are ready for that.
    try:
      if isinstance(self.pilotJSON['Setups'][self.setup]['CommandExtensions'], basestring):  # In the specific setup?
        self.commandExtensions = [str(pv).strip() for pv in self.pilotJSON['Setups']
                                  [self.setup]['CommandExtensions'].split(',')]
      else:
        self.commandExtensions = [str(pv).strip() for pv in self.pilotJSON['Setups'][self.setup]['CommandExtensions']]
    except KeyError:
      try:
        if isinstance(
                self.pilotJSON['Setups']['Defaults']['CommandExtensions'],
                basestring):  # Or in the defaults section?
          self.commandExtensions = [str(pv).strip() for pv in self.pilotJSON['Setups']
                                    ['Defaults']['CommandExtensions'].split(',')]
        else:
          self.commandExtensions = [str(pv).strip() for pv in self.pilotJSON['Setups']['Defaults']['CommandExtensions']]
      except KeyError:
        pass
    self.log.debug("Commands extesions: %s" % self.commandExtensions)

    # CS URL(s)
    # pilotSynchronizer() can publish this as a comma separated list. We are ready for that
    try:
      if isinstance(self.pilotJSON['ConfigurationServers'],
                    basestring):  # Generic, there may also be setup-specific ones
        self.configServer = ','.join([str(pv).strip() for pv in self.pilotJSON['ConfigurationServers'].split(',')])
      else:  # it's a list, we suppose
        self.configServer = ','.join([str(pv).strip() for pv in self.pilotJSON['ConfigurationServers']])
    except KeyError:
      pass
    try:  # now trying to see if there is setup-specific ones
      if isinstance(self.pilotJSON['Setups'][self.setup]['ConfigurationServer'], basestring):  # In the specific setup?
        self.configServer = ','.join([str(pv).strip() for pv in self.pilotJSON['Setups']
                                      [self.setup]['ConfigurationServer'].split(',')])
      else:  # it's a list, we suppose
        self.configServer = ','.join([str(pv).strip()
                                      for pv in self.pilotJSON['Setups'][self.setup]['ConfigurationServer']])
    except KeyError:  # and if it doesn't exist
      try:
        if isinstance(self.pilotJSON['Setups']['Defaults']['ConfigurationServer'],
                      basestring):  # Is there one in the defaults section?
          self.configServer = ','.join([str(pv).strip() for pv in self.pilotJSON['Setups']
                                        ['Defaults']['ConfigurationServer'].split(',')])
        else:  # it's a list, we suppose
          self.configServer = ','.join([str(pv).strip()
                                        for pv in self.pilotJSON['Setups']['Defaults']['ConfigurationServer']])
      except KeyError:
        pass
    self.log.debug("CS list: %s" % self.configServer)

    # Version
    # There may be a list of versions specified (in a string, comma separated). We just want the first one.
    dVersion = None
    try:
      dVersion = [dv.strip() for dv in self.pilotJSON['Setups'][self.setup]['Version'].split(',', 1)]
    except KeyError:
      try:
        dVersion = [dv.strip() for dv in self.pilotJSON['Setups']['Defaults']['Version'].split(',', 1)]
      except KeyError:
        self.log.warn("Could not find a version in the JSON file configuration")
    if dVersion is not None:
      self.releaseVersion = str(dVersion[0])
    self.log.debug("Version: %s -> %s" % (dVersion, self.releaseVersion))

    try:
      self.releaseProject = str(self.pilotJSON['Setups'][self.setup]['Project'])
    except KeyError:
      try:
        self.releaseProject = str(self.pilotJSON['Setups']['Defaults']['Project'])
      except KeyError:
        pass
    self.log.debug("Release project: %s" % self.releaseProject)
