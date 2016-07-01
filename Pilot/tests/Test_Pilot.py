""" Test class for agents
"""

# imports
import unittest
import json
import os

from Pilot.pilotTools import PilotParams, CommandBase
from Pilot.pilotCommands import GetPilotVersion

class PilotTestCase( unittest.TestCase ):
  """ Base class for the Agents test cases
  """
  def setUp( self ):
    self.pp = PilotParams()

  def tearDown( self ):
    try:
      os.remove( 'pilot.out' )
      os.remove( 'pilot.json' )
      os.remove( 'pilot.json-local' )
    except OSError:
      pass


class CommandsTestCase( PilotTestCase ):

  def test_commandBase(self):
    cb = CommandBase(self.pp)
    returnCode, _outputData = cb.executeAndGetOutput("ls")
    self.assertEqual(returnCode, 0)

  def test_GetPilotVersion( self ):

    # Now defining a local file for test, and all the necessary parameters
    fp = open( 'pilot.json', 'w' )
    json.dump( {'TestSetup':{'Commands':{'grid1':['x', 'y', 'z'], 'grid2':['d', 'f']}, 'Version':['v1r1', 'v2r2']}}, fp )
    fp.close()
    self.pp.setup = 'TestSetup'
    self.pp.pilotCFGFileLocation = 'file://%s' % os.getcwd()
    gpv = GetPilotVersion( self.pp )
    self.assertTrue( gpv.execute() is None )
    self.assertEqual( gpv.pp.releaseVersion, 'v1r1' )

  def test_RetrievePilotParameters( self ):
    with open ( 'pilot.json', 'w' ) as fp:
      json.dump( {'TestSetup':{'Commands':{'grid1':['x', 'y', 'z'], 'grid2':['d', 'f']}, 'Extensions':['TestExtension'],
                             'Version':['v1r1', 'v2r2']}}, fp )
    self.pp.setup = 'TestSetup'
    self.pp.site = 'grid1.cern.ch'
    self.pp.pilotCFGFileLocation = 'file://%s' % os.getcwd()
    self.pp.retrievePilotParameters()
    self.assertEqual( self.pp.commands, ['x', 'y', 'z'] )
    self.assertEqual( self.pp.commandExtensions, ['TestExtension'] )

#############################################################################
# Test Suite run
#############################################################################

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( PilotTestCase )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( CommandsTestCase ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )

# EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#
