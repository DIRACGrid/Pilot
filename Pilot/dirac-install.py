#!/usr/bin/env python
"""
The main DIRAC installer script
"""

import sys
import os
import getopt
import imp
import time
import stat
import types
import shutil
import hashlib as md5
from Pilot.DiracParams import Params
from Pilot.DiracReleaseConfig import ReleaseConfig
from Pilot.PilotTools import S_OK, S_ERROR, logNOTICE, logERROR, urlRetriveTimeout

__RCSID__ = "$Id$"

executablePerms = stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH



############
# Start of CFG
############


cliParams = Params()

#platformAlias = { 'Darwin_i386_10.6' : 'Darwin_i386_10.5' }
platformAlias = {}

def logDEBUG( msg ):
  """
  Debug Logger
  """
  if cliParams.debug:
    for line in msg.split( "\n" ):
      print "%s UTC dirac-install [DEBUG] %s" % ( time.strftime( '%Y-%m-%d %H:%M:%S', time.gmtime() ), line )
    sys.stdout.flush()

def checkHashFunction(pkgName, pkgVer, tarsURLInternal, cacheDir, cache, tarName):
  """ Checks a file hash"""
  md5Name = "%s-%s.md5" % ( pkgName, pkgVer )
  md5Path = os.path.join( cliParams.targetPath, md5Name )
  md5FileURL = "%s/%s" % ( tarsURLInternal, md5Name )
  md5CachePath = os.path.join( cacheDir, md5Name )
  if cache and os.path.isfile( md5CachePath ):
    logNOTICE( "Using cached copy of %s" % md5Name )
    shutil.copy( md5CachePath, md5Path )
  else:
    logNOTICE( "Retrieving %s" % md5FileURL )
    try:
      if not urlRetriveTimeout( md5FileURL, fileName=md5Path, timeout=60 ):
        logERROR( "Cannot download %s" % tarName )
        return False
    except Exception, e:
      logERROR( "Cannot download %s: %s" % ( md5Name, str( e ) ) )
      return False
  #Read md5
  fd = open( os.path.join( cliParams.targetPath, md5Name ), "r" )
  md5Expected = fd.read().strip()
  fd.close()
  #Calculate md5
  md5Calculated = md5.md5()
  fd = open( os.path.join( cliParams.targetPath, tarName ), "r" )
  buf = fd.read( 4096 )
  while buf:
    md5Calculated.update( buf )
    buf = fd.read( 4096 )
  fd.close()
  #Check
  if md5Expected != md5Calculated.hexdigest():
    logERROR( "Oops... md5 for package %s failed!" % pkgVer )
    sys.exit( 1 )
  #Delete md5 file
  if cache:
    if not os.path.isdir( cacheDir ):
      os.makedirs( cacheDir )
      os.rename( md5Path, md5CachePath )
  else:
    os.unlink( md5Path )
  return True


def downloadAndExtractTarball( tarsURLInternal, pkgName, pkgVer, checkHash = True, cache = False ):
  """
  Downloads and extracts the tarball
  """
  tarName = "%s-%s.tar.gz" % ( pkgName, pkgVer )
  tarPath = os.path.join( cliParams.targetPath, tarName )
  tarFileURL = "%s/%s" % ( tarsURLInternal, tarName )
  tarFileCVMFS = "/cvmfs/dirac.egi.eu/installSource/%s" % tarName
  cacheDir = os.path.join( cliParams.basePath, ".installCache" )
  tarCachePath = os.path.join( cacheDir, tarName )
  if cache and os.path.isfile( tarCachePath ):
    logNOTICE( "Using cached copy of %s" % tarName )
    shutil.copy( tarCachePath, tarPath )
  elif os.path.exists( tarFileCVMFS ):
    logNOTICE( "Using CVMFS copy of %s" % tarName )
    tarPath = tarFileCVMFS
    checkHash = False
    cache = False
  else:
    logNOTICE( "Retrieving %s" % tarFileURL )
    try:
      if not urlRetriveTimeout( tarFileURL, fileName=tarPath, timeout=cliParams.timeout ):
        logERROR( "Cannot download %s" % tarName )
        return False
    except Exception, e:
      logERROR( "Cannot download %s: %s" % ( tarName, str( e ) ) )
      sys.exit( 1 )
  if checkHash:
    res = checkHashFunction(pkgName, pkgVer, tarsURLInternal, cacheDir, cache, tarName)
    if not res:
      return res
  #Extract
  #cwd = os.getcwd()
  #os.chdir(cliParams.targetPath)
  #tf = tarfile.open( tarPath, "r" )
  #for member in tf.getmembers():
  #  tf.extract( member )
  #os.chdir(cwd)
  tarCmd = "tar xzf '%s' -C '%s'" % ( tarPath, cliParams.targetPath )
  os.system( tarCmd )
  #Delete tar
  if cache:
    if not os.path.isdir( cacheDir ):
      os.makedirs( cacheDir )
    os.rename( tarPath, tarCachePath )
  else:
    if tarPath != tarFileCVMFS:
      os.unlink( tarPath )

  postInstallScript = os.path.join( cliParams.targetPath, pkgName, 'dirac-postInstall.py' )
  if os.path.isfile( postInstallScript ):
    os.chmod( postInstallScript , executablePerms )
    logNOTICE( "Executing %s..." % postInstallScript )
    if os.system( "python '%s' > '%s.out' 2> '%s.err'" % ( postInstallScript,
                                                           postInstallScript,
                                                           postInstallScript ) ):
      logERROR( "Post installation script %s failed. Check %s.err" % ( postInstallScript,
                                                                       postInstallScript ) )
  return True

