""" Definitions of a standard set of pilot commands

    Each command is represented by a class inheriting from CommandBase class.
    The command class constructor takes PilotParams object which is a data
    structure which keeps common parameters across all the pilot commands.

    The constructor must call the superclass constructor with the PilotParams
    object and the command name as arguments, e.g.::

        class InstallDIRAC(CommandBase):

          def __init__(self, pilotParams):
            CommandBase.__init__(self, pilotParams, 'Install')
            ...

    The command class must implement execute() method for the actual command
    execution.
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

__RCSID__ = "$Id$"

import sys
import os
import time
import stat
import socket
import filecmp
import shutil
from collections import Counter
from distutils.version import LooseVersion

############################
# python 2 -> 3 "hacks"
try:
    # For Python 3.0 and later
    from http.client import HTTPSConnection
except ImportError:
    # Fall back to Python 2
    from httplib import HTTPSConnection

try:
    from shlex import quote
except ImportError:
    from pipes import quote

try:
    from Pilot.pilotTools import CommandBase, retrieveUrlTimeout, sendMessage
except ImportError:
    from pilotTools import CommandBase, retrieveUrlTimeout, sendMessage
############################


def logFinalizer(func):
    """
    PilotCammand decorator. It marks a log file as final so no more messages should be written to it .
    Finalising is triggered by a return statement or any sys.exit() call, so a file might be incomplete
    if a command throws SystemExit exception with a code =! 0.

    :param func: method to be decorated
    :type func: method object
    :return: None
    :rtype: None
    """

    def wrapper(self):
        if not self.log.isPilotLoggerOn:
            self.log.debug("Remote logger is not active, no log flushing performed")
            return func(self)

        try:
            return func(self)
        except SystemExit as exCode:  # or Exception ?
            pRef = self.pp.pilotReference
            self.log.info(
                "Flushing the remote logger buffer for pilot on sys.exit(): %s (exit code:%s)" % (pRef, str(exCode))
            )
            raise
        finally:
            try:
                self.log.buffer.flush()  # flush the buffer unconditionally (on sys.exit() and return).
                sendMessage(self.log.url, self.log.pilotUUID, "finaliseLogs", {"retCode": str(exCode)})
            except Exception as exc:
                self.log.error("Remote logger couldn't be finalised %s " % str(exc))

    return wrapper


class GetPilotVersion(CommandBase):
    """Now just returns what was obtained by pilotTools.py"""

    def __init__(self, pilotParams):
        """c'tor"""
        super(GetPilotVersion, self).__init__(pilotParams)

    @logFinalizer
    def execute(self):
        """Just returns what was obtained by pilotTools.py"""
        return self.releaseVersion


class CheckWorkerNode(CommandBase):
    """Executes some basic checks"""

    def __init__(self, pilotParams):
        """c'tor"""
        super(CheckWorkerNode, self).__init__(pilotParams)

    @logFinalizer
    def execute(self):
        """Get host and local user info, and other basic checks, e.g. space available"""

        self.log.info("Uname      = %s" % " ".join(os.uname()))
        self.log.info("Host Name  = %s" % socket.gethostname())
        self.log.info("Host FQDN  = %s" % socket.getfqdn())
        self.log.info("WorkingDir = %s" % self.pp.workingDir)  # this could be different than rootPath

        fileName = "/etc/redhat-release"
        if os.path.exists(fileName):
            with open(fileName, "r") as f:
                self.log.info("RedHat Release = %s" % f.read().strip())

        fileName = "/etc/lsb-release"
        if os.path.isfile(fileName):
            with open(fileName, "r") as f:
                self.log.info("Linux release:\n%s" % f.read().strip())

        fileName = "/proc/cpuinfo"
        if os.path.exists(fileName):
            with open(fileName, "r") as f:
                cpu = f.readlines()
            models = Counter()
            freqs = Counter()
            for line in cpu:
                if line.find("cpu MHz") == 0:
                    freqs[line.split()[3]] += 1
                elif line.find("model name") == 0:
                    models[line.split(": ")[1].strip()] += 1
            for model, count in models.items():
                self.log.info("CPU (model)    = %s x %s" % (count, model))
            for freq, count in freqs.items():
                self.log.info("CPU (MHz)      = %s x %s" % (count, freq))

        fileName = "/proc/meminfo"
        if os.path.exists(fileName):
            with open(fileName, "r") as f:
                mem = f.readlines()
            totalMem = 0
            freeMem = 0
            for line in mem:
                if line.find("MemTotal:") == 0:
                    totalMem += int(line.split()[1])
                if line.find("MemFree:") == 0:
                    freeMem += int(line.split()[1])
                if line.find("Cached:") == 0:
                    freeMem += int(line.split()[1])
            if totalMem:
                self.log.info("Memory (kB)    = %s" % totalMem)
            if freeMem:
                self.log.info("FreeMem. (kB)  = %s" % freeMem)

        ###########################################################################
        # Disk space check

        # fs = os.statvfs( rootPath )
        fs = os.statvfs(self.pp.workingDir)
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
        diskSpace = int(fs[4] * fs[0] / 1024 / 1024)
        self.log.info("DiskSpace (MB) = %s" % diskSpace)

        if diskSpace < self.pp.minDiskSpace:
            self.log.error(
                "%s MB < %s MB, not enough local disk space available, exiting" % (diskSpace, self.pp.minDiskSpace)
            )
            sys.exit(1)


