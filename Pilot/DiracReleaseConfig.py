""" Release config manager """

import os
import types
import hashlib as md5
from Pilot.PilotTools import S_OK, S_ERROR, urlRetriveTimeout

class ReleaseConfig( object ):
  """
  Release config manager
  """

  class CFG(object):
    """
    CFG manager
    """
    def __init__( self, cfgData = "" ):
      self.__data = {}
      self.__children = {}
      if cfgData:
        self.parse( cfgData )

    def getData(self):
      """
      Getter for data
      """
      return self.__data

    def parse( self, cfgData):
      """ Configuration data parser
      """
      try:
        self.__parse( cfgData )
      except:
        import traceback
        traceback.print_exc()
        raise
      return self

    def getChildren(self):
      """ Return the children dict
      """
      return self.__children

    def getChild( self, path ):
      """ Return a child path
      """
      child = self
      pathList = None
      for tmp in [types.ListType, types.TupleType]:
        if path.isinstance(tmp):
          pathList = path
      if pathList is None:
        pathList = [ sec.strip() for sec in path.split( "/" ) if sec.strip() ]
      for childName in pathList:
        if childName not in child.getChildren():
          return None
        child = child.getChildren()[ childName ]
      return child

    def genericWrapper(self, functionName, *args, **kwargs):
      """ Generic wrapper for internal functions """
      return getattr(self,functionName)(*args, **kwargs)

    def __parse( self, cfgData, cIndex = 0 ):
      """
      Parses a configuration data
      """
      childName = ""
      numLine = 0
      while cIndex < len( cfgData ):
        eol = cfgData.find( "\n", cIndex )
        if eol < cIndex:
          #End?
          return cIndex
        numLine += 1
        if eol == cIndex:
          cIndex += 1
          continue
        line = cfgData[ cIndex : eol ].strip()
        #Jump EOL
        cIndex = eol + 1
        if not line or line[0] == "#":
          continue
        if line.find( "+=" ) > -1:
          fields = line.split( "+=" )
          opName = fields[0].strip()
          if opName in self.__data:
            self.__data[ opName ] += ', %s' % '+='.join( fields[1:] ).strip()
          else:
            self.__data[ opName ] = '+='.join( fields[1:] ).strip()
          continue

        if line.find( "=" ) > -1:
          fields = line.split( "=" )
          self.__data[ fields[0].strip() ] = "=".join( fields[1:] ).strip()
          continue

        opFound = line.find( "{" )
        if opFound > -1:
          childName += line[ :opFound ].strip()
          if not childName:
            raise Exception( "No section name defined for opening in line %s" % numLine )
          childName = childName.strip()
          self.__children[ childName ] = ReleaseConfig.CFG()
          eoc = self.__children[ childName ].genericWrapper('__parse', cfgData, cIndex )
          cIndex = eoc
          childName = ""
          continue

        if line == "}":
          return cIndex
        #Must be name for section
        childName += line.strip()
      return cIndex

    def createSection( self, name, cfg = False ):
      """
      Provisions a section based on the name and configuration
      """
      if isinstance( name, ( list, tuple ) ):
        pathList = name
      else:
        pathList = [ sec.strip() for sec in name.split( "/" ) if sec.strip() ]
      parent = self
      for lev in pathList[:-1]:
        if lev not in parent.getChildren():
          parent.getChildren()[ lev ] = ReleaseConfig.CFG()
        parent = parent.getChildren()[ lev ]
      secName = pathList[-1]
      if secName not in parent.getChildren():
        if not cfg:
          cfg = ReleaseConfig.CFG()
        parent.getChildren()[ secName ] = cfg
      return parent.getChildren()[ secName ]

    def isSection( self, obList ):
      """
      Checks if CFG is a section
      """
      return self.__exists( [ ob.strip() for ob in obList.split( "/" ) if ob.strip() ] ) == 2

    def sections( self ):
      """ Returns the sections of CFG"""
      return [ k for k in self.__children ]

    def isOption( self, obList ):
      """
      Checks if CFG is an option
      """
      return self.__exists( [ ob.strip() for ob in obList.split( "/" ) if ob.strip() ] ) == 1

    def options( self ):
      """ Returns the options of CFG"""
      return [ k for k in self.__data ]

    def __exists( self, obList ):
      """
      Perform a verification on obList to verify if it is an option or a section
      """
      if len( obList ) == 1:
        if obList[0] in self.__children:
          return  2
        elif obList[0] in self.__data:
          return 1
        else:
          return 0
      if obList[0] in self.__children:
        return self.__children[ obList[0] ].genericWrapper('__exists', obList[1:] )
      return 0

    def get( self, opName, defaultValue = None ):
      """
      Gets the value for opName key from internal data
      """
      try:
        value = self.__get( [ op.strip() for op in opName.split( "/" ) if op.strip() ] )
      except KeyError:
        if defaultValue is not None:
          return defaultValue
        raise
      if defaultValue is None:
        return value
      defType = type( defaultValue )
      if defType == types.BooleanType:
        return value.lower() in ( "1", "true", "yes" )
      try:
        return defType( value )
      except ValueError:
        return defaultValue

    def __get( self, obList ):
      """ gets the internal value for keys in obList
      """
      if len( obList ) == 1:
        if obList[0] in self.__data:
          return self.__data[ obList[0] ]
        raise KeyError( "Missing option %s" % obList[0] )
      if obList[0] in self.__children:
        return self.__children[ obList[0] ].genericWrapper('__get',obList[1:] )
      raise KeyError( "Missing section %s" % obList[0] )

    def toString( self, tabs = 0 ):
      """
      casts to string
      """
      lines = [ "%s%s = %s" % ( "  " * tabs, opName, self.__data[ opName ] ) for opName in self.__data ]
      for secName in self.__children:
        lines.append( "%s%s" % ( "  " * tabs, secName ) )
        lines.append( "%s{" % ( "  " * tabs ) )
        lines.append( self.__children[ secName ].toString( tabs + 1 ) )
        lines.append( "%s}" % ( "  " * tabs ) )
      return "\n".join( lines )

    def getOptions( self, path = "" ):
      """
      Gets the options
      """
      parentPath = [ sec.strip() for sec in path.split( "/" ) if sec.strip() ][:-1]
      if parentPath:
        parent = self.getChild( parentPath )
      else:
        parent = self
      if not parent:
        return []
      return tuple( parent.getData() )

    def delPath( self, path ):
      """
      Deletes the data values with the keys in the path
      """
      path = [ sec.strip() for sec in path.split( "/" ) if sec.strip() ]
      if not path:
        return
      keyName = path[ -1 ]
      parentPath = path[:-1]
      if parentPath:
        parent = self.getChild( parentPath )
      else:
        parent = self
      if parent:
        parent.getData().pop( keyName )

    def update( self, path, cfg ):
      """
      Updates the configuration based on path
      """
      parent = self.getChild( path )
      if not parent:
        self.createSection( path, cfg )
        return
      parent.genericWrapper('__apply', cfg )

    def __apply( self, cfg ):
      """
      Apply a configuration
      """
      for k in cfg.sections():
        if k in self.__children:
          self.__children[ k ].genericWrapper('__apply',cfg.getChild( k ) )
        else:
          self.__children[ k ] = cfg.getChild( k )
      for k in cfg.options():
        self.__data[ k ] = cfg.get( k )

  ############################################################################
  # END OF CFG CLASS
  ############################################################################
  __loadedCfgs = []
  __prjDepends = {}
  __prjRelCFG = {}
  __projectsLoadedBy = {}
  __cfgCache = {}

  def __init__( self, instName = 'DIRAC', projectName = 'DIRAC', globalDefaultsURL = None, cliParams= None):

    if globalDefaultsURL:
      self.__globalDefaultsURL = globalDefaultsURL
    else:
      self.__globalDefaultsURL = "http://lhcbproject.web.cern.ch/lhcbproject/dist/DIRAC3/globalDefaults.cfg"
    self.__globalDefaults = ReleaseConfig.CFG()


    self.__debugCB = False
    self.__instName = instName
    self.__projectName = projectName
    self.__cliParams = cliParams

  def genericSetter(self, functionName, *args, **kwargs):
    """ Generic setter for attributes"""
    getattr(self, functionName)(*args, **kwargs)

  def genericGetter(self, functionName, *args, **kwargs):
    """ Generic getter for attributes"""
    return getattr(self, functionName)(*args, **kwargs)

  def __getInstallation( self ):
    """ Gets the installation name"""
    return self.__instName

  def __getProject( self ):
    """ Gets the project name """
    return self.__projectName

  def __setInstallation( self, instName ):
    """ Sets the instalation name """
    self.__instName = instName

  def __setProject( self, projectName ):
    """ Sets the project name """
    self.__projectName = projectName

  def __setDebugCB( self, debFunc ):
    """ Sets the debug function """
    self.__debugCB = debFunc

  def __dbgMsg( self, msg ):
    """ Calls the debug function """
    if self.__debugCB:
      self.__debugCB( msg )

  def __loadCFGFromURL( self, urlcfg, checkHash = False ):
    """ Loads the configuration file form a url """
    # This can be a local file
    if os.path.exists( urlcfg ):
      with open( urlcfg, 'r' ) as relFile:
        cfgData = relFile.read()
    else:
      if urlcfg in self.__cfgCache:
        return S_OK( self.__cfgCache[ urlcfg ] )
      try:
        cfgData = urlRetriveTimeout( urlcfg, timeout = self.__cliParams.timeout )
        if not cfgData:
          return S_ERROR( "Could not get data from %s" % urlcfg )
      except Exception, excp:
        return S_ERROR( "Could not open %s" % urlcfg )
    try:
      #cfgData = cfgFile.read()
      cfg = ReleaseConfig.CFG( cfgData )
    except Exception, excp:
      return S_ERROR( "Could not parse %s: %s" % ( urlcfg, excp ) )
    #cfgFile.close()
    if not checkHash:
      self.__cfgCache[ urlcfg ] = cfg
      return S_OK( cfg )
    try:
      md5Data = urlRetriveTimeout( urlcfg[:-4] + ".md5", timeout = 60 )
      md5Hex = md5Data.strip()
      #md5File.close()
      if md5Hex != md5.md5( cfgData ).hexdigest():
        return S_ERROR( "Hash check failed on %s" % urlcfg )
    except Exception, excp:
      return S_ERROR( "Hash check failed on %s: %s" % ( urlcfg, excp ) )
    self.__cfgCache[ urlcfg ] = cfg
    return S_OK( cfg )

  def loadInstallationDefaults( self ):
    """ Loads the installation defaults"""
    res = self.__loadGlobalDefaults()
    if not res[ 'OK' ]:
      return res
    return self.__loadObjectDefaults( "Installations", self.__instName )

  def loadProjectDefaults( self ):
    """ Loads the project defaults"""
    res = self.__loadGlobalDefaults()
    if not res[ 'OK' ]:
      return res
    return self.__loadObjectDefaults( "Projects", self.__projectName )

  def __loadGlobalDefaults( self ):
    """
    Loads the global defaults
    """
    self.__dbgMsg( "Loading global defaults from: %s" % self.__globalDefaultsURL )
    res = self.__loadCFGFromURL( self.__globalDefaultsURL )
    if not res[ 'OK' ]:
      return res
    self.__globalDefaults = res[ 'Value' ]
    for k in ( "Installations", "Projects" ):
      if not self.__globalDefaults.isSection( k ):
        self.__globalDefaults.createSection( k )
    self.__dbgMsg( "Loaded global defaults" )
    return S_OK()

  def __loadObjectDefaults( self, rootPath, objectName ):
    """
    Loads the object defaults
    """
    basePath = "%s/%s" % ( rootPath, objectName )
    if basePath in self.__loadedCfgs:
      return S_OK()

    #Check if it's a direct alias
    try:
      aliasTo = self.__globalDefaults.get( basePath )
    except KeyError:
      aliasTo = False

    if aliasTo:
      self.__dbgMsg( "%s is an alias to %s" % ( objectName, aliasTo ) )
      res = self.__loadObjectDefaults( rootPath, aliasTo )
      if not res[ 'OK' ]:
        return res
      cfg = res[ 'Value' ]
      self.__globalDefaults.update( basePath, cfg )
      return S_OK()

    #Load the defaults
    if self.__globalDefaults.get( "%s/SkipDefaults" % basePath, False ):
      defaultsLocation = ""
    else:
      defaultsLocation = self.__globalDefaults.get( "%s/DefaultsLocation" % basePath, "" )

    if not defaultsLocation:
      self.__dbgMsg( "No defaults file defined for %s %s" % ( rootPath.lower()[:-1], objectName ) )
    else:
      self.__dbgMsg( "Defaults for %s are in %s" % ( basePath, defaultsLocation ) )
      res = self.__loadCFGFromURL( defaultsLocation )
      if not res[ 'OK' ]:
        return res
      cfg = res[ 'Value' ]
      self.__globalDefaults.update( basePath, cfg )

    #Check if the defaults have a sub alias
    try:
      aliasTo = self.__globalDefaults.get( "%s/Alias" % basePath )
    except KeyError:
      aliasTo = False

    if aliasTo:
      self.__dbgMsg( "%s is an alias to %s" % ( objectName, aliasTo ) )
      res = self.__loadObjectDefaults( rootPath, aliasTo )
      if not res[ 'OK' ]:
        return res
      cfg = res[ 'Value' ]
      self.__globalDefaults.update( basePath, cfg )

    self.__loadedCfgs.append( basePath )
    return S_OK( self.__globalDefaults.getChild( basePath ) )

  def loadInstallationLocalDefaults( self, fileName ):
    """
    Loads the installation local defaults
    """
    try:
      fd = open( fileName, "r" )
      #TODO: Merge with installation CFG
      cfg = ReleaseConfig.CFG().parse( fd.read() )
      fd.close()
    except Exception, excp :
      return S_ERROR( "Could not load %s: %s" % ( fileName, excp ) )
    self.__globalDefaults.update( "Installations/%s" % self.genericGetter('__getInstallation'), cfg )
    return S_OK()

  def getInstallationCFG( self, instName = False ):
    """
    Gets the installation configuration file
    """
    if not instName:
      instName = self.__instName
    return self.__globalDefaults.getChild( "Installations/%s" % instName )

  def getInstallationConfig( self, opName, instName = False ):
    """
    Gets the installation config
    """
    if not instName:
      instName = self.__instName
    return self.__globalDefaults.get( "Installations/%s/%s" % ( instName, opName ) )

  def isProjectLoaded( self, project ):
    """
    Checks if the project is loaded
    """
    return project in self.__prjRelCFG

  def getTarsLocation( self, project ):
    """
    Gets the tars locations
    """
    defLoc = self.__globalDefaults.get( "Projects/%s/BaseURL" % project, "" )
    if defLoc:
      return S_OK( defLoc )
    return S_ERROR( "Don't know how to find the installation tarballs for project %s" % project )

  def getUploadCommand( self, project = False ):
    """
    Gets the upload command
    """
    if not project:
      project = self.__projectName
    defLoc = self.__globalDefaults.get( "Projects/%s/UploadCommand" % project, "" )
    if defLoc:
      return S_OK( defLoc )
    return S_ERROR( "No UploadCommand for %s" % project )

  def __loadReleaseConfig( self, project, release, releaseMode, sourceURL = None, relLocation = False ):
    """
    Loads the release configuration
    """
    if project not in self.__prjRelCFG:
      self.__prjRelCFG[ project ] = {}
    if release in self.__prjRelCFG[ project ]:
      self.__dbgMsg( "Release config for %s:%s has already been loaded" % ( project, release ) )
      return S_OK()

    if relLocation:
      relcfgLoc = relLocation
    else:
      if releaseMode:
        try:
          relcfgLoc = self.__globalDefaults.get( "Projects/%s/Releases" % project )
        except KeyError:
          return S_ERROR( "Missing Releases file for project %s" % project )
      else:
        if not sourceURL:
          res = self.getTarsLocation( project )
          if not res[ 'OK' ]:
            return res
          siu = res[ 'Value' ]
        else:
          siu = sourceURL
        relcfgLoc = "%s/release-%s-%s.cfg" % ( siu, project, release )
    self.__dbgMsg( "Releases file is %s" % relcfgLoc )
    res = self.__loadCFGFromURL( relcfgLoc, checkHash = not releaseMode )
    if not res[ 'OK' ]:
      return res
    self.__prjRelCFG[ project ][ release ] = res[ 'Value' ]
    self.__dbgMsg( "Loaded releases file %s" % relcfgLoc )

    return S_OK( self.__prjRelCFG[ project ][ release ] )

  def getReleaseCFG( self, project, release ):
    """
    Gets the release CFG
    """
    return self.__prjRelCFG[ project ][ release ]

  def dumpReleasesToPath( self, _ ):
    """
    Dumps the release to path
    """
    for project in self.__prjRelCFG:
      prjRels = self.__prjRelCFG[ project ]
      for release in prjRels:
        self.__dbgMsg( "Dumping releases file for %s:%s" % ( project, release ) )
        fd = open( os.path.join( self.__cliParams.targetPath, "releases-%s-%s.cfg" % ( project, release ) ), "w" )
        fd.write( prjRels[ release ].toString() )
        fd.close()

  def __checkCircularDependencies( self, key, routePath = None ):
    """
    Checks for circular dependencies
    """
    if not routePath:
      routePath = []
    if key not in self.__projectsLoadedBy:
      return S_OK()
    routePath.insert( 0, key )
    for lKey in self.__projectsLoadedBy[ key ]:
      if lKey in routePath:
        routePath.insert( 0, lKey )
        route = "->".join( [ "%s:%s" % sKey for sKey in routePath ] )
        return S_ERROR( "Circular dependency found for %s: %s" % ( "%s:%s" % lKey, route ) )
      res = self.__checkCircularDependencies( lKey, routePath )
      if not res[ 'OK' ]:
        return res
    routePath.pop( 0 )
    return S_OK()

  def __parseIntialDeps(self, initialDeps, project, release, relDeps):
    """ Parse release intial dependenceies"""
    for depProject in initialDeps:
      depVersion = initialDeps[ depProject ]

      #Check if already processed
      dKey = ( depProject, depVersion )
      self.__projectsLoadedBy[ dKey ] = [] if dKey not in self.__projectsLoadedBy else self.__projectsLoadedBy[ dKey ]
      self.__projectsLoadedBy[ dKey ].append( ( project, release ) )
      res = self.__checkCircularDependencies( dKey )
      if not res[ 'OK' ]:
        return res
      #if it has already been processed just return OK
      if len( self.__projectsLoadedBy[ dKey ] ) > 1:
        return (True, S_OK(), None)

      #Load dependencies and calculate incompatibilities
      res = self.loadProjectRelease( depVersion, project = depProject )
      if not res[ 'OK' ]:
        return (True, res, None)
      subDep = self.__prjDepends[ depProject ][ depVersion ]
      #Merge dependencies
      for sKey in subDep:
        if sKey not in relDeps:
          relDeps.append( sKey )
          continue
        prj, vrs = sKey
        for pKey in relDeps:
          if pKey[0] == prj and pKey[1] != vrs:
            errMsg = "%s is required with two different versions ( %s and %s ) starting with %s:%s" % ( prj,
                                                                                                        pKey[1], vrs,
                                                                                                        project, release )
            return (True, S_ERROR( errMsg ), None)
        #Same version already required
    return (False, None, relDeps)

  def loadProjectRelease( self, releases, project = False, sourceURL = False, releaseMode = False, relLocation = False ):
    """
    Loads a project release
    """
    project = self.__projectName if not project else project

    releases = [ releases ] if not isinstance(releases, (types.ListType, types.TupleType)) else releases

    #Load defaults
    res = self.__loadObjectDefaults( "Projects", project )
    if not res[ 'OK' ]:
      self.__dbgMsg( "Could not load defaults for project %s" % project )
      return res

    self.__prjDepends[project] = {} if project not in self.__prjDepends else self.__prjDepends[project]


    for release in releases:
      self.__dbgMsg( "Processing dependencies for %s:%s" % ( project, release ) )
      res = self.__loadReleaseConfig( project, release, releaseMode, sourceURL, relLocation )
      if not res[ 'OK' ]:
        return res
      relCFG = res[ 'Value' ]


      #Calculate dependencies and avoid circular deps
      self.__prjDepends[ project ][ release ] = [ ( project, release ) ]
      relDeps = self.__prjDepends[ project ][ release ]

      if not relCFG.getChild( "Releases/%s" % ( release ) ):
        return S_ERROR( "Release %s is not defined for project %s in the release file" % ( release, project ) )

      initialDeps = self.getReleaseDependencies( project, release )
      if initialDeps:
        self.__dbgMsg( "%s %s depends on %s" % ( project, release, ", ".join( [ "%s:%s" % ( k, initialDeps[k] ) for k in initialDeps ] ) ) )
      relDeps.extend( [ ( p, initialDeps[p] ) for p in initialDeps ] )
      (return_code, return_value, relDeps) =  self.__parseIntialDeps(initialDeps, project, release, relDeps)
      if return_code:
        return return_value
      if project in relDeps and relDeps[ project ] != release:
        errMsg = "%s:%s requires itself with a different version through dependencies ( %s )" % ( project, release,
                                                                                                  relDeps[ project ] )
        return S_ERROR( errMsg )

    return S_OK()

  def getReleaseOption( self, project, release, option ):
    """
    Gets the release options
    """
    try:
      return self.__prjRelCFG[ project ][ release ].get( option )
    except KeyError:
      self.__dbgMsg( "Missing option %s for %s:%s" % ( option, project, release ) )
      return None

  def getReleaseDependencies( self, project, release ):
    """
    Gets the release dependencies
    """
    try:
      data = self.__prjRelCFG[ project ][ release ].get( "Releases/%s/Depends" % release )
    except KeyError:
      return {}
    data = [ field for field in data.split( "," ) if field.strip() ]
    deps = {}
    for field in data:
      field = field.strip()
      if not field:
        continue
      pv = field.split( ":" )
      if len( pv ) == 1:
        deps[ pv[0].strip() ] = release
      else:
        deps[ pv[0].strip() ] = ":".join( pv[1:] ).strip()
    return deps

  def getModulesForRelease( self, release, project = False ):
    """
    Gets the modules for release
    """
    if not project:
      project = self.__projectName
    if not project in self.__prjRelCFG:
      return S_ERROR( "Project %s has not been loaded. I'm a MEGA BUG! Please report me!" % project )
    if not release in self.__prjRelCFG[ project ]:
      return S_ERROR( "Version %s has not been loaded for project %s" % ( release, project ) )
    config = self.__prjRelCFG[ project ][ release ]
    if not config.isSection( "Releases/%s" % release ):
      return S_ERROR( "Release %s is not defined for project %s" % ( release, project ) )
    #Defined Modules explicitly in the release
    modules = self.getReleaseOption( project, release, "Releases/%s/Modules" % release )
    if modules:
      dMods = {}
      for entry in [ entry.split( ":" ) for entry in modules.split( "," ) if entry.strip() ]:
        if len( entry ) == 1:
          dMods[ entry[0].strip() ] = release
        else:
          dMods[ entry[0].strip() ] = entry[1].strip()
      modules = dMods
    else:
      #Default modules with the same version as the release version
      modules = self.getReleaseOption( project, release, "DefaultModules" )
      #Mod = project and same version
      modules = dict((modName.strip() , release) for modName in modules.split(",") if modName.strip()) if modules else {project:release }
    #Check project is in the modNames if not DIRAC
    if project != "DIRAC":
      for modNameOutsideDirac in modules:
        if modNameOutsideDirac.find( project ) != 0:
          return S_ERROR( "Module %s does not start with the name %s" % ( modNameOutsideDirac, project ) )
    return S_OK( modules )

  def getModSource( self, release, modNameInternal ):
    """
    Gets the mod source
    """
    if self.__projectName not in self.__prjRelCFG:
      return S_ERROR( "Project %s has not been loaded. I'm a MEGA BUG! Please report me!" % self.__projectName )
    modLocation = self.getReleaseOption( self.__projectName, release, "Sources/%s" % modNameInternal )
    if not modLocation:
      return S_ERROR( "Source origin for module %s is not defined" % modNameInternal )
    modTpl = [ field.strip() for field in modLocation.split( "|" ) if field.strip() ]
    if len( modTpl ) == 1:
      return S_OK( ( False, modTpl[0] ) )
    return S_OK( ( modTpl[0], modTpl[1] ) )

  def getExtenalsVersion( self, release = False ):
    """
    Gets the external Version
    """
    if 'DIRAC' not in self.__prjRelCFG:
      return False
    if not release:
      release = list( self.__prjRelCFG[ 'DIRAC' ] )
      release = max( release )
    try:
      return self.__prjRelCFG[ 'DIRAC' ][ release ].get( 'Releases/%s/Externals' % release )
    except KeyError:
      return False

  def getLCGVersion( self, lcgVersion = "" ):
    """
    Gets LCG version
    """
    if lcgVersion:
      return lcgVersion
    for _ in self.__projectsLoadedBy:
      try:
        return self.__prjRelCFG[ self.__projectName ][ self.__cliParams.release ].get("Releases/%s/LcgVer"
                                                                                      % self.__cliParams.release, lcgVersion )
      except KeyError:
        pass
    return lcgVersion

  def _parseProjects(self, projects, extraModules, extraFound, modsToInstallInternal, modsOrderInternal):
    """ Parse projects """
    for project, relVersion in projects:
      try:
        requiredModules = self.__prjRelCFG[ project ][ relVersion ].get( "RequiredExtraModules" )
        requiredModules = [ modNameInternal.strip() for modNameInternal in requiredModules.split( "/" ) if modNameInternal.strip() ]
      except KeyError:
        requiredModules = []
      extraModules.extends([modNameInternal for modNameInternal in requiredModules if modNameInternal not in extraModules])
      res = self.getTarsLocation( project )
      if not res[ 'OK' ]:
        return (res, None, None, None, None)
      tarsPath = res[ 'Value' ]
      self.__dbgMsg( "Discovering modules to install for %s (%s)" % ( project, relVersion ) )
      res = self.getModulesForRelease( relVersion, project )
      if not res[ 'OK' ]:
        return (res, None, None, None, None)
      modVersions = res[ 'Value' ]
      try:
        defaultMods = self.__prjRelCFG[ project ][ relVersion ].get( "DefaultModules" )
        modNames = [ mod.strip() for mod in defaultMods.split( "," ) if mod.strip() ]
      except KeyError:
        modNames = []
      for extraMod in extraModules:
        # Check if the version of the extension module is specified in the command line
        extraVersion = None
        if ":" in extraMod:
          extraMod, extraVersion = extraMod.split( ":" )
          modVersions[extraMod] = extraVersion
        if extraMod in modVersions:
          modNames.append( extraMod )
          extraFound.append( extraMod )
        if project != 'DIRAC':
          dExtraMod = "%sDIRAC" % extraMod
          if dExtraMod in modVersions:
            modNames.append( dExtraMod )
            extraFound.append( extraMod )
      modNameVer = [ "%s:%s" % ( modNameInternal, modVersions[ modNameInternal ] ) for modNameInternal in modNames ]
      self.__dbgMsg( "Modules to be installed for %s are: %s" % ( project, ", ".join( modNameVer ) ) )
      for modNameInternal in modNames:
        modsToInstallInternal[ modNameInternal ] = ( tarsPath, modVersions[ modNameInternal ] )
        modsOrderInternal.insert( 0, modNameInternal )
      return (None, extraModules, extraFound, modsToInstallInternal, modsOrderInternal)

  def getModulesToInstall( self, release, extraModules = False ):
    """
    Gets the modules to install
    """
    if not extraModules:
      extraModules = []
    extraFound = []
    modsToInstallInternal = {}
    modsOrderInternal = []
    if self.__projectName not in self.__prjDepends:
      return S_ERROR( "Project %s has not been loaded" % self.__projectName )
    if release not in self.__prjDepends[ self.__projectName ]:
      return S_ERROR( "Version %s has not been loaded for project %s" % ( release, self.__projectName ) )
    #Get a list of projects with their releases
    projects = list( self.__prjDepends[ self.__projectName ][ release ] )
    (res, extraModules, extraFound, modsToInstallInternal, modsOrderInternal) = self._parseProjects(projects,
                                                                                                    extraModules,
                                                                                                    extraFound,
                                                                                                    modsToInstallInternal,
                                                                                                    modsOrderInternal)
    if not res:
      return res
    for modNameInternal in extraModules:
      if modNameInternal.split(":")[0] not in extraFound:
        return S_ERROR( "No module %s defined. You sure it's defined for this release?" % modNameInternal )

    return S_OK( ( modsOrderInternal, modsToInstallInternal ) )


#################################################################################
# End of ReleaseConfig
#################################################################################