def fixBuildPaths():
  """
  At compilation time many scripts get the building directory inserted,
  this needs to be changed to point to the current installation path:
  cliParams.targetPath
  """

  # Locate build path (from header of pydoc)
  binaryPath = os.path.join( cliParams.targetPath, cliParams.platform )
  pydocPath = os.path.join( binaryPath, 'bin', 'pydoc' )
  try:
    fd = open( pydocPath )
    line = fd.readline()
    fd.close()
    buildPath = line[2:line.find( cliParams.platform ) - 1]
    replaceCmd = "grep -rIl '%s' %s | xargs sed -i'.org' 's:%s:%s:g'" % ( buildPath,
                                                                          binaryPath,
                                                                          buildPath,
                                                                          cliParams.targetPath )
    os.system( replaceCmd )

  except Exception as _:
    pass


def runExternalsPostInstall():
  """
   If there are any postInstall in externals, run them
  """
  postInstallPath = os.path.join( cliParams.targetPath, cliParams.platform, "postInstall" )
  if not os.path.isdir( postInstallPath ):
    logDEBUG( "There's no %s directory. Skipping postInstall step" % postInstallPath )
    return
  postInstallSuffix = "-postInstall"
  for scriptName in os.listdir( postInstallPath ):
    if not scriptName.endswith( postInstallSuffix ):
      logDEBUG( "%s does not have the %s suffix. Skipping.." % ( scriptName, postInstallSuffix ) )
      continue
    scriptPath = os.path.join( postInstallPath, scriptName )
    os.chmod( scriptPath , executablePerms )
    logNOTICE( "Executing %s..." % scriptPath )
    if os.system( "'%s' > '%s.out' 2> '%s.err'" % ( scriptPath, scriptPath, scriptPath ) ):
      logERROR( "Post installation script %s failed. Check %s.err" % ( scriptPath, scriptPath ) )
      sys.exit( 1 )

def fixMySQLScript():
  """
   Update the mysql.server script (if installed) to point to the proper datadir
  """
  scriptPath = os.path.join( cliParams.targetPath, 'scripts', 'dirac-fix-mysql-script' )
  bashrcFile = os.path.join( cliParams.targetPath, 'bashrc' )
  if cliParams.useVersionsDir:
    bashrcFile = os.path.join( cliParams.basePath, 'bashrc' )
  command = 'source %s; %s > /dev/null' % (bashrcFile,scriptPath)
  if os.path.exists( scriptPath ):
    logNOTICE( "Executing %s..." % command )
    os.system( 'bash -c "%s"' % command )

def checkPlatformAliasLink():
  """
  Make a link if there's an alias
  """
  if cliParams.platform in platformAlias:
    os.symlink( os.path.join( cliParams.targetPath, platformAlias[ cliParams.platform ] ),
                os.path.join( cliParams.targetPath, cliParams.platform ) )

def installExternalRequirements( extType ):
  """ Install the extension requirements if any
  """
  reqScript = os.path.join( cliParams.targetPath, "scripts", 'dirac-externals-requirements' )
  bashrcFile = os.path.join( cliParams.targetPath, 'bashrc' )
  if cliParams.useVersionsDir:
    bashrcFile = os.path.join( cliParams.basePath, 'bashrc' )
  if os.path.isfile( reqScript ):
    os.chmod( reqScript , executablePerms )
    logNOTICE( "Executing %s..." % reqScript )
    command = "python '%s' -t '%s' > '%s.out' 2> '%s.err'" % ( reqScript, extType,
                                                               reqScript, reqScript )
    if os.system( 'bash -c "source %s; %s"' % (bashrcFile,command) ):
      logERROR( "Requirements installation script %s failed. Check %s.err" % ( reqScript,
                                                                               reqScript ) )
  return True