class InstallDIRAC(CommandBase):
    """Basically, this is used to call dirac-install with the passed parameters.

    It requires dirac-install script to be sitting in the same directory.
    """

    def __init__(self, pilotParams):
        """c'tor"""
        super(InstallDIRAC, self).__init__(pilotParams)
        self.installOpts = []
        self.pp.rootPath = self.pp.pilotRootPath
        self.installScriptName = "dirac-install.py"
        self.installScript = ""

    def _setInstallOptions(self):
        """Setup installation parameters"""

        for o, v in self.pp.optList:
            if o == "-d" or o == "--debug":
                self.installOpts.append("-d")
            elif o == "-e" or o == "--extraPackages":
                self.installOpts.append('-e "%s"' % v)
            elif o == "-u" or o == "--url":
                self.installOpts.append('-u "%s"' % v)
            elif o in ("-V", "--installation"):
                self.installOpts.append('-V "%s"' % v)

        if self.pp.releaseProject:
            self.installOpts.append("-l '%s'" % self.pp.releaseProject)
        if self.pp.modules:
            self.installOpts.append("-m '%s'" % self.pp.modules)
        if self.pp.userEnvVariables:
            self.installOpts.append("--userEnvVariables=%s" % self.pp.userEnvVariables)
        if self.pp.defaultsURL:
            self.installOpts.append("--defaultsURL=%s" % self.pp.defaultsURL)

        # The release version to install is a requirement
        self.installOpts.append('-r "%s"' % self.releaseVersion)

        self.log.debug("INSTALL OPTIONS [%s]" % ", ".join(map(str, self.installOpts)))

    def _locateInstallationScript(self):
        """Locate installation script"""
        installScript = ""
        for path in (self.pp.pilotRootPath, self.pp.originalRootPath, self.pp.rootPath):
            installScript = os.path.join(path, self.installScriptName)
            if os.path.isfile(installScript):
                break
        self.installScript = installScript

        if not os.path.isfile(installScript):
            self.log.error(
                "%s requires %s to exist in one of: %s, %s, %s"
                % (
                    self.pp.pilotScriptName,
                    self.installScriptName,
                    self.pp.pilotRootPath,
                    self.pp.originalRootPath,
                    self.pp.rootPath,
                )
            )
            sys.exit(1)

        try:
            # change permission of the script
            os.chmod(self.installScript, stat.S_IRWXU)
        except OSError:
            pass

    def _installDIRAC(self):
        """Install DIRAC or its extension, then parse the environment file created, and use it for subsequent calls"""
        # Installing
        installCmd = "%s %s" % (self.installScript, " ".join(self.installOpts))
        self.log.debug("Installing with: %s" % installCmd)

        # At this point self.pp.installEnv may coincide with os.environ
        # If extensions want to pass in a modified environment, it's easy to set self.pp.installEnv in an extended command
        retCode, _output = self.executeAndGetOutput(installCmd, self.pp.installEnv)

        if retCode:
            self.log.error("Could not make a proper DIRAC installation [ERROR %d]" % retCode)
            self.exitWithError(retCode)
        self.log.info("%s completed successfully" % self.installScriptName)

        # Parsing the bashrc then adding its content to the installEnv
        # at this point self.pp.installEnv may still coincide with os.environ
        retCode, output = self.executeAndGetOutput('bash -c "source bashrc && env"', self.pp.installEnv)
        if retCode:
            self.log.error("Could not parse the bashrc file [ERROR %d]" % retCode)
            self.exitWithError(retCode)
        for line in output.split("\n"):
            try:
                var, value = [vx.strip() for vx in line.split("=", 1)]
                if var == "_" or "SSH" in var or "{" in value or "}" in value:  # Avoiding useless/confusing stuff
                    continue
                self.pp.installEnv[var] = value
            except (IndexError, ValueError):
                continue
        # At this point self.pp.installEnv should contain all content of bashrc, sourced "on top" of (maybe) os.environ

    def _installDIRACpy3(self):
        """Install python3 version of DIRAC client"""

        # 1. Get the DIRACOS installer name
        # curl -O -L https://github.com/DIRACGrid/DIRACOS2/releases/latest/download/DIRACOS-Linux-$(uname -m).sh
        try:
            machine = os.uname().machine  # py3
        except AttributeError:
            machine = os.uname()[4]  # py2

        installerName = "DIRACOS-Linux-%s.sh" % machine

        # 2. Try to install from CVMFS

        if os.path.exists("diracos"):
            shutil.rmtree("diracos")

        retCode, _ = self.executeAndGetOutput(
            "bash /cvmfs/dirac.egi.eu/installSource/%s 2>&1" % installerName, self.pp.installEnv
        )
        if retCode:
            self.log.warn("Could not install DIRACOS from CVMFS [ERROR %d]" % retCode)

            # 3. Get the installer from GitHub otherwise
            if not retrieveUrlTimeout(
                "https://github.com/DIRACGrid/DIRACOS2/releases/latest/download/%s" % installerName,
                installerName,
                self.log,
            ):
                self.exitWithError(1)

            if os.path.exists("diracos"):
                shutil.rmtree("diracos")

            # 4. bash DIRACOS-Linux-$(uname -m).sh
            retCode, _ = self.executeAndGetOutput("bash %s 2>&1" % installerName, self.pp.installEnv)
            if retCode:
                self.log.error("Could not install DIRACOS [ERROR %d]" % retCode)
                self.exitWithError(retCode)

            # 5. rm DIRACOS-Linux-$(uname -m).sh
            if os.path.exists(installerName):
                os.remove(installerName)

        # is there some user-defined environment variable to add? then add them to diracosrc
        if self.pp.userEnvVariables:
            userEnvVariables = dict(
                zip(
                    [name.split(":::")[0] for name in self.pp.userEnvVariables.replace(" ", "").split(",")],
                    [value.split(":::")[1] for value in self.pp.userEnvVariables.replace(" ", "").split(",")],
                )
            )
            lines = []
            lines.extend(["# User-requested variables"])
            for envName, envValue in userEnvVariables.items():
                lines.extend(["export %s=%s" % (envName, envValue)])
            lines.append("")
            with open("diracos/diracosrc", "a") as diracosrc:
                diracosrc.write("\n".join(lines))

        # 6. source diracos/diracosrc then replace the content in installEnv
        retCode, output = self.executeAndGetOutput('bash -c "source diracos/diracosrc && env"', self.pp.installEnv)
        self.pp.installEnv = {}
        if retCode:
            self.log.error("Could not parse the diracos/diracosrc file [ERROR %d]" % retCode)
            self.exitWithError(retCode)
        for line in output.split("\n"):
            try:
                var, value = [vx.strip() for vx in line.split("=", 1)]
                if var == "_" or "SSH" in var or "{" in value or "}" in value:  # Avoiding useless/confusing stuff
                    continue
                self.pp.installEnv[var] = value
            except (IndexError, ValueError):
                continue

        # 7. pip install DIRAC[pilot]
        pipInstalling = "pip install %s " % self.pp.pipInstallOptions

        if self.pp.modules:  # install a non-released (on pypi) version
            for modules in self.pp.modules.split(","):
                branch = project = ""
                elements = modules.split(":::")
                if len(elements) == 3:
                    # e.g.: https://github.com/$DIRAC_test_repo/DIRAC.git:::DIRAC:::$DIRAC_test_branch
                    url, project, branch = elements
                elif len(elements) == 1:
                    url = elements[0]
                if url.endswith(".git"):
                    pipInstalling += "git+"
                pipInstalling += url
                if branch and project:
                    # e.g. git+https://github.com/fstagni/DIRAC.git@v7r2-fixes33#egg=DIRAC[pilot]
                    pipInstalling += "@%s#egg=%s" % (branch, project)
                pipInstalling += "[pilot]"

                # pipInstalling = "pip install %s%s@%s#egg=%s[pilot]" % (prefix, url, branch, project)
                retCode, output = self.executeAndGetOutput(pipInstalling, self.pp.installEnv)
                if retCode:
                    self.log.error("Could not %s [ERROR %d]" % (pipInstalling, retCode))
                    self.exitWithError(retCode)
        else:
            # pip install DIRAC[pilot]==version ExtensionDIRAC[pilot]==version_ext
            if not self.releaseVersion or self.releaseVersion in ["master", "main", "integration"]:
                cmd = "%s %sDIRAC[pilot]" % (pipInstalling, self.pp.releaseProject)
            else:
                cmd = "%s %sDIRAC[pilot]==%s" % (pipInstalling, self.pp.releaseProject, self.releaseVersion)
            retCode, output = self.executeAndGetOutput(cmd, self.pp.installEnv)
            if retCode:
                self.log.error("Could not pip install %s [ERROR %d]" % (self.releaseVersion, retCode))
                self.exitWithError(retCode)

    @logFinalizer
    def execute(self):
        """What is called all the time"""
        if self.pp.pythonVersion == "27":
            self._setInstallOptions()
            self._locateInstallationScript()
            self._installDIRAC()
        else:  # python3 is requested
            self._installDIRACpy3()


