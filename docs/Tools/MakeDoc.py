#!/usr/bin/env python
""" create rst files for documentation of Pilot """
import os
import shutil
import sys

def mkdir( folder ):
  """create a folder, ignore if it exists"""
  try:
    folder = os.path.join(os.getcwd(),folder)
    os.mkdir( folder )
  except OSError as e:
    print "MakeDoc: Exception %s when creating folder" %repr(e), folder


BASEPATH = "docs/source/CodeDocumentation"
PilotPATH = os.environ.get("Pilot","") + "/Pilot"

ORIGDIR = os.getcwd()

BASEPATH = os.path.join( PilotPATH, BASEPATH )

def mkRest( filename, modulename, fullmodulename, subpackages=None, modules=None ):
  """make a rst file for filename"""
  if modulename == "scripts":
    return
    #modulefinal = fullmodulename.split(".")[-2]+" Scripts"
  else:
    modulefinal = modulename

  lines = []
  lines.append("%s" % modulefinal)
  lines.append("="*len(modulefinal))
  lines.append(".. module:: %s " % fullmodulename )
  lines.append("" )

  if subpackages or modules:
    lines.append(".. toctree::")
    lines.append("   :maxdepth: 1")
    lines.append("")

  subpackages = [ s for s in subpackages if not s.endswith( ("scripts", ) ) ]
  if subpackages:
    print "MakeDoc: ",modulename, " subpackages ", subpackages
    lines.append( "SubPackages" )
    lines.append( "..........." )
    lines.append( "" )
    lines.append(".. toctree::")
    lines.append("   :maxdepth: 1")
    lines.append("")
    for package in sorted(subpackages):
      lines.append("   %s/%s_Module.rst" % (package,package.split("/")[-1] ) )
      #lines.append("   %s " % (package, ) )

  with open(filename, 'w') as rst:
    rst.write("\n".join(lines))


def mkModuleRest( classname, fullclassname, buildtype="full"):
  """ create rst file for class"""
  filename = classname+".rst"

  lines = []
  lines.append("%s" % classname)
  lines.append("="*len(classname))

  # if "-" not in classname:
  #   lines.append(".. autosummary::" )
  #   lines.append("   :toctree: %sGen" % classname )
  #   lines.append("")
  #   lines.append("   %s " % fullclassname )
  #   lines.append("")

  lines.append(".. automodule:: %s" % fullclassname )
  if buildtype == "full":
    lines.append("   :members:" )
    lines.append("   :inherited-members:" )
    lines.append("   :undoc-members:" )
    lines.append("   :show-inheritance:" )
    if classname.startswith("_"):
      lines.append( "   :private-members:" )

  with open(filename, 'w') as rst:
    rst.write("\n".join(lines))


def getsubpackages( abspath, direc):
  """return list of subpackages with full path"""
  packages = []
  for dire in direc:
    if "/test" in dire.lower():
      print "MakeDoc: skipping this directory", dire
      continue
    if os.path.exists( os.path.join( PilotPATH,abspath,dire, "__init__.py" ) ):
      #packages.append( os.path.join( "DOC", abspath, dire) )
      packages.append( os.path.join( dire ) )
  return packages

def getmodules( _abspath, _direc, files ):
  """return list of subpackages with full path"""
  packages = []
  for filename in files:
    if "test" in filename.lower():
      print "MakeDoc: Skipping this file", filename
      continue
    if filename != "__init__.py":
      packages.append( filename.split(".py")[0] )

  return packages


def createDoc(buildtype = "full"):
  """create the rst files for all the things we want them for"""
  print "MakeDoc: PilotPATH",PilotPATH
  print "MakeDoc: BASEPATH", BASEPATH

  ## we need to replace existing rst files so we can decide how much code-doc to create
  if os.path.exists(BASEPATH):
    shutil.rmtree(BASEPATH)
  mkdir(BASEPATH)
  os.chdir(BASEPATH)
  print "MakeDoc: Now creating rst files"
  for root,direc,files in os.walk(PilotPATH):
    files = [ _ for _ in files if _.endswith(".py") ]
    if "__init__.py" not in files:
      continue

    if any( root.lower().endswith( f.lower() ) for f in ("/docs", ) ):
      continue
    elif any( f.lower() in root.lower() for f in ("/test", "scripts",
                                                 ) ):
      print "MakeDoc: Skipping this folder:", root
      continue

    modulename = root.split("/")[-1]
    abspath = root.split(PilotPATH)[1].strip("/")
    fullmodulename = ".".join(abspath.split("/"))
    packages = getsubpackages(abspath,direc)
    if abspath:
      mkdir( abspath )
      os.chdir( abspath )
    if modulename == "Pilot":
      createCodeDocIndex(subpackages=packages, modules=getmodules(abspath, direc, files), buildtype=buildtype)
    else:
      mkRest( modulename+"_Module.rst", modulename, fullmodulename, subpackages=packages, modules=getmodules(abspath, direc, files) )

    os.chdir(BASEPATH)
  return 0

def createCodeDocIndex( subpackages, modules, buildtype="full"):
  """create the main index file"""
  filename = "index.rst"
  lines = []
  lines.append( ".. _code_documentation:")
  lines.append("")
  lines.append( "Code Documentation (|release|)" )
  lines.append( "------------------------------" )

  ## for limited builds we only create the most basic code documentation so we let users know there is more elsewhere
  if buildtype == "limited":
    lines.append( "" )
    lines.append( ".. warning::" )
    lines.append( "  This a limited build of the code documentation, for the full code documentation please look at the website" )
    lines.append( "" )

  if subpackages or modules:
    lines.append(".. toctree::")
    lines.append("   :maxdepth: 1")
    lines.append("")

  if subpackages:
    systemPackages = sorted([ pck for pck in subpackages if pck.endswith("System") ])
    otherPackages = sorted([ pck for pck in subpackages if not pck.endswith("System") ])

    lines.append( "=======" )
    lines.append( "Systems" )
    lines.append( "=======" )
    lines.append("")
    lines.append(".. toctree::")
    lines.append("   :maxdepth: 1")
    lines.append("")
    for package in systemPackages:
      lines.append("   %s/%s_Module.rst" % (package,package.split("/")[-1] ) )

    lines.append("")
    lines.append( "=====" )
    lines.append( "Other" )
    lines.append( "=====" )
    lines.append("")
    lines.append(".. toctree::")
    lines.append("   :maxdepth: 1")
    lines.append("")
    for package in otherPackages:
      lines.append("   %s/%s_Module.rst" % (package,package.split("/")[-1] ) )

  if modules:
    for module in sorted(modules):
      lines.append("   %s.rst" % (module.split("/")[-1],) )
      #lines.append("   %s " % (package, ) )

  with open(filename, 'w') as rst:
    rst.write("\n".join(lines))


def checkBuildTypeAndRun():
  """ check for input argument and then create the doc rst files """
  buildtypes = ( "full", "limited")
  buildtype = "full" if len(sys.argv) <= 1 else sys.argv[1]
  if buildtype not in buildtypes:
    print "MakeDoc: Unknown build type: %s use %s " %( buildtype, " ".join(buildtypes) )
    return 1
  print "MakeDoc: buildtype:", buildtype
  exit(createDoc(buildtype))

if __name__ == "__main__":
  ### get the options
  exit(checkBuildTypeAndRun())