####
# End of helper functions
####

cmdOpts = ( ( 'r:', 'release=', 'Release version to install' ),
            ( 'l:', 'project=', 'Project to install' ),
            ( 'e:', 'extraModules=', 'Extra modules to install (comma separated)' ),
            ( 't:', 'installType=', 'Installation type (client/server)' ),
            ( 'i:', 'pythonVersion=', 'Python version to compile (27/26)' ),
            ( 'p:', 'platform=', 'Platform to install' ),
            ( 'P:', 'installationPath=', 'Path where to install (default current working dir)' ),
            ( 'b', 'build', 'Force local compilation' ),
            ( 'g:', 'grid=', 'lcg tools package version' ),
            ( 'B', 'noAutoBuild', 'Do not build if not available' ),
            ( 'v', 'useVersionsDir', 'Use versions directory' ),
            ( 'u:', 'baseURL=', "Use URL as the source for installation tarballs" ),
            ( 'd', 'debug', 'Show debug messages' ),
            ( 'V:', 'installation=', 'Installation from which to extract parameter values' ),
            ( 'X', 'externalsOnly', 'Only install external binaries' ),
            ( 'M:', 'defaultsURL=', 'Where to retrieve the global defaults from' ),
            ( 'h', 'help', 'Show this help' ),
            ( 'T:', 'Timeout=', 'Timeout for downloads (default = %s)' )
          )

def usage():
  """
  Prints the usage of script
  """
  print "\nUsage:\n\n  %s <opts> <cfgFile>" % os.path.basename( sys.argv[0] )
  print "\nOptions:"
  for cmdOpt in cmdOpts:
    print "\n  %s %s : %s" % ( cmdOpt[0].ljust( 3 ), cmdOpt[1].ljust( 20 ), cmdOpt[2] )
  print
  print "Known options and default values from /defaults section of releases file"
  for options in [ ( 'Release', cliParams.release ),
                   ( 'Project', cliParams.project ),
                   ( 'ModulesToInstall', [] ),
                   ( 'ExternalsType', cliParams.externalsType ),
                   ( 'PythonVersion', cliParams.pythonVersion ),
                   ( 'LcgVer', cliParams.lcgVer ),
                   ( 'UseVersionsDir', cliParams.useVersionsDir ),
                   ( 'BuildExternals', cliParams.buildExternals ),
                   ( 'NoAutoBuild', cliParams.noAutoBuild ),
                   ( 'Debug', cliParams.debug ),
                   ( 'Timeout', cliParams.timeout ) ]:
    print " %s = %s" % options

  sys.exit( 1 )

def parseRelease(value):
  """ Parse release argument """
  cliParams.release = value

def parseProject(value):
  """ Parse project argument """
  cliParams.project = value

def parseExtraModules(value):
  """ Parse extra modules argument """
  for pkg in [ p.strip() for p in value.split( "," ) if p.strip() ]:
    if pkg not in cliParams.extraModules:
      cliParams.extraModules.append( pkg )

def parseInstallType(value):
  """ Parse the install type argument """
  cliParams.externalsType = value

def parsePythonVersion(value):
  """ Parse the python version argument """
  cliParams.pythonVersion = value

def parsePlatform(value):
  """ Parse the platform argument """
  cliParams.platform = value

def parseDebug(_):
  """ Parse the debug argument """
  cliParams.debug = True

def parseGrid(value):
  """ Parse the Grid argument """
  cliParams.lcgVer = value

def parseBaseUrl(value):
  """ Parse the base URL argument """
  cliParams.installSource = value

def parseInstallPath(value):
  """ Parse the install Path argument """
  cliParams.targetPath = value
  try:
    os.makedirs( value )
  except Exception as _:
    pass

def parseUseVersionsDir(_):
  """ Parse the version dir argument """
  cliParams.useVersionsDir = True

def parseBuild(_):
  """ Parse the build argument"""
  cliParams.useVersionsDir = True

def parsenoAutoBuild(_):
  """ Parse the no auto build argument """
  cliParams.useVersionsDir = True

def parseExternalsOnly(_):
  """ Parse the externals only argument """
  cliParams.externalsOnly = True

def parseTimeout(value):
  """ Parse the timeout argument"""
  try:
    cliParams.timeout = max( cliParams.timeout, int( value ) )
    cliParams.timeout = min( cliParams.timeout, 3600 )
  except ValueError as _:
    pass