class ConfigureBasics(CommandBase):
    """This command completes DIRAC installation.

    It calls dirac-configure to:

        * download, by default, the CAs
        * creates a standard or custom (defined by self.pp.localConfigFile) cfg file
          (by default 'pilot.cfg') to be used where all the pilot configuration is to be set, e.g.:
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

    def __init__(self, pilotParams):
        """c'tor"""
        super(ConfigureBasics, self).__init__(pilotParams)
        self.cfg = []

    @logFinalizer
    def execute(self):
        """What is called all the times.

        VOs may want to replace/extend the _getBasicsCFG and _getSecurityCFG functions
        """

        self._getBasicsCFG()
        self._getSecurityCFG()

        if self.pp.debugFlag:
            self.cfg.append("-ddd")
        if self.pp.localConfigFile:
            self.cfg.append("-O %s" % self.pp.localConfigFile)  # here, only as output

        configureCmd = "%s %s" % (self.pp.configureScript, " ".join(self.cfg))

        retCode, _configureOutData = self.executeAndGetOutput(configureCmd, self.pp.installEnv)

        if retCode:
            self.log.error("Could not configure DIRAC basics [ERROR %d]" % retCode)
            self.exitWithError(retCode)

        # Create etc/dirac.cfg if it's missing and safe to do so
        if not os.path.exists("etc/dirac.cfg"):
            symlink_conf = False
            # If etc exists, check it's a normal dir
            # otherwise, create etc dir
            if os.path.exists("etc"):
                if os.path.isdir("etc"):
                    symlink_conf = True
            else:
                os.mkdir("etc", 0o755)
                symlink_conf = True
            # Create the dirac.cfg in the etc dir
            if symlink_conf:
                os.symlink(os.path.join("..", self.pp.localConfigFile), "etc/dirac.cfg")

    def _getBasicsCFG(self):
        """basics (needed!)"""
        self.cfg.append('-S "%s"' % self.pp.setup)
        if self.pp.configServer:
            self.cfg.append('-C "%s"' % self.pp.configServer)
        if self.pp.releaseProject:
            self.cfg.append('-e "%s"' % self.pp.releaseProject)
            self.cfg.append("-o /LocalSite/ReleaseProject=%s" % self.pp.releaseProject)
        if self.pp.gateway:
            self.cfg.append('-W "%s"' % self.pp.gateway)
        if self.pp.userGroup:
            self.cfg.append('-o /AgentJobRequirements/OwnerGroup="%s"' % self.pp.userGroup)
        if self.pp.userDN:
            self.cfg.append('-o /AgentJobRequirements/OwnerDN="%s"' % self.pp.userDN)
        self.cfg.append("-o /LocalSite/ReleaseVersion=%s" % self.releaseVersion)

        if self.pp.wnVO:
            self.cfg.append('-o "/Resources/Computing/CEDefaults/VirtualOrganization=%s"' % self.pp.wnVO)

    def _getSecurityCFG(self):
        """Nothing specific by default, but need to know host cert and key location in case they are needed"""
        if self.pp.useServerCertificate:
            self.cfg.append("--UseServerCertificate")
            self.cfg.append("-o /DIRAC/Security/CertFile=%s/hostcert.pem" % self.pp.certsLocation)
            self.cfg.append("-o /DIRAC/Security/KeyFile=%s/hostkey.pem" % self.pp.certsLocation)


class CheckCECapabilities(CommandBase):
    """Used to get CE tags and other relevant parameters."""

    def __init__(self, pilotParams):
        """c'tor"""
        super(CheckCECapabilities, self).__init__(pilotParams)

        # this variable contains the options that are passed to dirac-configure,
        # and that will fill the local dirac.cfg file
        self.cfg = []

    @logFinalizer
    def execute(self):
        """Setup CE/Queue Tags and other relevant parameters."""

        if self.pp.useServerCertificate:
            self.cfg.append("-o  /DIRAC/Security/UseServerCertificate=yes")
        if self.pp.localConfigFile:
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                self.cfg.append("--cfg")
            self.cfg.append(self.pp.localConfigFile)  # this file is as input

        # Get the resource description as defined in its configuration
        checkCmd = "dirac-resource-get-parameters -S %s -N %s -Q %s %s -d" % (
            self.pp.site,
            self.pp.ceName,
            self.pp.queueName,
            " ".join(self.cfg),
        )
        retCode, resourceDict = self.executeAndGetOutput(checkCmd, self.pp.installEnv)
        if retCode:
            self.log.error("Could not get resource parameters [ERROR %d]" % retCode)
            self.exitWithError(retCode)
        try:
            import json

            resourceDict = json.loads(resourceDict.strip().split("\n")[-1])
        except ValueError:
            self.log.error("The pilot command output is not json compatible.")
            sys.exit(1)

        self.pp.queueParameters = resourceDict
        for queueParamName, queueParamValue in self.pp.queueParameters.items():
            if isinstance(queueParamValue, list):  # for the tags
                queueParamValue = ",".join([str(qpv).strip() for qpv in queueParamValue])
            self.cfg.append("-o /LocalSite/%s=%s" % (queueParamName, quote(queueParamValue)))

        # Pick up all the relevant resource parameters that will be used in the job matching
        if "WholeNode" in resourceDict:
            self.pp.tags.append("WholeNode")

        # Tags must be added to already defined tags if any
        if resourceDict.get("Tag"):
            self.pp.tags += resourceDict["Tag"]

        # RequiredTags are like Tags.
        if resourceDict.get("RequiredTag"):
            self.pp.reqtags += resourceDict["RequiredTag"]

        if self.cfg:
            self.cfg.append("-FDMH")

            if self.debugFlag:
                self.cfg.append("-ddd")

            configureCmd = "%s %s" % (self.pp.configureScript, " ".join(self.cfg))
            retCode, _configureOutData = self.executeAndGetOutput(configureCmd, self.pp.installEnv)
            if retCode:
                self.log.error("Could not configure DIRAC [ERROR %d]" % retCode)
                self.exitWithError(retCode)

        else:
            self.log.debug("No CE parameters (tags) defined for %s/%s" % (self.pp.ceName, self.pp.queueName))


