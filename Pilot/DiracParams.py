"""
Parametres class
"""
import os

class Params( object ): # pylint: disable=R0902
  """
  Parametres class
  """

  project = 'DIRAC'
  installation = 'DIRAC'
  release = ""
  externalsType = 'client'
  pythonVersion = '27'
  installSource = ""
  lcgVer = ''
  platform = ""

  def __init__( self ):
    self.extraModules = []
    self.basePath = os.getcwd()
    self.targetPath = os.getcwd()
    self.buildExternals = False
    self.noAutoBuild = False
    self.debug = False
    self.externalsOnly = False
    self.useVersionsDir = False
    self.globalDefaults = False
    self.timeout = 300