options_dict = {
    '-r': parseRelease,
    '--release': parseRelease,
    '-l': parseProject,
    '--project': parseProject,
    '-e': parseExtraModules,
    '--extraModules': parseExtraModules,
    '-t': parseInstallType,
    '--installType': parseInstallType,
    '-i': parsePythonVersion,
    '--pythonVersion': parsePythonVersion,
    '-p': parsePlatform,
    '--platform' : parsePlatform,
    '-d': parseDebug,
    '--debug': parseDebug,
    '-g': parseGrid,
    '--grid': parseGrid,
    '-u': parseBaseUrl,
    '--baseURL': parseBaseUrl,
    '-P': parseInstallPath,
    '--installationPath': parseInstallPath,
    '-v': parseUseVersionsDir,
    '--useVersionsDir': parseUseVersionsDir,
    '-b': parseBuild,
    '--build': parseBuild,
    '-B': parsenoAutoBuild,
    '--noAutoBuild': parsenoAutoBuild,
    '-X': parseExternalsOnly,
    '--externalsOnly': parseExternalsOnly,
    '-T': parseTimeout,
    '--Timeout': parseTimeout
}

def optionParser(optList):
  """ Option Parser """
  for option, value in optList:
    opt_funct = options_dict.get(option,None)
    if opt_funct:
      opt_funct(value)

def intialOptionParser(optList):
  """ Initial option parse """
  for option, value in optList:
    if option in ( '-h', '--help' ):
      usage()
    elif option in ( '-V', '--installation' ):
      cliParams.installation = value
    elif option in ( "-d", "--debug" ):
      cliParams.debug = True
    elif option in ( "-M", "--defaultsURL" ):
      cliParams.globalDefaults = value

def parseInstallConfOption(releaseConfigInternal):
  """ Parse Installation configuration options"""
  for opName in ( 'release', 'externalsType', 'installType', 'pythonVersion',
                  'buildExternals', 'noAutoBuild', 'debug', 'globalDefaults',
                  'lcgVer', 'useVersionsDir', 'targetPath',
                  'project', 'release', 'extraModules', 'extensions', 'timeout' ):
    try:
      opVal = releaseConfigInternal.getInstallationConfig( "LocalInstallation/%s" % ( opName[0].upper() + opName[1:] ) )
    except KeyError:
      continue
    #Also react to Extensions as if they were extra modules
    if opName == 'extensions':
      opName = 'extraModules'
    if opName == 'installType':
      opName = 'externalsType'
    if isinstance( getattr( cliParams, opName ), basestring ):
      setattr( cliParams, opName, opVal )
    elif isinstance(getattr( cliParams, opName ), types.BooleanType):
      setattr( cliParams, opName, opVal.lower() in ( "y", "yes", "true", "1" ) )
    elif isinstance(getattr( cliParams, opName ), types.ListType):
      setattr( cliParams, opName, [ opV.strip() for opV in opVal.split( "," ) if opV ] )

def loadConfiguration():
  """
  Loads the configuration
  """
  optList, args = getopt.getopt( sys.argv[1:],
                                 "".join( [ opt[0] for opt in cmdOpts ] ),
                                 [ opt[1] for opt in cmdOpts ] )

  # First check if the name is defined
  intialOptionParser(optList)

  releaseConfigInternal = ReleaseConfig( instName = cliParams.installation, globalDefaultsURL = cliParams.globalDefaults )
  if cliParams.debug:
    releaseConfigInternal.genericSetter('__setDebugCB', logDEBUG )

  res = releaseConfigInternal.loadInstallationDefaults()
  if not result[ 'OK' ]:
    logERROR( "Could not load defaults: %s" % res[ 'Message' ] )

  for arg in args:
    if len( arg ) > 4 and arg.find( ".cfg" ) == len( arg ) - 4:
      res = releaseConfigInternal.loadInstallationLocalDefaults( arg )
      if not res[ 'OK' ]:
        logERROR( res[ 'Message' ] )
      else:
        logNOTICE( "Loaded %s" % arg )

  parseInstallConfOption(releaseConfigInternal)

  optionParser(optList)

  if not cliParams.release:
    logERROR( "Missing release to install" )
    usage()

  cliParams.basePath = cliParams.targetPath
  if cliParams.useVersionsDir:
    # install under <installPath>/versions/<version>_<timestamp>
    cliParams.targetPath = os.path.join( cliParams.targetPath, 'versions', '%s_%s' % ( cliParams.release, int( time.time() ) ) )
    try:
      os.makedirs( cliParams.targetPath )
    except Exception as _:
      pass

  logNOTICE( "Destination path for installation is %s" % cliParams.targetPath )
  releaseConfigInternal.genericSetter('__setProject', cliParams.project )

  res = releaseConfigInternal.loadProjectRelease( cliParams.release,
                                                  project = cliParams.project,
                                                  sourceURL = cliParams.installSource )
  if not res[ 'OK' ]:
    return res

  if not releaseConfigInternal.isProjectLoaded( "DIRAC" ):
    return S_ERROR( "DIRAC is not depended by this installation. Aborting" )

  return S_OK( releaseConfigInternal )