class CheckWNCapabilities(CommandBase):
    """Used to get capabilities specific to the Worker Node. This command must be called
    after the CheckCECapabilities command
    """

    def __init__(self, pilotParams):
        """c'tor"""
        super(CheckWNCapabilities, self).__init__(pilotParams)
        self.cfg = []

    @logFinalizer
    def execute(self):
        """Discover NumberOfProcessors and RAM"""

        if self.pp.useServerCertificate:
            self.cfg.append("-o /DIRAC/Security/UseServerCertificate=yes")
        if self.pp.localConfigFile:
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                self.cfg.append("--cfg")
            self.cfg.append(self.pp.localConfigFile)  # this file is as input
        # Get the worker node parameters
        checkCmd = "dirac-wms-get-wn-parameters -S %s -N %s -Q %s %s -d" % (
            self.pp.site,
            self.pp.ceName,
            self.pp.queueName,
            " ".join(self.cfg),
        )
        retCode, result = self.executeAndGetOutput(checkCmd, self.pp.installEnv)
        if retCode:
            self.log.error("Could not get resource parameters [ERROR %d]" % retCode)
            self.exitWithError(retCode)

        try:
            result = result.strip().split("\n")[-1].split(" ")
            numberOfProcessorsOnWN = int(result[0])
            maxRAM = int(result[1])
            try:
                numberOfGPUs = int(result[2])
            except IndexError:
                numberOfGPUs = 0
        except ValueError:
            self.log.error("Wrong Command output %s" % result)
            sys.exit(1)

        # If NumberOfProcessors or MaxRAM are defined in the resource configuration, these
        # values are preferred

        # pilotProcessors is basically the number of processors this pilot is "managing"
        self.pp.pilotProcessors = numberOfProcessorsOnWN

        # payloadProcessors is the max number of processors used by the single payloads.
        # We store payloadProcessors in the global parameters so that other commands can more easily use it.
        # (MultiLaunchAgent is right now the only consumer)
        self.pp.payloadProcessors = 1
        if "WholeNode" in self.pp.tags:
            self.pp.payloadProcessors = self.pp.pilotProcessors
        if self.pp.maxNumberOfProcessors > 0:
            self.pp.payloadProcessors = min(self.pp.pilotProcessors, self.pp.maxNumberOfProcessors)

        self.log.info("pilotProcessors = %d" % self.pp.pilotProcessors)
        self.log.info("payloadProcessors = %d" % self.pp.payloadProcessors)
        self.cfg.append('-o "/Resources/Computing/CEDefaults/NumberOfProcessors=%d"' % self.pp.pilotProcessors)
        self.cfg.append('-o "/Resources/Computing/CEDefaults/NumberOfPayloadProcessors=%d"' % self.pp.payloadProcessors)

        maxRAM = self.pp.queueParameters.get("MaxRAM", maxRAM)
        if maxRAM:
            try:
                self.cfg.append('-o "/Resources/Computing/CEDefaults/MaxRAM=%d"' % int(maxRAM))
            except ValueError:
                self.log.warn("MaxRAM is not an integer, will not fill it")
        else:
            self.log.warn("Could not retrieve MaxRAM, this parameter won't be filled")

        if numberOfGPUs:
            self.log.info("numberOfGPUs = %d" % int(numberOfGPUs))
            self.cfg.append('-o "/Resources/Computing/CEDefaults/NumberOfGPUs=%d"' % int(numberOfGPUs))

        # Add normal and required tags to the configuration
        self.pp.tags = list(set(self.pp.tags))
        if self.pp.tags:
            self.cfg.append('-o "/Resources/Computing/CEDefaults/Tag=%s"' % ",".join((str(x) for x in self.pp.tags)))

        self.pp.reqtags = list(set(self.pp.reqtags))
        if self.pp.reqtags:
            self.cfg.append(
                '-o "/Resources/Computing/CEDefaults/RequiredTag=%s"' % ",".join((str(x) for x in self.pp.reqtags))
            )

        if self.pp.useServerCertificate:
            self.cfg.append("-o /DIRAC/Security/UseServerCertificate=yes")

        if self.pp.localConfigFile:
            self.cfg.append("-O %s" % self.pp.localConfigFile)  # this file is as output
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                self.cfg.append("--cfg")
            self.cfg.append(self.pp.localConfigFile)  # this file is as input

        if self.debugFlag:
            self.cfg.append("-ddd")

        if self.cfg:
            self.cfg.append("-FDMH")

            configureCmd = "%s %s" % (self.pp.configureScript, " ".join(self.cfg))
            retCode, _configureOutData = self.executeAndGetOutput(configureCmd, self.pp.installEnv)
            if retCode:
                self.log.error("Could not configure DIRAC [ERROR %d]" % retCode)
                self.exitWithError(retCode)


