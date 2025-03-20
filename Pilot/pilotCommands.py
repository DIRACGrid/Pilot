"""Definitions of a standard set of pilot commands

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

from __future__ import absolute_import, division, print_function

import filecmp
import os
import platform
import shutil
import socket
import stat
import sys
import time
import traceback
from collections import Counter

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
    from Pilot.pilotTools import (
        CommandBase,
        getSubmitterInfo,
        retrieveUrlTimeout,
        safe_listdir,
        sendMessage,
    )
except ImportError:
    from pilotTools import (
        CommandBase,
        getSubmitterInfo,
        retrieveUrlTimeout,
        safe_listdir,
        sendMessage,
    )
############################


def logFinalizer(func):
    """
    PilotCommand decorator. It marks a log file as final so no more messages should be written to it.
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
            ret = func(self)
            self.log.buffer.flush()
            return ret

        except SystemExit as exCode:  # or Exception ?
            # controlled exit
            pRef = self.pp.pilotReference
            self.log.info(
                "Flushing the remote logger buffer for pilot on sys.exit(): %s (exit code:%s)" % (pRef, str(exCode))
            )
            self.log.buffer.flush()  # flush the buffer unconditionally (on sys.exit()).
            try:
                sendMessage(self.log.url, self.log.pilotUUID, self.log.wnVO, "finaliseLogs", {"retCode": str(exCode)})
            except Exception as exc:
                self.log.error("Remote logger couldn't be finalised %s " % str(exc))
            raise
        except Exception as exc:
            # unexpected exit: document it and bail out.
            self.log.error(str(exc))
            self.log.error(traceback.format_exc())
            raise
        finally:
            self.log.buffer.cancelTimer()

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
            self.exitWithError(1)