def compileExternals( extVersion ):
  """
  Compiles the external components
  """
  logNOTICE( "Compiling externals %s" % extVersion )
  buildCmd = os.path.join( cliParams.targetPath, "DIRAC", "Core", "scripts", "dirac-compile-externals.py" )
  buildCmd = "%s -t '%s' -D '%s' -v '%s' -i '%s'" % ( buildCmd, cliParams.externalsType,
                                                      os.path.join( cliParams.targetPath, cliParams.platform ),
                                                      extVersion,
                                                      cliParams.pythonVersion )
  if os.system( buildCmd ):
    logERROR( "Could not compile binaries" )
    return False
  return True

def installExternals( releaseConfigInternal ):
  """
  Installs the external components
  """
  externalsVersion = releaseConfigInternal.getExtenalsVersion()
  if not externalsVersion:
    logERROR( "No externals defined" )
    return False

  if not cliParams.platform:
    platformPath = os.path.join( cliParams.targetPath, "DIRAC", "Core", "Utilities", "Platform.py" )
    try:
      platFD = open( platformPath, "r" )
    except IOError:
      logERROR( "Cannot open Platform.py. Is DIRAC installed?" )
      return False

    platform = imp.load_module( "Platform", platFD, platformPath, ( "", "r", imp.PY_SOURCE ) )
    platFD.close()
    cliParams.platform = platform.getPlatformString()

  if cliParams.installSource:
    tarsURLInternal = cliParams.installSource
  else:
    tarsURLInternal = releaseConfigInternal.getTarsLocation( 'DIRAC' )[ 'Value' ]

  if cliParams.buildExternals:
    compileExternals( externalsVersion )
  else:
    logDEBUG( "Using platform: %s" % cliParams.platform )
    extVer = "%s-%s-%s-python%s" % ( cliParams.externalsType, externalsVersion, cliParams.platform, cliParams.pythonVersion )
    logDEBUG( "Externals %s are to be installed" % extVer )
    if not downloadAndExtractTarball( tarsURLInternal, "Externals", extVer, cache = True ):
      return ( not cliParams.noAutoBuild ) and compileExternals( externalsVersion )
    logNOTICE( "Fixing externals paths..." )
    fixBuildPaths()
  logNOTICE( "Running externals post install..." )
  checkPlatformAliasLink()
  #lcg utils?
  #LCG utils if required
  lcgVer = releaseConfigInternal.getLCGVersion( cliParams.lcgVer )
  if lcgVer:
    verString = "%s-%s-python%s" % ( lcgVer, cliParams.platform, cliParams.pythonVersion )
    #HACK: try to find a more elegant solution for the lcg bundles location
    if not downloadAndExtractTarball( tarsURLInternal + "/../lcgBundles", "DIRAC-lcg", verString, False, cache = True ):
      logERROR( "Check that there is a release for your platform: DIRAC-lcg-%s" % verString )
  return True

def createPermanentDirLinks():
  """
  Create links to permanent directories from within the version directory
  """
  if cliParams.useVersionsDir:
    try:
      for directory in ['startup', 'runit', 'data', 'work', 'control', 'sbin', 'etc', 'webRoot']:
        fake = os.path.join( cliParams.targetPath, directory )
        real = os.path.join( cliParams.basePath, directory )
        if not os.path.exists( real ):
          os.makedirs( real )
        if os.path.exists( fake ):
          createFakeDirLinks(fake, real)
          os.rename( fake, fake + '.bak' )
        os.symlink( real, fake )
    except Exception, x:
      logERROR( str( x ) )
      return False
  return True

def createFakeDirLinks(fake, real):
  """
  Try to reproduce the directory structure to avoid lacking directories
  """
  fakeDirs = os.listdir( fake)
  for fd in fakeDirs:
    if os.path.isdir( os.path.join( fake, fd ) ):
      if not os.path.exists( os.path.join( real, fd ) ):
        os.makedirs( os.path.join( real, fd ) )