class ConfigureSite(CommandBase):
    """Command to configure DIRAC sites using the pilot options"""

    def __init__(self, pilotParams):
        """c'tor"""
        super(ConfigureSite, self).__init__(pilotParams)

        # this variable contains the options that are passed to dirac-configure,
        # and that will fill the local dirac.cfg file
        self.cfg = []

    @logFinalizer
    def execute(self):
        """Setup configuration parameters"""
        self.__setFlavour()
        self.cfg.append("-o /LocalSite/GridMiddleware=%s" % self.pp.flavour)

        self.cfg.append('-n "%s"' % self.pp.site)
        self.cfg.append('-S "%s"' % self.pp.setup)

        self.cfg.append('-N "%s"' % self.pp.ceName)
        self.cfg.append("-o /LocalSite/GridCE=%s" % self.pp.ceName)
        self.cfg.append("-o /LocalSite/CEQueue=%s" % self.pp.queueName)
        if self.pp.ceType:
            self.cfg.append("-o /LocalSite/LocalCE=%s" % self.pp.ceType)

        for o, v in self.pp.optList:
            if o == "-o" or o == "--option":
                self.cfg.append('-o "%s"' % v)

        if self.pp.pilotReference != "Unknown":
            self.cfg.append("-o /LocalSite/PilotReference=%s" % self.pp.pilotReference)

        if self.pp.useServerCertificate:
            self.cfg.append("--UseServerCertificate")
            self.cfg.append("-o /DIRAC/Security/CertFile=%s/hostcert.pem" % self.pp.certsLocation)
            self.cfg.append("-o /DIRAC/Security/KeyFile=%s/hostkey.pem" % self.pp.certsLocation)

        # these are needed as this is not the first time we call dirac-configure
        self.cfg.append("-FDMH")
        if self.pp.localConfigFile:
            self.cfg.append("-O %s" % self.pp.localConfigFile)
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                self.cfg.append("--cfg")
            self.cfg.append(self.pp.localConfigFile)

        if self.debugFlag:
            self.cfg.append("-ddd")

        configureCmd = "%s %s" % (self.pp.configureScript, " ".join(self.cfg))

        retCode, _configureOutData = self.executeAndGetOutput(configureCmd, self.pp.installEnv)

        if retCode:
            self.log.error("Could not configure DIRAC [ERROR %d]" % retCode)
            self.exitWithError(retCode)

    def __setFlavour(self):
        pilotRef = "Unknown"
        self.pp.flavour = "Generic"

        # If pilot reference is specified at submission, then set flavour to DIRAC
        # unless overridden by presence of batch system environment variables
        if self.pp.pilotReference:
            self.pp.flavour = "DIRAC"
            pilotRef = self.pp.pilotReference

        # # Batch systems

        # Take the reference from the Torque batch system
        if "PBS_JOBID" in os.environ:
            self.pp.flavour = "SSHTorque"
            pilotRef = "sshtorque://" + self.pp.ceName + "/" + os.environ["PBS_JOBID"].split(".")[0]

        # Take the reference from the OAR batch system
        if "OAR_JOBID" in os.environ:
            self.pp.flavour = "SSHOAR"
            pilotRef = "sshoar://" + self.pp.ceName + "/" + os.environ["OAR_JOBID"]

        # Grid Engine
        if "JOB_ID" in os.environ and "SGE_TASK_ID" in os.environ:
            self.pp.flavour = "SSHGE"
            pilotRef = "sshge://" + self.pp.ceName + "/" + os.environ["JOB_ID"]
        # Generic JOB_ID
        elif "JOB_ID" in os.environ:
            self.pp.flavour = "Generic"
            pilotRef = "generic://" + self.pp.ceName + "/" + os.environ["JOB_ID"]

        # LSF
        if "LSB_BATCH_JID" in os.environ:
            self.pp.flavour = "SSHLSF"
            pilotRef = "sshlsf://" + self.pp.ceName + "/" + os.environ["LSB_BATCH_JID"]

        #  SLURM batch system
        if "SLURM_JOBID" in os.environ:
            self.pp.flavour = "SSHSLURM"
            pilotRef = "sshslurm://" + self.pp.ceName + "/" + os.environ["SLURM_JOBID"]

        # Condor
        if "CONDOR_JOBID" in os.environ:
            self.pp.flavour = "SSHCondor"
            pilotRef = "sshcondor://" + self.pp.ceName + "/" + os.environ["CONDOR_JOBID"]

        # # CEs

        # HTCondor
        if "HTCONDOR_JOBID" in os.environ:
            self.pp.flavour = "HTCondorCE"
            pilotRef = "htcondorce://" + self.pp.ceName + "/" + os.environ["HTCONDOR_JOBID"]

        # This is the CREAM direct submission case
        if "CREAM_JOBID" in os.environ:
            self.pp.flavour = "CREAM"
            pilotRef = os.environ["CREAM_JOBID"]

        if "OSG_WN_TMP" in os.environ:
            self.pp.flavour = "OSG"

        # GLOBUS Computing Elements
        if "GLOBUS_GRAM_JOB_CONTACT" in os.environ:
            self.pp.flavour = "GLOBUS"
            pilotRef = os.environ["GLOBUS_GRAM_JOB_CONTACT"]

        # Direct SSH tunnel submission
        if "SSHCE_JOBID" in os.environ:
            self.pp.flavour = "SSH"
            pilotRef = "ssh://" + self.pp.ceName + "/" + os.environ["SSHCE_JOBID"]

        # Batch host SSH tunnel submission (SSHBatch CE)
        if "SSHBATCH_JOBID" in os.environ and "SSH_NODE_HOST" in os.environ:
            self.pp.flavour = "SSHBATCH"
            pilotRef = (
                "sshbatchhost://"
                + self.pp.ceName
                + "/"
                + os.environ["SSH_NODE_HOST"]
                + "/"
                + os.environ["SSHBATCH_JOBID"]
            )

        # ARC case
        # JOBID does not provide the full url in recent versions of ARC
        # JOBURL has been introduced recently and should be preferred when present
        if "GRID_GLOBAL_JOBID" in os.environ:
            self.pp.flavour = "ARC"
            pilotRef = os.environ["GRID_GLOBAL_JOBID"]

        if "GRID_GLOBAL_JOBURL" in os.environ:
            self.pp.flavour = "ARC"
            pilotRef = os.environ["GRID_GLOBAL_JOBURL"]

        # # DIRAC specific

        # VMDIRAC case
        if "VMDIRAC_VERSION" in os.environ:
            self.pp.flavour = "VMDIRAC"
            pilotRef = "vm://" + self.pp.ceName + "/" + os.environ["JOB_ID"]

        # Pilot reference is given explicitly in environment
        if "PILOT_UUID" in os.environ:
            pilotRef = os.environ["PILOT_UUID"]

        # Pilot reference is specified at submission
        if self.pp.pilotReference:
            pilotRef = self.pp.pilotReference

        self.log.debug("Flavour: %s; pilot reference: %s " % (self.pp.flavour, pilotRef))

        self.pp.pilotReference = pilotRef


class ConfigureArchitecture(CommandBase):
    """This command simply calls dirac-platfom to determine the platform.
    Separated from the ConfigureDIRAC command for easier extensibility.
    """

    @logFinalizer
    def execute(self):
        """This is a simple command to call the dirac-platform utility to get the platform,
        and add it to the configuration

        The architecture script, as well as its options can be replaced in a pilot extension
        """

        cfg = []
        if self.pp.useServerCertificate:
            cfg.append("-o  /DIRAC/Security/UseServerCertificate=yes")
        if self.pp.localConfigFile:
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                cfg.append("--cfg")
            cfg.append(self.pp.localConfigFile)  # this file is as input

        architectureCmd = "%s %s -d" % (self.pp.architectureScript, " ".join(cfg))

        retCode, localArchitecture = self.executeAndGetOutput(architectureCmd, self.pp.installEnv)
        if retCode:
            self.log.error("There was an error updating the platform [ERROR %d]" % retCode)
            self.exitWithError(retCode)
        self.log.info("Architecture determined: %s" % localArchitecture.strip().split("\n")[-1])

        # standard options
        cfg = ["-FDMH"]  # force update, skip CA checks, skip CA download, skip VOMS
        if self.pp.useServerCertificate:
            cfg.append("--UseServerCertificate")
        if self.pp.localConfigFile:
            cfg.append("-O %s" % self.pp.localConfigFile)  # our target file for pilots
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                cfg.append("--cfg")
            cfg.append(self.pp.localConfigFile)  # this file is also an input
        if self.pp.debugFlag:
            cfg.append("-ddd")

        # real options added here
        localArchitecture = localArchitecture.strip().split("\n")[-1].strip()
        cfg.append('-S "%s"' % self.pp.setup)
        cfg.append("-o /LocalSite/Architecture=%s" % localArchitecture)

        configureCmd = "%s %s" % (self.pp.configureScript, " ".join(cfg))
        retCode, _configureOutData = self.executeAndGetOutput(configureCmd, self.pp.installEnv)
        if retCode:
            self.log.error("Configuration error [ERROR %d]" % retCode)
            self.exitWithError(retCode)

        return localArchitecture