class InstallDIRAC(CommandBase):
    """Source from CVMFS, or install locally"""

    def __init__(self, pilotParams):
        """c'tor"""
        super(InstallDIRAC, self).__init__(pilotParams)
        self.pp.rootPath = self.pp.pilotRootPath

    def _sourceEnvironmentFile(self):
        """Source the $DIRAC_RC_FILE and save the created environment in self.pp.installEnv"""

        retCode, output = self.executeAndGetOutput("bash -c 'source $DIRAC_RC_PATH && env'", self.pp.installEnv)
        if retCode:
            self.log.error("Could not parse the %s file [ERROR %d]" % (self.pp.installEnv["DIRAC_RC_PATH"], retCode))
            self.exitWithError(retCode)
        for line in output.split("\n"):
            try:
                var, value = [vx.strip() for vx in line.split("=", 1)]
                if var == "_" or "SSH" in var or "{" in value or "}" in value:  # Avoiding useless/confusing stuff
                    continue
                self.pp.installEnv[var] = value
            except (IndexError, ValueError):
                continue

    def _saveEnvInFile(self, eFile="environmentSourceDirac"):
        """Save pp.installEnv in file (delete if already present)

        :param str eFile: file where to save env
        """
        if os.path.isfile(eFile):
            os.remove(eFile)

        with open(eFile, "w") as fd:
            for var, val in self.pp.installEnv.items():
                if var == "_" or var == "X509_USER_PROXY" or "SSH" in var or "{" in val or "}" in val:
                    continue
                if " " in val and val[0] != '"':
                    val = '"%s"' % val
                bl = "export %s=%s\n" % (var, val.rstrip(":"))
                fd.write(bl)

    def _getPreinstalledEnvScript(self):
        """Get preinstalled environment script if any"""

        self.log.debug("self.pp.preinstalledEnv = %s" % self.pp.preinstalledEnv)
        self.log.debug("self.pp.preinstalledEnvPrefix = %s" % self.pp.preinstalledEnvPrefix)
        self.log.debug("self.pp.CVMFS_locations = %s" % self.pp.CVMFS_locations)

        preinstalledEnvScript = self.pp.preinstalledEnv
        if not preinstalledEnvScript and self.pp.preinstalledEnvPrefix:
            version = self.pp.releaseVersion or "pro"
            arch = platform.system() + "-" + platform.machine()
            preinstalledEnvScript = os.path.join(self.pp.preinstalledEnvPrefix, version, arch, "diracosrc")

        if not preinstalledEnvScript and self.pp.CVMFS_locations:
            for CVMFS_location in self.pp.CVMFS_locations:
                version = self.pp.releaseVersion or "pro"
                arch = platform.system() + "-" + platform.machine()
                preinstalledEnvScript = os.path.join(
                    CVMFS_location, self.pp.releaseProject.lower() + "dirac", version, arch, "diracosrc"
                )
                if os.path.isfile(preinstalledEnvScript):
                    break

        self.log.debug("preinstalledEnvScript = %s" % preinstalledEnvScript)

        if preinstalledEnvScript:
            self.log.info("Evaluating env script %s" % preinstalledEnvScript)
            if not safe_listdir(os.path.dirname(preinstalledEnvScript)):
                raise OSError("release not found")

            if os.path.isfile(preinstalledEnvScript):
                self.pp.preinstalledEnv = preinstalledEnvScript
                self.pp.installEnv["DIRAC_RC_PATH"] = preinstalledEnvScript

    def _localInstallDIRAC(self):
        """Install python3 version of DIRAC client"""

        self.log.info("Installing DIRAC locally")

        # default to limit the resources used during installation to what the pilot owns
        installEnv = {
            # see https://github.com/DIRACGrid/Pilot/issues/189
            "MAMBA_EXTRACT_THREADS": str(self.pp.maxNumberOfProcessors or 1),
        }
        installEnv.update(self.pp.installEnv)

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
            "bash /cvmfs/dirac.egi.eu/installSource/%s 2>&1" % installerName, installEnv
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
            retCode, _ = self.executeAndGetOutput("bash %s 2>&1" % installerName, installEnv)
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

        # 6. source diracos/diracosrc
        self.pp.installEnv["DIRAC_RC_PATH"] = os.path.join(os.getcwd(), "diracos/diracosrc")
        self._sourceEnvironmentFile()
        self._saveEnvInFile()

        # 7. pip install DIRAC[pilot]
        pipInstalling = "pip install %s " % self.pp.pipInstallOptions

        if self.pp.modules:  # install a non-released (on pypi) version
            for modules in self.pp.modules.split(","):
                branch = project = ""
                elements = modules.split(":::")
                url = ""
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

        try:
            # In case we want to force local installation (in absence of CVMFS or for test reasons)
            if "diracInstallOnly" in self.pp.genericOption:
                self.log.info("NOT sourcing: starting traditional DIRAC installation")
                self._localInstallDIRAC()
                return

            # Try sourcing from CVMFS
            self._getPreinstalledEnvScript()
            if not self.pp.preinstalledEnv:
                self._localInstallDIRAC()
                return
            # if we are here, we have a preinstalled environment
            self._sourceEnvironmentFile()
            self.log.info("source DIRAC env DONE, for release %s" % self.pp.releaseVersion)
            # environment variables to add?
            if self.pp.userEnvVariables:
                # User-requested environment variables (comma-separated, name and value separated by ":::")
                newEnvVars = dict(name.split(":::", 1) for name in self.pp.userEnvVariables.replace(" ", "").split(","))
                self.log.info("Adding env variable(s) to the environment : %s" % newEnvVars)
                self.pp.installEnv.update(newEnvVars)

        except OSError as e:
            self.log.error("Exception when trying to source the DIRAC environment: %s" % str(e))
            if "cvmfsOnly" in self.pp.genericOption:
                self.exitWithError(1)
            self.log.warn("Source of the DIRAC environment NOT DONE: starting traditional DIRAC installation")
            self._localInstallDIRAC()

        finally:
            # saving also in environmentSourceDirac file for completeness...
            # (and bashrc too, if not created, with the same content)...
            # this is doing some horrible mangling unfortunately!
            self._saveEnvInFile()
            if not os.path.isfile("bashrc"):
                shutil.copyfile("environmentSourceDirac", "bashrc")