def createOldProLinks():
  """ Create links to permanent directories from within the version directory
  """
  proPath = cliParams.targetPath
  if cliParams.useVersionsDir:
    oldPath = os.path.join( cliParams.basePath, 'old' )
    proPath = os.path.join( cliParams.basePath, 'pro' )
    try:
      if os.path.exists( proPath ) or os.path.islink( proPath ):
        if os.path.exists( oldPath ) or os.path.islink( oldPath ):
          os.unlink( oldPath )
        os.rename( proPath, oldPath )
      os.symlink( cliParams.targetPath, proPath )
    except Exception, x:
      logERROR( str( x ) )
      return False

  return True

def createBashrc():
  """ Create DIRAC environment setting script for the bash shell
  """

  proPath = cliParams.targetPath
  # Now create bashrc at basePath
  try:
    bashrcFile = os.path.join( cliParams.targetPath, 'bashrc' )
    if cliParams.useVersionsDir:
      bashrcFile = os.path.join( cliParams.basePath, 'bashrc' )
      proPath = os.path.join( cliParams.basePath, 'pro' )
    logNOTICE( 'Creating %s' % bashrcFile )
    if not os.path.exists( bashrcFile ):
      lines = [ '# DIRAC bashrc file, used by service and agent run scripts to set environment',
                'export PYTHONUNBUFFERED=yes',
                'export PYTHONOPTIMIZE=x' ]
      if 'HOME' in os.environ:
        lines.append( '[ -z "$HOME" ] && export HOME=%s' % os.environ['HOME'] )
      if 'X509_CERT_DIR' in os.environ:
        lines.append( 'export X509_CERT_DIR=%s' % os.environ['X509_CERT_DIR'] )
      elif not os.path.isdir( "/etc/grid-security/certificates" ):
        tmp_string = "[[ -d '%s/etc/grid-security/certificates' ]] && export "\
                      "X509_CERT_DIR='%s/etc/grid-security/certificates'"
        tmp_string = tmp_string % ( proPath, proPath )
        lines.append(tmp_string)
      lines.append( 'export X509_VOMS_DIR=%s' % os.path.join( proPath, 'etc', 'grid-security', 'vomsdir' ) )
      lines.extend( ['# Some DIRAC locations',
                     '[ -z "$DIRAC" ] && export DIRAC=%s' % proPath,
                     'export DIRACBIN=%s' % os.path.join( "$DIRAC", cliParams.platform, 'bin' ),
                     'export DIRACSCRIPTS=%s' % os.path.join( "$DIRAC", 'scripts' ),
                     'export DIRACLIB=%s' % os.path.join( "$DIRAC", cliParams.platform, 'lib' ),
                     'export TERMINFO=%s' % __getTerminfoLocations( os.path.join( "$DIRAC", cliParams.platform, 'share', 'terminfo' ) ),
                     'export RRD_DEFAULT_FONT=%s' % os.path.join( "$DIRAC", cliParams.platform, 'share',
                                                                  'rrdtool', 'fonts', 'DejaVuSansMono-Roman.ttf' ) ] )

      lines.extend( ['# Prepend the PYTHONPATH, the LD_LIBRARY_PATH, and the DYLD_LIBRARY_PATH'] )

      lines.extend( ['( echo $PATH | grep -q $DIRACBIN ) || export PATH=$DIRACBIN:$PATH',
                     '( echo $PATH | grep -q $DIRACSCRIPTS ) || export PATH=$DIRACSCRIPTS:$PATH',
                     '( echo $LD_LIBRARY_PATH | grep -q $DIRACLIB ) || export LD_LIBRARY_PATH=$DIRACLIB:$LD_LIBRARY_PATH',
                     '( echo $LD_LIBRARY_PATH | grep -q $DIRACLIB/mysql ) || export LD_LIBRARY_PATH=$DIRACLIB/mysql:$LD_LIBRARY_PATH',
                     '( echo $DYLD_LIBRARY_PATH | grep -q $DIRACLIB ) || export DYLD_LIBRARY_PATH=$DIRACLIB:$DYLD_LIBRARY_PATH',
                     '( echo $DYLD_LIBRARY_PATH | grep -q $DIRACLIB/mysql ) || export DYLD_LIBRARY_PATH=$DIRACLIB/mysql:$DYLD_LIBRARY_PATH',
                     '( echo $PYTHONPATH | grep -q $DIRAC ) || export PYTHONPATH=$DIRAC:$PYTHONPATH'] )
      lines.extend( ['# new OpenSSL version require OPENSSL_CONF to point to some accessible location',
                     'export OPENSSL_CONF=/tmp'] )
      # add DIRACPLAT environment variable for client installations
      if cliParams.externalsType == 'client':
        lines.extend( ['# DIRAC platform',
                       '[ -z "$DIRACPLAT" ] && export DIRACPLAT=`$DIRAC/scripts/dirac-platform`'] )
      # Add the lines required for globus-* tools to use IPv6
      lines.extend( ['# IPv6 support',
                     'export GLOBUS_IO_IPV6=TRUE',
                     'export GLOBUS_FTP_CLIENT_IPV6=TRUE'] )
      # Add the lines required for ARC CE support
      lines.extend( ['# ARC Computing Element',
                     'export ARC_PLUGIN_PATH=$DIRACLIB/arc'] )
      lines.append( '' )
      fFile = open( bashrcFile, 'w' )
      fFile.write( '\n'.join( lines ) )
      fFile.close()
  except Exception, x:
    logERROR( str( x ) )
    return False

  return True