class ConfigureCPURequirements(CommandBase):
    """This command determines the CPU requirements. Needs to be executed after ConfigureSite"""

    def __init__(self, pilotParams):
        """c'tor"""
        super(ConfigureCPURequirements, self).__init__(pilotParams)

    @logFinalizer
    def execute(self):
        """Get job CPU requirement and queue normalization"""
        # Determining the CPU normalization factor and updating pilot.cfg with it
        configFileArg = ""
        if self.pp.useServerCertificate:
            configFileArg = "-o /DIRAC/Security/UseServerCertificate=yes"
        if self.pp.localConfigFile:
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                configFileArg = "%s -R %s --cfg %s" % (configFileArg, self.pp.localConfigFile, self.pp.localConfigFile)
            else:
                configFileArg = "%s -R %s %s" % (configFileArg, self.pp.localConfigFile, self.pp.localConfigFile)
        retCode, cpuNormalizationFactorOutput = self.executeAndGetOutput(
            "dirac-wms-cpu-normalization -U %s -d" % configFileArg, self.pp.installEnv
        )
        if retCode:
            self.log.error("Failed to determine cpu normalization [ERROR %d]" % retCode)
            self.exitWithError(retCode)
        # HS06 benchmark
        for line in cpuNormalizationFactorOutput.split("\n"):
            if "Estimated CPU power is" in line:
                line = line.replace("Estimated CPU power is", "")
            if "HS06" in line:
                line = line.replace("HS06", "")
                cpuNormalizationFactor = float(line.strip())
                self.log.info(
                    "Current normalized CPU as determined by 'dirac-wms-cpu-normalization' is %f"
                    % cpuNormalizationFactor
                )

        configFileArg = ""
        if self.pp.useServerCertificate:
            configFileArg = "-o /DIRAC/Security/UseServerCertificate=yes"
        if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
            cfgFile = "--cfg %s" % self.pp.localConfigFile
        else:
            cfgFile = self.pp.localConfigFile
        retCode, cpuTimeOutput = self.executeAndGetOutput(
            "dirac-wms-get-queue-cpu-time --CPUNormalizationFactor=%f %s %s -d"
            % (cpuNormalizationFactor, configFileArg, cfgFile),
            self.pp.installEnv,
        )

        if retCode:
            self.log.error("Failed to determine cpu time left in the queue [ERROR %d]" % retCode)
            self.exitWithError(retCode)

        for line in cpuTimeOutput.split("\n"):
            if "CPU time left determined as" in line:
                cpuTimeOutput = line.replace("CPU time left determined as", "").strip()
                cpuTime = int(cpuTimeOutput)
                self.log.info("CPUTime left (in seconds) is %d" % cpuTime)

        # HS06s = seconds * HS06
        try:
            # determining the CPU time left (in HS06s)
            self.pp.jobCPUReq = float(cpuTime) * float(cpuNormalizationFactor)
            self.log.info("Queue length (which is also set as CPUTimeLeft) is %f" % self.pp.jobCPUReq)
        except ValueError:
            self.log.error("Pilot command output does not have the correct format")
            sys.exit(1)
        # now setting this value in local file
        cfg = ["-FDMH"]
        if self.pp.useServerCertificate:
            cfg.append("-o  /DIRAC/Security/UseServerCertificate=yes")
        if self.pp.localConfigFile:
            cfg.append("-O %s" % self.pp.localConfigFile)  # our target file for pilots
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                cfg.append("--cfg")
            cfg.append(self.pp.localConfigFile)  # this file is also input
        cfg.append("-o /LocalSite/CPUTimeLeft=%s" % str(int(self.pp.jobCPUReq)))  # the only real option

        configureCmd = "%s %s" % (self.pp.configureScript, " ".join(cfg))
        retCode, _configureOutData = self.executeAndGetOutput(configureCmd, self.pp.installEnv)
        if retCode:
            self.log.error("Failed to update CFG file for CPUTimeLeft [ERROR %d]" % retCode)
            self.exitWithError(retCode)


class LaunchAgent(CommandBase):
    """Prepare and launch the job agent"""

    def __init__(self, pilotParams):
        """c'tor"""
        super(LaunchAgent, self).__init__(pilotParams)
        self.innerCEOpts = []
        self.jobAgentOpts = []

    def __setInnerCEOpts(self):
        localUid = os.getuid()
        try:
            import pwd

            localUser = pwd.getpwuid(localUid)[0]
        except KeyError:
            localUser = "Unknown"
        self.log.info("User Name  = %s" % localUser)
        self.log.info("User Id    = %s" % localUid)
        self.innerCEOpts = ["-s /Resources/Computing/CEDefaults"]
        self.innerCEOpts.append("-o WorkingDirectory=%s" % self.pp.workingDir)
        self.innerCEOpts.append("-o /LocalSite/CPUTime=%s" % (int(self.pp.jobCPUReq)))
        if self.pp.ceType.split("/")[0] == "Pool":
            self.jobAgentOpts = [
                "-o MaxCycles=5000",
                "-o PollingTime=%s" % min(20, self.pp.pollingTime),
                "-o StopOnApplicationFailure=False",
                "-o StopAfterFailedMatches=%s" % max(self.pp.pilotProcessors, self.pp.stopAfterFailedMatches),
                "-o FillingModeFlag=True",
            ]
        else:
            self.jobAgentOpts = [
                "-o MaxCycles=%s" % self.pp.maxCycles,
                "-o PollingTime=%s" % self.pp.pollingTime,
                "-o StopOnApplicationFailure=%s" % self.pp.stopOnApplicationFailure,
                "-o StopAfterFailedMatches=%s" % self.pp.stopAfterFailedMatches,
            ]

        if self.debugFlag:
            self.jobAgentOpts.append("-o LogLevel=DEBUG")
        else:
            self.jobAgentOpts.append("-o LogLevel=INFO")

        if self.pp.userGroup:
            self.log.debug('Setting DIRAC Group to "%s"' % self.pp.userGroup)
            self.innerCEOpts.append('-o OwnerGroup="%s"' % self.pp.userGroup)

        if self.pp.userDN:
            self.log.debug('Setting Owner DN to "%s"' % self.pp.userDN)
            self.innerCEOpts.append('-o OwnerDN="%s"' % self.pp.userDN)

        if self.pp.useServerCertificate:
            self.log.debug("Setting UseServerCertificate flag")
            self.innerCEOpts.append("-o /DIRAC/Security/UseServerCertificate=yes")

        # The instancePath is where the agent works
        self.innerCEOpts.append("-o /LocalSite/InstancePath=%s" % self.pp.workingDir)

        # The file pilot.cfg has to be created previously by ConfigureDIRAC
        if self.pp.localConfigFile:
            self.innerCEOpts.append(" -o /AgentJobRequirements/ExtraOptions=%s" % self.pp.localConfigFile)
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                self.innerCEOpts.append("--cfg")
            self.innerCEOpts.append(self.pp.localConfigFile)

    def __startJobAgent(self):
        """Starting of the JobAgent (or of a user-defined command)"""

        diracAgentScript = "dirac-agent"

        # Find any .cfg file uploaded with the sandbox or generated by previous commands
        # and add it in input of the JobAgent run
        extraCFG = []
        for i in os.listdir(self.pp.rootPath):
            cfg = os.path.join(self.pp.rootPath, i)
            if os.path.isfile(cfg) and cfg.endswith(".cfg") and not filecmp.cmp(self.pp.localConfigFile, cfg):
                if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                    extraCFG.append("--cfg")
                extraCFG.append(cfg)

        if self.pp.executeCmd:
            # Execute user command
            self.log.info("Executing user defined command: %s" % self.pp.executeCmd)
            if self.pp.pythonVersion == "27":
                self.exitWithError(int(os.system("source bashrc; %s" % self.pp.executeCmd) / 256))
            else:
                self.exitWithError(int(os.system("source diracos/diracosrc; %s" % self.pp.executeCmd) / 256))

        self.log.info("Starting JobAgent")
        os.environ["PYTHONUNBUFFERED"] = "yes"

        jobAgent = "%s WorkloadManagement/JobAgent %s %s %s" % (
            diracAgentScript,
            " ".join(self.jobAgentOpts),
            " ".join(self.innerCEOpts),
            " ".join(extraCFG),
        )

        retCode, _output = self.executeAndGetOutput(jobAgent, self.pp.installEnv)
        if retCode:
            self.log.error("Error executing the JobAgent [ERROR %d]" % retCode)
            self.exitWithError(retCode)

        fs = os.statvfs(self.pp.workingDir)
        diskSpace = int(fs[4] * fs[0] / 1024 / 1024)
        self.log.info("DiskSpace (MB) = %s" % diskSpace)

    @logFinalizer
    def execute(self):
        """What is called all the time"""
        self.__setInnerCEOpts()
        self.__startJobAgent()

        sys.exit(0)