class ConfigureBasics(CommandBase):
    """This command completes DIRAC installation.

    It calls dirac-configure to:

        * (maybe) download the CAs
        * creates a standard or custom (defined by self.pp.localConfigFile) cfg file
          (by default 'pilot.cfg') to be used where all the pilot configuration is to be set, e.g.:
        * adds to it basic info like the version
        * adds to it the security configuration

    If there is more than one command calling dirac-configure, this one should be always the first one called.

    .. note:: Further commands should always call dirac-configure using the options -FDMH
    .. note:: If custom cfg file is created further commands should call dirac-configure with
               "-O %s %s" % ( self.pp.localConfigFile, self.pp.localConfigFile )
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
        self.pp.flavour, self.pp.pilotReference, self.pp.batchSystemInfo = getSubmitterInfo(self.pp.ceName)

        if not self.pp.pilotReference:
            self.pp.pilotReference = self.pp.pilotUUID

        self._getBasicsCFG()
        self._getSecurityCFG()

        if self.pp.debugFlag:
            self.cfg.append("-ddd")
        if self.pp.localConfigFile:
            self.cfg.append("-O %s" % self.pp.localConfigFile)  # here, only as output
            # Make sure that this configuration is available in the user job environment
            self.pp.installEnv["DIRACSYSCONFIG"] = os.path.realpath(self.pp.localConfigFile)

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
        # add the installation locations
        self.cfg.append("-o /LocalSite/CVMFS_locations=%s" % ",".join(self.pp.CVMFS_locations))

        if self.pp.wnVO:
            self.cfg.append('-o "/Resources/Computing/CEDefaults/VirtualOrganization=%s"' % self.pp.wnVO)

    def _getSecurityCFG(self):
        """Sets security-related env variables, if needed"""
        # Need to know host cert and key location in case they are needed
        if self.pp.useServerCertificate:
            self.cfg.append("--UseServerCertificate")
            self.cfg.append("-o /DIRAC/Security/CertFile=%s/hostcert.pem" % self.pp.certsLocation)
            self.cfg.append("-o /DIRAC/Security/KeyFile=%s/hostkey.pem" % self.pp.certsLocation)

        # If DIRAC (or its extension) is installed in CVMFS do not download VOMS and CAs
        if self.pp.preinstalledEnv:
            self.cfg.append("-DMH")


class RegisterPilot(CommandBase):
    """The Pilot self-announce its own presence"""

    def __init__(self, pilotParams):
        """c'tor"""
        super(RegisterPilot, self).__init__(pilotParams)

        # this variable contains the options that are passed to dirac-admin-add-pilot
        self.cfg = []
        self.pilotStamp = os.environ.get("DIRAC_PILOT_STAMP", self.pp.pilotUUID)

    @logFinalizer
    def execute(self):
        """Calls dirac-admin-add-pilot"""

        if not self.pp.pilotReference:
            self.log.warn("Skipping module, no pilot reference found")
            return

        if self.pp.useServerCertificate:
            self.cfg.append("-o  /DIRAC/Security/UseServerCertificate=yes")
        if self.pp.localConfigFile:
            self.cfg.extend(["--cfg", self.pp.localConfigFile])  # this file is as input

        checkCmd = "dirac-admin-add-pilot %s %s %s %s --status=Running %s -d" % (
            self.pp.pilotReference,
            self.pp.wnVO,
            self.pp.flavour,
            self.pilotStamp,
            " ".join(self.cfg),
        )
        retCode, _ = self.executeAndGetOutput(checkCmd, self.pp.installEnv)
        if retCode:
            self.log.error("Could not get execute dirac-admin-add-pilot [ERROR %d]" % retCode)


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
            self.cfg.extend(["--cfg", self.pp.localConfigFile])  # this file is as input

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
            self.exitWithError(1)

        # Pick up all the relevant resource parameters that will be used in the job matching
        if "WholeNode" in resourceDict:
            self.pp.tags.append("WholeNode")

        # Tags must be added to already defined tags if any
        self.pp.tags += resourceDict.pop("Tag", [])

        # RequiredTags are like Tags.
        self.pp.reqtags += resourceDict.pop("RequiredTag", [])

        self.pp.queueParameters = resourceDict
        for queueParamName, queueParamValue in self.pp.queueParameters.items():
            if isinstance(queueParamValue, list):  # for the tags
                queueParamValue = ",".join([str(qpv).strip() for qpv in queueParamValue])
            self.cfg.append("-o /LocalSite/%s=%s" % (queueParamName, quote(queueParamValue)))

        if self.cfg:
            if self.pp.localConfigFile:
                self.cfg.append("-O %s" % self.pp.localConfigFile)  # this file is as output

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
            self.cfg.extend(["--cfg", self.pp.localConfigFile])  # this file is as input
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
            self.exitWithError(1)

        # If NumberOfProcessors or MaxRAM are defined in the resource configuration, these
        # values are preferred

        # pilotProcessors is basically the number of processors this pilot is "managing"
        self.pp.pilotProcessors = numberOfProcessorsOnWN

        self.log.info("pilotProcessors = %d" % self.pp.pilotProcessors)
        self.cfg.append('-o "/Resources/Computing/CEDefaults/NumberOfProcessors=%d"' % self.pp.pilotProcessors)

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
            self.cfg.extend(["--cfg", self.pp.localConfigFile])  # this file is as input

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
        self.cfg.append("-o /LocalSite/GridMiddleware=%s" % self.pp.flavour)

        # Add batch system details to the configuration
        # Can be used by the pilot/job later on, to interact with the batch system
        self.cfg.append("-o /LocalSite/BatchSystemInfo/Type=%s" % self.pp.batchSystemInfo.get("Type", "Unknown"))
        self.cfg.append("-o /LocalSite/BatchSystemInfo/JobID=%s" % self.pp.batchSystemInfo.get("JobID", "Unknown"))

        batchSystemParams = self.pp.batchSystemInfo.get("Parameters", {})
        self.cfg.append("-o /LocalSite/BatchSystemInfo/Parameters/Queue=%s" % batchSystemParams.get("Queue", "Unknown"))
        self.cfg.append(
            "-o /LocalSite/BatchSystemInfo/Parameters/BinaryPath=%s" % batchSystemParams.get("BinaryPath", "Unknown")
        )
        self.cfg.append("-o /LocalSite/BatchSystemInfo/Parameters/Host=%s" % batchSystemParams.get("Host", "Unknown"))
        self.cfg.append(
            "-o /LocalSite/BatchSystemInfo/Parameters/InfoPath=%s" % batchSystemParams.get("InfoPath", "Unknown")
        )

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

        if self.pp.pilotReference:
            self.cfg.append("-o /LocalSite/PilotReference=%s" % self.pp.pilotReference)

        if self.pp.useServerCertificate:
            self.cfg.append("--UseServerCertificate")
            self.cfg.append("-o /DIRAC/Security/CertFile=%s/hostcert.pem" % self.pp.certsLocation)
            self.cfg.append("-o /DIRAC/Security/KeyFile=%s/hostkey.pem" % self.pp.certsLocation)

        # these are needed as this is not the first time we call dirac-configure
        self.cfg.append("-FDMH")
        if self.pp.localConfigFile:
            self.cfg.append("-O %s" % self.pp.localConfigFile)
            self.cfg.extend(["--cfg", self.pp.localConfigFile])

        if self.debugFlag:
            self.cfg.append("-ddd")

        configureCmd = "%s %s" % (self.pp.configureScript, " ".join(self.cfg))

        retCode, _configureOutData = self.executeAndGetOutput(configureCmd, self.pp.installEnv)

        if retCode:
            self.log.error("Could not configure DIRAC [ERROR %d]" % retCode)
            self.exitWithError(retCode)


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
            cfg.extend(["--cfg", self.pp.localConfigFile])  # this file is as input

        archScript = self.pp.architectureScript
        if self.pp.architectureScript.split(" ")[0] == "dirac-apptainer-exec":
            archScript = self.pp.architectureScript.split(" ")[1]
        
        architectureCmd = "%s %s -ddd" % (archScript, " ".join(cfg))

        if self.pp.architectureScript.startswith("dirac-apptainer-exec"):
            architectureCmd = "dirac-apptainer-exec '%s' %s" % (architectureCmd, " ".join(cfg))

        retCode, localArchitecture = self.executeAndGetOutput(architectureCmd, self.pp.installEnv)
        if retCode:
            self.log.error("There was an error getting the platform [ERROR %d]" % retCode)
            self.exitWithError(retCode)
        self.log.info("Architecture determined: %s" % localArchitecture.strip().split("\n")[-1])

        # standard options
        cfg = ["-FDMH"]  # force update, skip CA checks, skip CA download, skip VOMS
        if self.pp.useServerCertificate:
            cfg.append("--UseServerCertificate")
        if self.pp.localConfigFile:
            cfg.append("-O %s" % self.pp.localConfigFile)  # our target file for pilots
            cfg.extend(["--cfg", self.pp.localConfigFile])  # this file is also an input
        if self.pp.debugFlag:
            cfg.append("-ddd")

        # real options added here
        localArchitecture = localArchitecture.strip().split("\n")[-1].strip()
        cfg.append('-S "%s"' % self.pp.setup)
        cfg.append("-o /LocalSite/Architecture=%s" % localArchitecture)

        # add the local platform as determined by the platform module
        cfg.append("-o /LocalSite/Platform=%s" % platform.machine())

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
            configFileArg = "%s -R %s --cfg %s" % (configFileArg, self.pp.localConfigFile, self.pp.localConfigFile)
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
        cfgFile = "--cfg %s" % self.pp.localConfigFile
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
            self.exitWithError(1)
        # now setting this value in local file
        cfg = ["-FDMH"]
        if self.pp.useServerCertificate:
            cfg.append("-o  /DIRAC/Security/UseServerCertificate=yes")
        if self.pp.localConfigFile:
            cfg.append("-O %s" % self.pp.localConfigFile)  # our target file for pilots
            cfg.extend(["--cfg", self.pp.localConfigFile])  # this file is also input
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
            self.innerCEOpts.extend(["--cfg", self.pp.localConfigFile])

    def __startJobAgent(self):
        """Starting of the JobAgent (or of a user-defined command)"""

        diracAgentScript = "dirac-agent"

        # Find any .cfg file uploaded with the sandbox or generated by previous commands
        # and add it in input of the JobAgent run
        extraCFG = []
        for i in os.listdir(self.pp.rootPath):
            cfg = os.path.join(self.pp.rootPath, i)
            if os.path.isfile(cfg) and cfg.endswith(".cfg") and not filecmp.cmp(self.pp.localConfigFile, cfg):
                extraCFG.extend(["--cfg", cfg])

        if self.pp.executeCmd:
            # Execute user command
            self.log.info("Executing user defined command: %s" % self.pp.executeCmd)
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

            # TODO: Do something with the retStatus (for example: log it?)

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