def createCshrc():
  """ Create DIRAC environment setting script for the (t)csh shell
  """

  proPath = cliParams.targetPath
  # Now create cshrc at basePath
  try:
    cshrcFile = os.path.join( cliParams.targetPath, 'cshrc' )
    if cliParams.useVersionsDir:
      cshrcFile = os.path.join( cliParams.basePath, 'cshrc' )
      proPath = os.path.join( cliParams.basePath, 'pro' )
    logNOTICE( 'Creating %s' % cshrcFile )
    if not os.path.exists( cshrcFile ):
      lines = [ '# DIRAC cshrc file, used by clients to set up the environment',
                'setenv PYTHONUNBUFFERED yes',
                'setenv PYTHONOPTIMIZE x' ]
      if not 'X509_CERT_DIR' in os.environ and not os.path.isdir( "/etc/grid-security/certificates" ):
        tmp_string = "test -d '%s/etc/grid-security/certificates' && setenv X509_CERT_DIR %s/etc/grid-security/certificates"
        tmp_string = tmp_string %  ( proPath, proPath )
        lines.append(tmp_string)
      lines.append( 'setenv X509_VOMS_DIR %s' % os.path.join( proPath, 'etc', 'grid-security', 'vomsdir' ) )
      lines.extend( ['# Some DIRAC locations',
                     '( test $?DIRAC -eq 1 ) || setenv DIRAC %s' % proPath,
                     'setenv DIRACBIN %s' % os.path.join( "$DIRAC", cliParams.platform, 'bin' ),
                     'setenv DIRACSCRIPTS %s' % os.path.join( "$DIRAC", 'scripts' ),
                     'setenv DIRACLIB %s' % os.path.join( "$DIRAC", cliParams.platform, 'lib' ),
                     'setenv TERMINFO %s' % __getTerminfoLocations( os.path.join( "$DIRAC", cliParams.platform, 'share', 'terminfo' ) ) ] )

      lines.extend( ['# Prepend the PYTHONPATH, the LD_LIBRARY_PATH, and the DYLD_LIBRARY_PATH'] )

      lines.extend( ['( test $?PATH -eq 1 ) || setenv PATH ""',
                     '( test $?LD_LIBRARY_PATH -eq 1 ) || setenv LD_LIBRARY_PATH ""',
                     '( test $?DY_LD_LIBRARY_PATH -eq 1 ) || setenv DYLD_LIBRARY_PATH ""',
                     '( test $?PYTHONPATH -eq 1 ) || setenv PYTHONPATH ""',
                     '( echo $PATH | grep -q $DIRACBIN ) || setenv PATH ${DIRACBIN}:$PATH',
                     '( echo $PATH | grep -q $DIRACSCRIPTS ) || setenv PATH ${DIRACSCRIPTS}:$PATH',
                     '( echo $LD_LIBRARY_PATH | grep -q $DIRACLIB ) || setenv LD_LIBRARY_PATH ${DIRACLIB}:$LD_LIBRARY_PATH',
                     '( echo $LD_LIBRARY_PATH | grep -q $DIRACLIB/mysql ) || setenv LD_LIBRARY_PATH ${DIRACLIB}/mysql:$LD_LIBRARY_PATH',
                     '( echo $DYLD_LIBRARY_PATH | grep -q $DIRACLIB ) || setenv DYLD_LIBRARY_PATH ${DIRACLIB}:$DYLD_LIBRARY_PATH',
                     '( echo $DYLD_LIBRARY_PATH | grep -q $DIRACLIB/mysql ) ||' \
                     'setenv DYLD_LIBRARY_PATH ${DIRACLIB}/mysql:$DYLD_LIBRARY_PATH',
                     '( echo $PYTHONPATH | grep -q $DIRAC ) || setenv PYTHONPATH ${DIRAC}:$PYTHONPATH'] )
      lines.extend( ['# new OpenSSL version require OPENSSL_CONF to point to some accessible location',
                     'setenv OPENSSL_CONF /tmp'] )
      lines.extend( ['# IPv6 support',
                     'setenv GLOBUS_IO_IPV6 TRUE',
                     'setenv GLOBUS_FTP_CLIENT_IPV6 TRUE'] )
      # add DIRACPLAT environment variable for client installations
      if cliParams.externalsType == 'client':
        lines.extend( ['# DIRAC platform',
                       'test $?DIRACPLAT -eq 1 || setenv DIRACPLAT `$DIRAC/scripts/dirac-platform`'] )
      # Add the lines required for ARC CE support
      lines.extend( ['# ARC Computing Element',
                     'setenv ARC_PLUGIN_PATH $DIRACLIB/arc'] )
      lines.append( '' )
      fFile = open( cshrcFile, 'w' )
      fFile.write( '\n'.join( lines ) )
      fFile.close()
  except Exception, x:
    logERROR( str( x ) )
    return False

  return True