class MultiLaunchAgent(CommandBase):
    """Prepare and launch multiple agents"""

    def __init__(self, pilotParams):
        """c'tor"""
        super(MultiLaunchAgent, self).__init__(pilotParams)
        self.inProcessOpts = []
        self.jobAgentOpts = []

    def __setInProcessOpts(self):
        localUid = os.getuid()
        try:
            import pwd

            localUser = pwd.getpwuid(localUid)[0]
        except KeyError:
            localUser = "Unknown"
        self.log.info("User Name  = %s" % localUser)
        self.log.info("User Id    = %s" % localUid)
        self.inProcessOpts = ["-s /Resources/Computing/CEDefaults"]
        self.inProcessOpts.append("-o WorkingDirectory=%s" % self.pp.workingDir)
        self.inProcessOpts.append("-o /LocalSite/CPUTime=%s" % (int(self.pp.jobCPUReq)))
        # To prevent a wayward agent picking up and failing many jobs.
        self.inProcessOpts.append("-o MaxTotalJobs=%s" % self.pp.maxCycles)
        self.jobAgentOpts = [
            "-o MaxCycles=%s" % self.pp.maxCycles,
            "-o PollingTime=%s" % self.pp.pollingTime,
            "-o StopOnApplicationFailure=%s" % self.pp.stopOnApplicationFailure,
            "-o StopAfterFailedMatches=0",
        ]

        if self.debugFlag:
            self.jobAgentOpts.append("-o LogLevel=DEBUG")

        if self.pp.userGroup:
            self.log.debug('Setting DIRAC Group to "%s"' % self.pp.userGroup)
            self.inProcessOpts.append('-o OwnerGroup="%s"' % self.pp.userGroup)

        if self.pp.userDN:
            self.log.debug('Setting Owner DN to "%s"' % self.pp.userDN)
            self.inProcessOpts.append('-o OwnerDN="%s"' % self.pp.userDN)

        if self.pp.useServerCertificate:
            self.log.debug("Setting UseServerCertificate flag")
            self.inProcessOpts.append("-o /DIRAC/Security/UseServerCertificate=yes")

        # The instancePath is where the agent works
        self.inProcessOpts.append("-o /LocalSite/InstancePath=%s" % self.pp.workingDir)

        # The file pilot.cfg has to be created previously by ConfigureDIRAC
        if self.pp.localConfigFile:
            self.inProcessOpts.append(" -o /AgentJobRequirements/ExtraOptions=%s" % self.pp.localConfigFile)
            if LooseVersion(self.releaseVersion) >= self.cfgOptionDIRACVersion:
                self.inProcessOpts.append("--cfg")
            self.inProcessOpts.append(self.pp.localConfigFile)

    def __startJobAgent(self):
        """Starting of the JobAgent"""

        # Find any .cfg file uploaded with the sandbox or generated by previous commands

        diracAgentScript = "dirac-agent"
        extraCFG = []
        for i in os.listdir(self.pp.rootPath):
            cfg = os.path.join(self.pp.rootPath, i)
            if os.path.isfile(cfg) and cfg.endswith(".cfg"):
                extraCFG.append(cfg)

        if self.pp.executeCmd:
            # Execute user command
            self.log.info("Executing user defined command: %s" % self.pp.executeCmd)
            if self.pp.pythonVersion == "27":
                self.exitWithError(int(os.system("source bashrc; %s" % self.pp.executeCmd) / 256))
            else:
                self.exitWithError(int(os.system("source diracos/diracosrc; %s" % self.pp.executeCmd) / 256))

        self.log.info("Starting JobAgent")
        os.environ["PYTHONUNBUFFERED"] = "yes"

        pid = {}

        for i in range(int(self.pp.pilotProcessors / self.pp.payloadProcessors)):
            # One JobAgent per each set of payload processors, based on the
            # number of processors allocated to this pilot, rounding downwards

            if self.pp.ceType == "Sudo":
                # Available within the SudoComputingElement as BaseUsername in the ceParameters
                sudoOpts = "-o /LocalSite/BaseUsername=%s%02dp00" % (os.environ["USER"], i)
            else:
                sudoOpts = ""

            jobAgent = "%s WorkloadManagement/JobAgent %s %s %s %s" % (
                diracAgentScript,
                " ".join(self.jobAgentOpts),
                " ".join(self.inProcessOpts),
                sudoOpts,
                " ".join(extraCFG),
            )

            pid[i] = self.forkAndExecute(
                jobAgent, os.path.join(self.pp.workingDir, "jobagent.%02d.log" % i), self.pp.installEnv
            )

            if not pid[i]:
                self.log.error("Error executing the JobAgent %d" % i)
            else:
                self.log.info(
                    "Forked JobAgent %02d (%d/%d) with PID %d"
                    % (i, i + 1, int(self.pp.pilotProcessors / self.pp.payloadProcessors), pid[i])
                )

        # Not very subtle this. How about a time limit??
        for i in range(int(self.pp.pilotProcessors / self.pp.payloadProcessors)):
            os.waitpid(pid[i], 0)

        for i in range(int(self.pp.pilotProcessors / self.pp.payloadProcessors)):
            shutdownMessage = self.__parseJobAgentLog(os.path.join(self.pp.workingDir, "jobagent.%02d.log" % i))
            open(os.path.join(self.pp.workingDir, "shutdown_message.%02d" % i), "w").write(shutdownMessage)
            print(shutdownMessage)

        # FIX ME: this effectively picks one at random. Should be the last one to finish chronologically.
        # Not in order of being started.
        open(os.path.join(self.pp.workingDir, "shutdown_message"), "w").write(shutdownMessage)

        fs = os.statvfs(self.pp.workingDir)
        diskSpace = int(fs[4] * fs[0] / 1024 / 1024)
        self.log.info("DiskSpace (MB) = %s" % diskSpace)

    def __parseJobAgentLog(self, logFile):
        """Parse the JobAgent log and return shutdown message"""

        # catch-all in case nothing matches
        shutdownMessage = "700 Failed, probably JobAgent or Application problem"

        # log file patterns to look for and corresponding messages
        messageMappings = [
            # Variants of: "100 Shutdown as requested by the VM's host/hypervisor"
            ######################################################################
            # There are other errors from the TimeLeft handling, but we let those go
            # to the 600 Failed default
            ['INFO: JobAgent will stop with message "No time left for slot', "100 No time left for slot"],
            # Variants of: "200 Intended work completed ok"
            ###############################################
            # Our work is done. More work available in the queue? Who knows!
            ['INFO: JobAgent will stop with message "Filling Mode is Disabled', "200 Filling Mode is Disabled"],
            ["NOTICE:  Cycle was successful", "200 Success"],
            #
            # !!! Codes 300-699 trigger Vac/Vcycle backoff procedure !!!
            #
            # Variants of: "300 No more work available from task queue"
            ###########################################################
            # We asked, but nothing more from the matcher.
            ['INFO: JobAgent will stop with message "Nothing to do for more than', "300 Nothing to do"],
            ["Job request OK: No match found", "300 Nothing to do"],
            # Variants of: "400 Site/host/VM is currently banned/disabled from receiving more work"
            #######################################################################################
            # Variants of: "500 Problem detected with environment/VM/contextualization provided by the site"
            ################################################################################################
            # This detects using an RFC proxy to talk to legacy-only DIRAC
            ['Error while handshaking [("Remote certificate hasn', "500 Certificate/proxy not acceptable"],
            # Variants of: "600 Grid-wide problem with job agent or application within VM"
            ##############################################################################
            [
                "ERROR: Pilot version does not match the production version",
                "600 Cannot match jobs with this pilot version",
            ],
            # Variants of: "700 Error related to job agent or application within VM"
            ########################################################################
            # Some of the ways the JobAgent/Application can stop with errors.
            # Otherwise we just get the default 700 Failed message.
            ['INFO: JobAgent will stop with message "Job Rescheduled', "600 Problem so job rescheduled"],
            ['INFO: JobAgent will stop with message "Matcher Failed', "600 Matcher Failed"],
            ['INFO: JobAgent will stop with message "JDL Problem', "600 JDL Problem"],
            ['INFO: JobAgent will stop with message "Payload Proxy Not Found', "600 Payload Proxy Not Found"],
            ['INFO: JobAgent will stop with message "Problem Rescheduling Job', "600 Problem Rescheduling Job"],
            [
                'INFO: JobAgent will stop with message "Payload execution failed with error code',
                "600 Payload execution failed with error",
            ],
        ]

        try:
            with open(logFile, "r") as f:
                oneline = f.readline()
                while oneline:
                    for pair in messageMappings:
                        if pair[0] in oneline:
                            shutdownMessage = pair[1]
                            break
                    oneline = f.readline()

        except BaseException:
            return "700 Internal VM logging failed"

        return shutdownMessage

    @logFinalizer
    def execute(self):
        """What is called all the time"""
        self.__setInProcessOpts()
        self.__startJobAgent()

        sys.exit(0)


