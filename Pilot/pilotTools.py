""" A set of common tools to be used in pilot commands
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

__RCSID__ = "$Id$"

import sys
import os
import pickle
import getopt
import imp
import json
import re
import select
import signal
import subprocess
import ssl
import fcntl
from datetime import datetime
from functools import partial
from distutils.version import LooseVersion

############################
# python 2 -> 3 "hacks"
try:
    from urllib.request import urlopen
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
except ImportError:
    from urllib2 import urlopen, HTTPError, URLError
    from urllib import urlencode

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

try:
    basestring  # pylint: disable=used-before-assignment
except NameError:
    basestring = str

try:
    from Pilot.proxyTools import getVO
except ImportError:
    from proxyTools import getVO

# Utilities functions


def parseVersion(releaseVersion, useLegacyStyle):
    """Convert the releaseVersion into a legacy or PEP-440 style string

    :param str releaseVersion: The software version to use
    :param bool useLegacyStyle: True to return a vXrY(pZ)(-preN) style version else vX.Y.ZaN
    """
    VERSION_PATTERN = re.compile(r"^(?:v)?(\d+)[r\.](\d+)(?:[p\.](\d+))?(?:(?:-pre|a)?(\d+))?$")

    match = VERSION_PATTERN.match(releaseVersion)
    # If the regex fails just return the original version
    if not match:
        return releaseVersion
    major, minor, patch, pre = match.groups()
    if useLegacyStyle:
        version = "v" + major + "r" + minor
        if patch and int(patch):
            version += "p" + patch
        if pre:
            version += "-pre" + pre
    else:
        version = major + "." + minor
        version += "." + (patch or "0")
        if pre:
            version += "a" + pre
    return version


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
        pythonpath = os.getenv("PYTHONPATH", "").split(":")
        print("Directories in PYTHONPATH:", pythonpath)
        for p in pythonpath:
            if p == "":
                continue
            try:
                if os.path.normpath(p) in sys.path:
                    # In case a given directory is twice in PYTHONPATH it has to removed only once
                    sys.path.remove(os.path.normpath(p))
            except Exception as x:
                print(x)
                print("[EXCEPTION-info] Failing path:", p, os.path.normpath(p))
                print("[EXCEPTION-info] sys.path:", sys.path)
                raise x
    except Exception as x:
        print(x)
        print("[EXCEPTION-info] sys.executable:", sys.executable)
        print("[EXCEPTION-info] sys.version:", sys.version)
        print("[EXCEPTION-info] os.uname():", os.uname())
        raise x


def alarmTimeoutHandler(*args):
    raise Exception("Timeout")


def retrieveUrlTimeout(url, fileName, log, timeout=0):
    """
    Retrieve remote url to local file, with timeout wrapper
    """
    urlData = ""
    if timeout:
        signal.signal(signal.SIGALRM, alarmTimeoutHandler)
        # set timeout alarm
        signal.alarm(timeout + 5)
    try:
        remoteFD = urlopen(url)
        expectedBytes = 0
        # Sometimes repositories do not return Content-Length parameter
        try:
            expectedBytes = int(remoteFD.info()["Content-Length"])
        except Exception:
            expectedBytes = 0
        data = remoteFD.read()
        if fileName:
            with open(fileName, "wb") as localFD:
                localFD.write(data)
        else:
            urlData += data
        remoteFD.close()
        if len(data) != expectedBytes and expectedBytes > 0:
            log.error("URL retrieve: expected size does not match the received one")
            return False

        if timeout:
            signal.alarm(0)
        if fileName:
            return True
        return urlData

    except HTTPError as x:
        if x.code == 404:
            log.error("URL retrieve: %s does not exist" % url)
            if timeout:
                signal.alarm(0)
            return False
    except URLError:
        log.error('Timeout after %s seconds on transfer request for "%s"' % (str(timeout), url))
        return False
    except Exception as x:
        if x == "Timeout":
            log.error('Timeout after %s seconds on transfer request for "%s"' % (str(timeout), url))
        if timeout:
            signal.alarm(0)
        raise x


class ObjectLoader(object):
    """Simplified class for loading objects from a DIRAC installation.

    Example:

    ol = ObjectLoader()
    object, modulePath = ol.loadObject( 'pilot', 'LaunchAgent' )
    """

    def __init__(self, baseModules, log):
        """init"""
        self.__rootModules = baseModules
        self.log = log

    def loadModule(self, modName, hideExceptions=False):
        """Auto search which root module has to be used"""
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
        """Internal function to load modules"""
        if isinstance(modName, basestring):
            modName = modName.split(".")
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
        return self.__recurseImport(modName[1:], impModule, hideExceptions=hideExceptions)

    def loadObject(self, package, moduleName, command):
        """Load an object from inside a module"""
        loadModuleName = "%s.%s" % (package, moduleName)
        module, parentPath = self.loadModule(loadModuleName)
        if module is None:
            return None, None
        try:
            commandObj = getattr(module, command)
            return commandObj, os.path.join(parentPath, moduleName)
        except AttributeError as e:
            self.log.error("Exception: %s" % str(e))
            return None, None


def getCommand(params, commandName, log):
    """Get an instantiated command object for execution.
    Commands are looked in the following modules in the order:

    1. <CommandExtension>Commands
    2. pilotCommands
    """
    extensions = params.commandExtensions
    modules = [m + "Commands" for m in extensions + ["pilot"]]
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

    # No command could be instantiated
    return None, None


class Logger(object):
    """Basic logger object, for use inside the pilot. Just using print."""

    def __init__(self, name="Pilot", debugFlag=False, pilotOutput="pilot.out"):
        self.debugFlag = debugFlag
        self.name = name
        self.out = pilotOutput
        self._headerTemplate = "{datestamp} {{level}} [{name}] {{message}}"

    @property
    def messageTemplate(self):
        """
        Message template in ISO-8601 format.

        :return: template string
        :rtype: str
        """
        return self._headerTemplate.format(
            datestamp=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            name=self.name,
        )

    def __outputMessage(self, msg, level, header):
        if self.out:
            with open(self.out, "a") as outputFile:
                for _line in str(msg).split("\n"):
                    if header:
                        outLine = self.messageTemplate.format(level=level, message=_line)
                        print(outLine)
                        if self.out:
                            outputFile.write(outLine + "\n")
                    else:
                        print(_line)
                        outputFile.write(_line + "\n")

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


class RemoteLogger(Logger):
    """
    The remote logger object, for use inside the pilot. It prints messages,
    but can be also used to send messages to an external service.
    """

    def __init__(
        self,
        url,
        name="Pilot",
        debugFlag=False,
        pilotOutput="pilot.out",
        isPilotLoggerOn=True,
        pilotUUID="unknown",
        setup="DIRAC-Certification",
    ):
        """
        c'tor
        If flag PilotLoggerOn is not set, the logger will behave just like
        the original Logger object, that means it will just print logs locally on the screen
        """
        super(RemoteLogger, self).__init__(name, debugFlag, pilotOutput)
        self.url = url
        self.pilotUUID = pilotUUID
        self.isPilotLoggerOn = isPilotLoggerOn
        sendToURL = partial(sendMessage, url, pilotUUID, "sendMessage")
        self.buffer = FixedSizeBuffer(sendToURL)

    def debug(self, msg, header=True, sendPilotLog=False):
        super(RemoteLogger, self).debug(msg, header)
        if (
            self.isPilotLoggerOn and self.debugFlag
        ):  # the -d flag activates this debug flag in CommandBase via PilotParams
            self.sendMessage(self.messageTemplate.format(level="DEBUG", message=msg))

    def error(self, msg, header=True, sendPilotLog=False):
        super(RemoteLogger, self).error(msg, header)
        if self.isPilotLoggerOn:
            self.sendMessage(self.messageTemplate.format(level="ERROR", message=msg))

    def warn(self, msg, header=True, sendPilotLog=False):
        super(RemoteLogger, self).warn(msg, header)
        if self.isPilotLoggerOn:
            self.sendMessage(self.messageTemplate.format(level="WARNING", message=msg))

    def info(self, msg, header=True, sendPilotLog=False):
        super(RemoteLogger, self).info(msg, header)
        if self.isPilotLoggerOn:
            self.sendMessage(self.messageTemplate.format(level="INFO", message=msg))

    def sendMessage(self, msg):
        """
        Buffered message sender.

        :param msg: message to send
        :type msg: str
        :return: None
        :rtype: None
        """
        try:
            self.buffer.write(msg + "\n")
        except Exception as err:
            super(RemoteLogger, self).error("Message not sent")
            super(RemoteLogger, self).error(str(err))


class FixedSizeBuffer(object):
    """
    A buffer with a (preferred) fixed number of lines.
    Once it's full, a message is sent to a remote server and the buffer is renewed.
    """

    def __init__(self, senderFunc, bufsize=10):
        """
        Constructor.

        :param senderFunc: a function used to send a message
        :type senderFunc: func
        :param bufsize: size of the buffer (in lines)
        :type bufsize: int
        """
        self.output = StringIO()
        self.bufsize = bufsize
        self.__nlines = 0
        self.senderFunc = senderFunc

    def write(self, text):
        """
        Write text to a string buffer. Newline characters are counted and number of lines in the buffer
        is increased accordingly.

        :param text: text string to write
        :type text: str
        :return: None
        :rtype: None
        """
        # reopen the buffer in a case we had to flush a partially filled buffer
        if self.output.closed:
            self.output = StringIO()
        self.output.write(text)
        self.__nlines += max(1, text.count("\n"))
        self.sendFullBuffer()

    def getValue(self):
        content = self.output.getvalue()
        return content

    def sendFullBuffer(self):
        """
        Get the buffer content, send a message, close the current buffer and re-create a new one for subsequent writes.

        """

        if self.__nlines >= self.bufsize:
            self.flush()
            self.output = StringIO()

    def flush(self):
        """
        Flush the buffer and send log records to a remote server. The buffer is closed as well.

        :return: None
        :rtype:  None
        """

        self.output.flush()
        buf = self.getValue()
        self.senderFunc(buf)
        self.__nlines = 0
        self.output.close()


def sendMessage(url, pilotUUID, method, rawMessage):
    """
    Invoke a remote method on a Tornado server and pass a JSON message to it.

    :param str url: Server URL
    :param str pilotUUID: pilot unique ID
    :param str method: a method to be invoked
    :param str rawMessage: a message to be sent, in JSON format
    :return: None.
    """
    message = json.dumps((json.dumps(rawMessage), pilotUUID))
    major, minor, micro, _, _ = sys.version_info
    if major >= 3:
        data = urlencode({"method": method, "args": message}).encode("utf-8")  # encode to bytes ! for python3
    else:
        data = urlencode({"method": method, "args": message})
    caPath = os.getenv("X509_CERT_DIR")
    cert = os.getenv("X509_USER_PROXY")

    context = ssl.create_default_context()
    context.load_verify_locations(capath=caPath)
    context.load_cert_chain(cert)
    res = urlopen(url, data, context=context)
    res.close()


class CommandBase(object):
    """CommandBase is the base class for every command in the pilot commands toolbox"""

    def __init__(self, pilotParams, dummy=""):
        """
        Defines the classic pilot logger and the pilot parameters.
        Debug level of the Logger is controlled by the -d flag in pilotParams.

        :param pilotParams: a dictionary of pilot parameters.
        :type pilotParams: dict
        :param dummy:
        """

        self.pp = pilotParams
        isPilotLoggerOn = pilotParams.pilotLogging
        self.debugFlag = pilotParams.debugFlag
        loggerURL = pilotParams.loggerURL

        if loggerURL is None:
            self.log = Logger(self.__class__.__name__, debugFlag=self.debugFlag)
        else:
            # remote logger
            self.log = RemoteLogger(
                loggerURL, self.__class__.__name__, pilotUUID=pilotParams.pilotUUID, debugFlag=self.debugFlag
            )

        self.log.isPilotLoggerOn = isPilotLoggerOn
        if self.debugFlag:
            self.log.setDebug()

        self.log.debug("Initialized command %s" % self.__class__.__name__)
        self.log.debug("pilotParams option list: %s" % self.pp.optList)
        self.cfgOptionDIRACVersion = self._getCFGOptionDIRACVersion()

    def _getCFGOptionDIRACVersion(self):
        """Convenience method.

        Reference vanilla DIRAC version from when we ask to use --cfg for cfg files

        For extensions: the only way to know the vanilla DIRAC version
        is to check releases.cfg. Not impossible, but cumbersome to do here.
        Extensions could replace this function.
        """
        if not self.pp.releaseProject:
            return LooseVersion(parseVersion("v7r0p29", self.pp.pythonVersion == "27"))
        # just a trick to always evaluate comparisons in pilotCommands to False
        return LooseVersion("z") if self.pp.pythonVersion == "27" else LooseVersion("1000")

    def executeAndGetOutput(self, cmd, environDict=None):
        """Execute a command on the worker node and get the output"""

        self.log.info("Executing command %s" % cmd)
        _p = subprocess.Popen(
            "%s" % cmd, shell=True, env=environDict, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=False
        )

        # Use non-blocking I/O on the process pipes
        for fd in [_p.stdout.fileno(), _p.stderr.fileno()]:
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        outData = ""
        while True:
            readfd, _, _ = select.select([_p.stdout, _p.stderr], [], [])
            dataWasRead = False
            for stream in readfd:
                outChunk = stream.read().decode("ascii", "replace")
                if not outChunk:
                    continue
                dataWasRead = True
                # Strip unicode replacement characters
                outChunk = str(outChunk.replace(u"\ufffd", ""))
                if stream == _p.stderr:
                    sys.stderr.write(outChunk)
                    sys.stderr.flush()
                else:
                    sys.stdout.write(outChunk)
                    sys.stdout.flush()
                    if hasattr(self.log, "buffer") and self.log.isPilotLoggerOn:
                        self.log.buffer.write(outChunk)
                    outData += outChunk
            # If no data was read on any of the pipes then the process has finished
            if not dataWasRead:
                break

        # Ensure output ends on a newline
        sys.stdout.write("\n")
        sys.stdout.flush()
        sys.stderr.write("\n")
        sys.stderr.flush()

        # return code
        returnCode = _p.wait()
        self.log.debug("Return code of %s: %d" % (cmd, returnCode))

        return (returnCode, outData)

    def exitWithError(self, errorCode):
        """Wrapper around sys.exit()"""
        self.log.info("List of child processes of current PID:")
        retCode, _outData = self.executeAndGetOutput(
            "ps --forest -o pid,%%cpu,%%mem,tty,stat,time,cmd -g %d" % os.getpid()
        )
        if retCode:
            self.log.error("Failed to issue ps [ERROR %d] " % retCode)
        sys.exit(errorCode)

    def forkAndExecute(self, cmd, logFile, environDict=None):
        """Fork and execute a command on the worker node"""

        self.log.info("Fork and execute command %s" % cmd)
        pid = os.fork()

        if pid != 0:
            # Still in the parent, return the subprocess ID
            return pid

        # The subprocess stdout/stderr will be written to logFile
        with open(logFile, "a+", 0) as fpLogFile:
            try:
                _p = subprocess.Popen(
                    "%s" % cmd, shell=True, env=environDict, close_fds=False, stdout=fpLogFile, stderr=fpLogFile
                )

                # return code
                returnCode = _p.wait()
                self.log.debug("Return code of %s: %d" % (cmd, returnCode))
            except BaseException:
                returnCode = 99

        sys.exit(returnCode)

    @property
    def releaseVersion(self):
        parsedVersion = parseVersion(self.pp.releaseVersion, self.pp.pythonVersion == "27")
        # strip what is not strictly the version number (e.g. if it is DIRAC[pilot]==7.3.4])
        return parsedVersion.split("==")[1] if "==" in parsedVersion else parsedVersion


class PilotParams(object):
    """Class that holds the structure with all the parameters to be used across all the commands"""

    def __init__(self):
        """c'tor

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
        self.commands = [
            "CheckWorkerNode",
            "InstallDIRAC",
            "ConfigureBasics",
            "CheckCECapabilities",
            "CheckWNCapabilities",
            "ConfigureSite",
            "ConfigureArchitecture",
            "ConfigureCPURequirements",
            "LaunchAgent",
        ]
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
        # maxNumberOfProcessors: the number of
        # processors allocated to the pilot which the pilot can allocate to one payload
        # used to set payloadProcessors unless other limits are reached (like the number of processors on the WN)
        self.maxNumberOfProcessors = 0
        self.minDiskSpace = 2560  # MB
        self.pythonVersion = "3"
        self.defaultsURL = None
        self.userGroup = ""
        self.userDN = ""
        self.maxCycles = 10
        self.pollingTime = 20
        self.stopOnApplicationFailure = True
        self.stopAfterFailedMatches = 10
        self.flavour = "DIRAC"
        self.pilotReference = ""
        self.releaseVersion = ""
        self.releaseProject = ""
        self.gateway = ""
        self.useServerCertificate = False
        self.pilotScriptName = ""
        self.genericOption = ""
        self.wnVO = ""  # for binding the resource (WN) to a specific VO
        # Some commands can define environment necessary to execute subsequent commands
        self.installEnv = os.environ
        # If DIRAC is preinstalled this file will receive the updates of the local configuration
        self.localConfigFile = "pilot.cfg"
        self.executeCmd = False
        self.configureScript = "dirac-configure"
        self.architectureScript = "dirac-platform"
        self.certsLocation = "%s/etc/grid-security" % self.workingDir
        self.pilotCFGFile = "pilot.json"
        self.pilotLogging = False
        self.loggerURL = None
        self.pilotUUID = "unknown"
        self.modules = ""  # see dirac-install "-m" option documentation
        self.userEnvVariables = ""  # see dirac-install "--userEnvVariables" option documentation
        self.pipInstallOptions = ""

        # Parameters that can be determined at runtime only
        self.queueParameters = {}  # from CE description
        self.jobCPUReq = 900  # HS06s, here just a random value

        # Set number of allocatable processors from MJF if available
        try:
            self.pilotProcessors = int(urlopen(os.path.join(os.environ["JOBFEATURES"], "allocated_cpu")).read())
        except Exception:
            self.pilotProcessors = 1

        # Pilot command options
        self.cmdOpts = (
            ("", "requiredTag=", "extra required tags for resource description"),
            ("a:", "gridCEType=", "Grid CE Type (CREAM etc)"),
            ("c", "cert", "Use server certificate instead of proxy"),
            ("d", "debug", "Set debug flag"),
            ("e:", "extraPackages=", "Extra packages to install (comma separated)"),
            ("g:", "loggerURL=", "Remote Logger service URL"),
            ("h", "help", "Show this help"),
            ("k", "keepPP", "Do not clear PYTHONPATH on start"),
            ("l:", "project=", "Project to install"),
            ("n:", "name=", "Set <Site> as Site Name"),
            ("o:", "option=", "Option=value to add"),
            ("m:", "maxNumberOfProcessors=", "specify a max number of processors to use by the payload inside a pilot"),
            ("", "modules=", 'for installing non-released code (see dirac-install "-m" option documentation)'),
            (
                "",
                "userEnvVariables=",
                'User-requested environment variables (comma-separated, name and value separated by ":::")',
            ),
            ("", "pipInstallOptions=", "Options to pip install"),
            ("r:", "release=", "DIRAC release to install"),
            ("s:", "section=", "Set base section for relative parsed options"),
            ("t:", "tag=", "extra tags for resource description"),
            ("u:", "url=", "Use <url> to download tarballs"),
            ("x:", "execute=", "Execute instead of JobAgent"),
            ("y:", "CEType=", "CE Type (normally InProcess)"),
            ("z", "pilotLogging", "Activate pilot logging system"),
            ("C:", "configurationServer=", "Configuration servers to use"),
            ("D:", "disk=", "Require at least <space> MB available"),
            ("E:", "commandExtensions=", "Python modules with extra commands"),
            ("F:", "pilotCFGFile=", "Specify pilot CFG file"),
            ("G:", "Group=", "DIRAC Group to use"),
            ("K:", "certLocation=", "Specify server certificate location"),
            ("M:", "MaxCycles=", "Maximum Number of JobAgent cycles to run"),
            ("", "PollingTime=", "JobAgent execution frequency"),
            ("", "StopOnApplicationFailure=", "Stop Job Agent when encounter an application failure"),
            ("", "StopAfterFailedMatches=", "Stop Job Agent after N failed matches"),
            ("N:", "Name=", "CE Name"),
            ("O:", "OwnerDN=", "Pilot OwnerDN (for private pilots)"),
            ("", "wnVO=", "Bind the resource (WN) to a VO"),
            ("P:", "pilotProcessors=", "Number of processors allocated to this pilot"),
            ("Q:", "Queue=", "Queue name"),
            ("R:", "reference=", "Use this pilot reference"),
            ("S:", "setup=", "DIRAC Setup to use"),
            ("T:", "CPUTime=", "Requested CPU Time"),
            ("V:", "installation=", "Installation configuration file"),
            ("W:", "gateway=", "Configure <gateway> as DIRAC Gateway during installation"),
            ("X:", "commands=", "Pilot commands to execute"),
            ("Z:", "commandOptions=", "Options parsed by command modules"),
            ("", "pythonVersion=", "Python version of DIRAC client to install"),
            ("", "defaultsURL=", "user-defined URL for global config"),
            ("", "pilotUUID=", "pilot UUID"),
        )

        # Possibly get Setup and JSON URL/filename from command line
        self.__initCommandLine1()

        # Get main options from the JSON file. Load JSON first to determine the format used.
        self.__loadJSON()
        if "Setups" in self.pilotJSON:
            self.__initJSON()
        else:
            self.__initJSON2()

        # Command line can override options from JSON
        self.__initCommandLine2()

    def __initCommandLine1(self):
        """Parses and interpret options on the command line: first pass (essential things)"""

        self.optList, __args__ = getopt.getopt(
            sys.argv[1:], "".join([opt[0] for opt in self.cmdOpts]), [opt[1] for opt in self.cmdOpts]
        )
        self.log.debug("Options list: %s" % self.optList)
        for o, v in self.optList:
            if o == "-N" or o == "--Name":
                self.ceName = v
            if o == "-Q" or o == "--Queue":
                self.queueName = v
            elif o == "-a" or o == "--gridCEType":
                self.gridCEType = v
            elif o == "-d" or o == "--debug":
                self.debugFlag = True
            elif o in ("-S", "--setup"):
                self.setup = v
            elif o == "-F" or o == "--pilotCFGFile":
                self.pilotCFGFile = v

    def __initCommandLine2(self):
        """
        Parses and interpret options on the command line: second pass
        (overriding discovered parameters, for tests/debug)
        """

        self.optList, __args__ = getopt.getopt(
            sys.argv[1:], "".join([opt[0] for opt in self.cmdOpts]), [opt[1] for opt in self.cmdOpts]
        )
        for o, v in self.optList:
            if o == "-E" or o == "--commandExtensions":
                self.commandExtensions = v.split(",")
            elif o == "-X" or o == "--commands":
                self.commands = v.split(",")
            elif o == "-Z" or o == "--commandOptions":
                for i in v.split(","):
                    self.commandOptions[i.split("=", 1)[0].strip()] = i.split("=", 1)[1].strip()
            elif o == "-e" or o == "--extraPackages":
                self.extensions = v.split(",")
            elif o == "-n" or o == "--name":
                self.site = v
            elif o == "-y" or o == "--CEType":
                self.ceType = v
            elif o == "-R" or o == "--reference":
                self.pilotReference = v
            elif o == "-k" or o == "--keepPP":
                self.keepPythonPath = True
            elif o in ("-C", "--configurationServer"):
                self.configServer = v
            elif o in ("-G", "--Group"):
                self.userGroup = v
            elif o in ("-x", "--execute"):
                self.executeCmd = v
            elif o in ("-O", "--OwnerDN"):
                self.userDN = v
            elif o == "--wnVO":
                self.wnVO = v
            elif o in ("-V", "--installation"):
                self.installation = v
            elif o == "-m" or o == "--maxNumberOfProcessors":
                self.maxNumberOfProcessors = int(v)
            elif o == "-D" or o == "--disk":
                try:
                    self.minDiskSpace = int(v)
                except ValueError:
                    pass
            elif o == "-r" or o == "--release":
                self.releaseVersion = v.split(",", 1)[0]
            elif o in ("-l", "--project"):
                self.releaseProject = v
            elif o in ("-W", "--gateway"):
                self.gateway = v
            elif o == "-c" or o == "--cert":
                self.useServerCertificate = True
            elif o == "-C" or o == "--certLocation":
                self.certsLocation = v
            elif o == "-M" or o == "--MaxCycles":
                try:
                    self.maxCycles = int(v)
                except ValueError:
                    pass
            elif o == "--PollingTime":
                try:
                    self.pollingTime = int(v)
                except ValueError:
                    pass
            elif o == "--StopOnApplicationFailure":
                self.stopOnApplicationFailure = v
            elif o == "--StopAfterFailedMatches":
                try:
                    self.stopAfterFailedMatches = int(v)
                except ValueError:
                    pass
            elif o in ("-T", "--CPUTime"):
                self.jobCPUReq = v
            elif o == "-P" or o == "--pilotProcessors":
                try:
                    self.pilotProcessors = int(v)
                except BaseException:
                    pass
            elif o == "-z" or o == "--pilotLogging":
                self.pilotLogging = True
            elif o == "-g" or o == "--loggerURL":
                self.loggerURL = v
            elif o == "--pilotUUID":
                self.pilotUUID = v
            elif o in ("-o", "--option"):
                self.genericOption = v
            elif o in ("-t", "--tag"):
                self.tags.append(v)
            elif o == "--requiredTag":
                self.reqtags.append(v)
            elif o == "--modules":
                self.modules = v
            elif o == "--userEnvVariables":
                self.userEnvVariables = v
            elif o == "--pipInstallOptions":
                self.pipInstallOptions = v
            elif o == "--pythonVersion":
                self.pythonVersion = v
            elif o == "--defaultsURL":
                self.defaultsURL = v

    def __loadJSON(self):
        """
        Load JSON file and return a dict content.

        :return:
        :rtype:
        """

        self.log.debug("JSON file loaded: %s" % self.pilotCFGFile)
        with open(self.pilotCFGFile, "r") as fp:
            # We save the parsed JSON in case pilot commands need it
            # to read their own options
            self.pilotJSON = json.load(fp)

    def __initJSON2(self):
        """
        Retrieve pilot parameters from the content of JSON dict using a new format, which closer follows the
        CS Operations section. The CE JSON section remains the same. The first difference is present in Commands,
        followed by a new VO-specific sections.

        :return: None
        """

        self.__ceType()
        # Commands first. In the new format they can be either in a self.setup/Pilot section in Defaults/Pilot
        # section or in a VO section (voname/self.setup/Pilot). They are published as a string.
        pilotOptions = self.getPilotOptionsDict()
        # remote logging
        self.pilotLogging = pilotOptions.get("RemoteLogging", self.pilotLogging)
        self.loggerURL = pilotOptions.get("RemoteLoggerURL")
        pilotLogLevel = pilotOptions.get("PilotLogLevel", "INFO")
        if pilotLogLevel.lower() == "debug":
            self.debugFlag = True
        self.log.debug("JSON: Remote logging: %s" % self.pilotLogging)
        self.log.debug("JSON: Remote logging URL: %s" % self.loggerURL)
        self.log.debug("JSON: Remote/local logging debug flag: %s" % self.debugFlag)

        # CE type if present, then Defaults, otherwise as defined in the code:
        if "Commands" in pilotOptions:
            for key in [self.gridCEType, "Defaults"]:
                commands = pilotOptions["Commands"].get(key)
                if commands is not None:
                    self.commands = [elem.strip() for elem in commands.split(",")]
                    self.log.debug("Selecting commands from JSON for Grid CE type %s" % key)
                    break
        else:
            key = "CodeDefaults"

        self.log.debug("Commands[%s]: %s" % (key, self.commands))

        # Command extensions for the commands above:
        commandExtOptions = pilotOptions.get("CommandExtensions")
        if commandExtOptions:
            self.commandExtensions = [elem.strip() for elem in commandExtOptions.split(",")]
        # Configuration server (the synchroniser looks into gConfig.getServersList(), as before
        # the generic one (a list):
        self.configServer = ",".join([str(pv).strip() for pv in self.pilotJSON["ConfigurationServers"]])

        # version(a comma separated values in a string). We take the first one. (the default value defined in the code)
        dVersion = pilotOptions.get("Version", self.releaseVersion)
        if dVersion:
            dVersion = [dv.strip() for dv in dVersion.split(",", 1)]
            self.releaseVersion = str(dVersion[0])
        else:
            self.log.warn("Could not find a version in the JSON file configuration")

        self.log.debug("Version: %s -> (release) %s" % (str(dVersion), self.releaseVersion))

        self.releaseProject = pilotOptions.get("Project", self.releaseProject)  # default from the code.
        self.log.debug("Release project: %s" % self.releaseProject)

    def getPilotOptionsDict(self):
        """
        Get pilot option dictionary by searching paths in a certain order (commands, logging etc.).

        :return: option dict
        :rtype: dict
        """

        return self.__getOptionForPaths(self.__getSearchPaths(), self.pilotJSON)

    def __getVOFromProxy(self):
        """
        Get a VO from a proxy. In case of problems return a value 'unknown", which would get pilot logging
        properties from a Defaults section of the CS.

        :return: VO name
        :rtype: str
        """

        cert = os.getenv("X509_USER_PROXY")
        vo = "unknown"
        if cert:
            try:
                with open(cert, "rb") as fp:
                    vo = getVO(fp.read())
            except IOError as err:
                self.log.error("Could not read a proxy, setting vo to 'unknown': ", os.strerror(err.errno))
        else:
            self.log.error("Could not locate a proxy via X509_USER_PROXY, setting vo to 'unknown' ")
        return vo

    def __getSearchPaths(self):
        """
        Paths to search for a given VO

        :return: list paths to search in JSON derived dict.
        """

        vo = self.__getVOFromProxy()
        paths = [
            "/Defaults/Pilot",
            "/%s/Pilot" % self.setup,
            "/%s/Defaults/Pilot" % vo,
            "/%s/%s/Pilot" % (vo, self.setup),
        ]

        return paths

    def __getOptionForPaths(self, paths, inDict):
        """
        Get the preferred option from an input dict passed on a path list. It modifies the inDict.

        :param list paths: list of paths to walk through to get a preferred option. The option in
        the last path has preference over earlier options.
        :param dict inDict:
        :return: dict
        """

        outDict = {}
        for path in paths:
            target = inDict
            for elem in path.strip("/").split("/"):
                target = target.setdefault(elem, {})
            outDict.update(target)
        return outDict

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

        The file must contain at least the Defaults section. Missing values are taken from the Defaults setup."""

        self.__ceType()

        # Commands first
        # FIXME: pilotSynchronizer() should publish these as comma-separated lists. We are ready for that.
        try:
            if isinstance(self.pilotJSON["Setups"][self.setup]["Commands"][self.gridCEType], basestring):
                self.commands = [
                    str(pv).strip()
                    for pv in self.pilotJSON["Setups"][self.setup]["Commands"][self.gridCEType].split(",")
                ]
            else:
                self.commands = [
                    str(pv).strip() for pv in self.pilotJSON["Setups"][self.setup]["Commands"][self.gridCEType]
                ]
        except KeyError:
            try:
                if isinstance(self.pilotJSON["Setups"][self.setup]["Commands"]["Defaults"], basestring):
                    self.commands = [
                        str(pv).strip()
                        for pv in self.pilotJSON["Setups"][self.setup]["Commands"]["Defaults"].split(",")
                    ]
                else:
                    self.commands = [
                        str(pv).strip() for pv in self.pilotJSON["Setups"][self.setup]["Commands"]["Defaults"]
                    ]
            except KeyError:
                try:
                    if isinstance(self.pilotJSON["Setups"]["Defaults"]["Commands"][self.gridCEType], basestring):
                        self.commands = [
                            str(pv).strip()
                            for pv in self.pilotJSON["Setups"]["Defaults"]["Commands"][self.gridCEType].split(",")
                        ]
                    else:
                        self.commands = [
                            str(pv).strip() for pv in self.pilotJSON["Setups"]["Defaults"]["Commands"][self.gridCEType]
                        ]
                except KeyError:
                    try:
                        if isinstance(self.pilotJSON["Defaults"]["Commands"]["Defaults"], basestring):
                            self.commands = [
                                str(pv).strip() for pv in self.pilotJSON["Defaults"]["Commands"]["Defaults"].split(",")
                            ]
                        else:
                            self.commands = [
                                str(pv).strip() for pv in self.pilotJSON["Defaults"]["Commands"]["Defaults"]
                            ]
                    except KeyError:
                        pass
        self.log.debug("Commands: %s" % self.commands)

        # CommandExtensions
        # pilotSynchronizer() can publish this as a comma separated list. We are ready for that.
        try:
            if isinstance(
                self.pilotJSON["Setups"][self.setup]["CommandExtensions"], basestring
            ):  # In the specific setup?
                self.commandExtensions = [
                    str(pv).strip() for pv in self.pilotJSON["Setups"][self.setup]["CommandExtensions"].split(",")
                ]
            else:
                self.commandExtensions = [
                    str(pv).strip() for pv in self.pilotJSON["Setups"][self.setup]["CommandExtensions"]
                ]
        except KeyError:
            try:
                if isinstance(
                    self.pilotJSON["Setups"]["Defaults"]["CommandExtensions"], basestring
                ):  # Or in the defaults section?
                    self.commandExtensions = [
                        str(pv).strip() for pv in self.pilotJSON["Setups"]["Defaults"]["CommandExtensions"].split(",")
                    ]
                else:
                    self.commandExtensions = [
                        str(pv).strip() for pv in self.pilotJSON["Setups"]["Defaults"]["CommandExtensions"]
                    ]
            except KeyError:
                pass
        self.log.debug("Commands extesions: %s" % self.commandExtensions)

        # CS URL(s)
        # pilotSynchronizer() can publish this as a comma separated list. We are ready for that
        try:
            if isinstance(
                self.pilotJSON["ConfigurationServers"], basestring
            ):  # Generic, there may also be setup-specific ones
                self.configServer = ",".join(
                    [str(pv).strip() for pv in self.pilotJSON["ConfigurationServers"].split(",")]
                )
            else:  # it's a list, we suppose
                self.configServer = ",".join([str(pv).strip() for pv in self.pilotJSON["ConfigurationServers"]])
        except KeyError:
            pass
        try:  # now trying to see if there is setup-specific ones
            if isinstance(
                self.pilotJSON["Setups"][self.setup]["ConfigurationServer"], basestring
            ):  # In the specific setup?
                self.configServer = ",".join(
                    [str(pv).strip() for pv in self.pilotJSON["Setups"][self.setup]["ConfigurationServer"].split(",")]
                )
            else:  # it's a list, we suppose
                self.configServer = ",".join(
                    [str(pv).strip() for pv in self.pilotJSON["Setups"][self.setup]["ConfigurationServer"]]
                )
        except KeyError:  # and if it doesn't exist
            try:
                if isinstance(
                    self.pilotJSON["Setups"]["Defaults"]["ConfigurationServer"], basestring
                ):  # Is there one in the defaults section?
                    self.configServer = ",".join(
                        [
                            str(pv).strip()
                            for pv in self.pilotJSON["Setups"]["Defaults"]["ConfigurationServer"].split(",")
                        ]
                    )
                else:  # it's a list, we suppose
                    self.configServer = ",".join(
                        [str(pv).strip() for pv in self.pilotJSON["Setups"]["Defaults"]["ConfigurationServer"]]
                    )
            except KeyError:
                pass
        self.log.debug("CS list: %s" % self.configServer)

        # Version
        # There may be a list of versions specified (in a string, comma separated). We just want the first one.
        dVersion = None
        try:
            dVersion = [dv.strip() for dv in self.pilotJSON["Setups"][self.setup]["Version"].split(",", 1)]
        except KeyError:
            try:
                dVersion = [dv.strip() for dv in self.pilotJSON["Setups"]["Defaults"]["Version"].split(",", 1)]
            except KeyError:
                self.log.warn("Could not find a version in the JSON file configuration")
        if dVersion is not None:
            self.releaseVersion = str(dVersion[0])
        self.log.debug("Version: %s -> %s" % (dVersion, self.releaseVersion))

        try:
            self.releaseProject = str(self.pilotJSON["Setups"][self.setup]["Project"])
        except KeyError:
            try:
                self.releaseProject = str(self.pilotJSON["Setups"]["Defaults"]["Project"])
            except KeyError:
                pass
        self.log.debug("Release project: %s" % self.releaseProject)

    def __ceType(self):
        """
        Set CE type and setup.

        """
        self.log.debug("CE name: %s" % self.ceName)
        if self.ceName:
            # Try to get the site name and grid CEType from the CE name
            # GridCEType is like "CREAM" or "HTCondorCE" not "InProcess" etc
            try:
                self.site = str(self.pilotJSON["CEs"][self.ceName]["Site"])
            except KeyError:
                pass
            try:
                if not self.gridCEType:
                    # We don't override a grid CEType given on the command line!
                    self.gridCEType = str(self.pilotJSON["CEs"][self.ceName]["GridCEType"])
            except KeyError:
                pass
            # This LocalCEType is like 'InProcess' or 'Pool' or 'Pool/Singularity' etc.
            # It can be in the queue and/or the CE level
            try:
                self.ceType = str(self.pilotJSON["CEs"][self.ceName]["LocalCEType"])
            except KeyError:
                pass
            try:
                self.ceType = str(self.pilotJSON["CEs"][self.ceName][self.queueName]["LocalCEType"])
            except KeyError:
                pass

                self.log.debug("Setup: %s" % self.setup)
        if not self.setup:
            # We don't use the default to override an explicit value from command line!
            try:
                self.setup = str(self.pilotJSON["DefaultSetup"])
            except KeyError:
                pass