def writeDefaultConfiguration():
  """
  Writes the default configuration
  """
  instCFG = releaseConfig.getInstallationCFG()
  if not instCFG:
    return
  for opName in instCFG.getOptions():
    instCFG.delPath( opName )

  # filePath = os.path.join( cliParams.targetPath, "defaults-%s.cfg" % cliParams.installation )
  # Keep the default configuration file in the working directory
  filePath = "defaults-%s.cfg" % cliParams.installation
  try:
    fd = open( filePath, "wb" )
    fd.write( instCFG.toString() )
    fd.close()
  except Exception, excp:
    logERROR( "Could not write %s: %s" % ( filePath, excp ) )
  logNOTICE( "Defaults written to %s" % filePath )

def __getTerminfoLocations( defaultLocation=None ):
  """returns the terminfo locations as a colon separated string"""

  terminfoLocations = []
  if defaultLocation:
    terminfoLocations = [ defaultLocation ]

  for termpath in [ '/usr/share/terminfo', '/etc/terminfo' ]:
    if os.path.exists( termpath ):
      terminfoLocations.append( termpath )

  return ":".join( terminfoLocations )

if __name__ == "__main__":
  logNOTICE( "Processing installation requirements" )
  result = loadConfiguration()
  if not result[ 'OK' ]:
    logERROR( result[ 'Message' ] )
    sys.exit( 1 )
  releaseConfig = result[ 'Value' ]
  if not createPermanentDirLinks():
    sys.exit( 1 )
  if not cliParams.externalsOnly:
    logNOTICE( "Discovering modules to install" )
    result = releaseConfig.getModulesToInstall( cliParams.release, cliParams.extraModules )
    if not result[ 'OK' ]:
      logERROR( result[ 'Message' ] )
      sys.exit( 1 )
    modsOrder, modsToInstall = result[ 'Value' ]
    if cliParams.debug:
      logNOTICE( "Writing down the releases files" )
      releaseConfig.dumpReleasesToPath( cliParams.targetPath )
    logNOTICE( "Installing modules..." )
    for modName in modsOrder:
      tarsURL, modVersion = modsToInstall[ modName ]
      if cliParams.installSource:
        tarsURL = cliParams.installSource
      logNOTICE( "Installing %s:%s" % ( modName, modVersion ) )
      if not downloadAndExtractTarball( tarsURL, modName, modVersion ):
        sys.exit( 1 )
    logNOTICE( "Deploying scripts..." )
    ddeLocation = os.path.join( cliParams.targetPath, "DIRAC", "Core", "scripts", "dirac-deploy-scripts.py" )
    if os.path.isfile( ddeLocation ):
      os.system( ddeLocation )
    else:
      logDEBUG( "No dirac-deploy-scripts found. This doesn't look good" )
  else:
    logNOTICE( "Skipping installing DIRAC" )
  logNOTICE( "Installing %s externals..." % cliParams.externalsType )
  if not installExternals( releaseConfig ):
    sys.exit( 1 )
  if not createOldProLinks():
    sys.exit( 1 )
  if not createBashrc():
    sys.exit( 1 )
  if not createCshrc():
    sys.exit( 1 )
  runExternalsPostInstall()
  writeDefaultConfiguration()
  if cliParams.externalsType == "server":
    fixMySQLScript()
  installExternalRequirements( cliParams.externalsType )
  logNOTICE( "%s properly installed" % cliParams.installation )
  sys.exit( 0 )