class NagiosProbes(CommandBase):
    """Run one or more Nagios probe scripts that follow the Nagios Plugin API:
     https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html

    Each probe is a script or executable present in the pilot directory, which is
    executed to gather its return code and stdout messages. Probe name = filename.

    Probes must not expect any command line arguments but can gather information about
    the current machine from expected environment variables etc.

    The results are reported through the Pilot Logger.
    """

    def __init__(self, pilotParams):
        """c'tor"""
        super(NagiosProbes, self).__init__(pilotParams)
        self.nagiosProbes = []
        self.nagiosPutURL = None

    def _setNagiosOptions(self):
        """Setup list of Nagios probes and optional PUT URL from pilot.json"""

        try:
            self.nagiosProbes = [
                str(pv).strip() for pv in self.pp.pilotJSON["Setups"][self.pp.setup]["NagiosProbes"].split(",")
            ]
        except KeyError:
            try:
                self.nagiosProbes = [
                    str(pv).strip() for pv in self.pp.pilotJSON["Setups"]["Defaults"]["NagiosProbes"].split(",")
                ]
            except KeyError:
                pass

        try:
            self.nagiosPutURL = str(self.pp.pilotJSON["Setups"][self.pp.setup]["NagiosPutURL"])
        except KeyError:
            try:
                self.nagiosPutURL = str(self.pp.pilotJSON["Setups"]["Defaults"]["NagiosPutURL"])
            except KeyError:
                pass

        self.log.debug("NAGIOS PROBES [%s]" % ", ".join(self.nagiosProbes))

    def _runNagiosProbes(self):
        """Run the probes one by one"""

        for probeCmd in self.nagiosProbes:
            self.log.debug("Running Nagios probe %s" % probeCmd)

            try:
                # Make sure the probe is executable
                os.chmod(probeCmd, stat.S_IXUSR + os.stat(probeCmd).st_mode)

            except OSError:
                self.log.error("File %s is missing! Skipping test" % probeCmd)
                retCode = 2
                output = "Probe file %s missing from pilot!" % probeCmd

            else:
                # FIXME: need a time limit on this in case the probe hangs
                retCode, output = self.executeAndGetOutput("./" + probeCmd)

            if retCode == 0:
                self.log.info("Return code = 0: %s" % str(output).split("\n", 1)[0])
                retStatus = "info"
            elif retCode == 1:
                self.log.warn("Return code = 1: %s" % str(output).split("\n", 1)[0])
                retStatus = "warning"
            else:
                # retCode could be 2 (error) or 3 (unknown) or something we haven't thought of
                self.log.error("Return code = %d: %s" % (retCode, str(output).split("\n", 1)[0]))
                retStatus = "error"

            # report results to pilot logger too. Like this:
            #   "NagiosProbes", probeCmd, retStatus, str(retCode) + ' ' + output.split('\n',1)[0]

            if self.nagiosPutURL:
                # Alternate logging of results to HTTPS PUT service too
                hostPort = self.nagiosPutURL.split("/")[2]
                path = "/" + "/".join(self.nagiosPutURL.split("/")[3:]) + self.pp.ceName + "/" + probeCmd

                self.log.info("Putting %s Nagios output to https://%s%s" % (probeCmd, hostPort, path))

                try:
                    connection = HTTPSConnection(
                        host=hostPort,
                        timeout=30,
                        key_file=os.environ["X509_USER_PROXY"],
                        cert_file=os.environ["X509_USER_PROXY"],
                    )

                    connection.request("PUT", path, str(retCode) + " " + str(int(time.time())) + "\n" + output)

                except Exception as e:
                    self.log.error("PUT of %s Nagios output fails with %s" % (probeCmd, str(e)))

                else:
                    result = connection.getresponse()

                    if int(result.status / 100) == 2:
                        self.log.info(
                            "PUT of %s Nagios output succeeds with %d %s" % (probeCmd, result.status, result.reason)
                        )
                    else:
                        self.log.error(
                            "PUT of %s Nagios output fails with %d %s" % (probeCmd, result.status, result.reason)
                        )

    @logFinalizer
    def execute(self):
        """Standard entry point to a pilot command"""
        self._setNagiosOptions()
        self._runNagiosProbes()
