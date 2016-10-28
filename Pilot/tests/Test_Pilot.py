""" Test class for agents
"""

# imports
import unittest
import json
import sys
import os

from Pilot.pilotTools import PilotParams
from Pilot.pilotCommands import GetPilotVersion, CheckWorkerNode, ConfigureSite

class PilotTestCase( unittest.TestCase ):
  """ Base class for the Agents test cases
  """
  def setUp( self ):
    # Define a local file for test, and all the necessary parameters
    with open ( 'pilot.json', 'w' ) as fp:
      json.dump( {'Setups':{'TestSetup':{'Commands':{'cetype1':['x', 'y', 'z'], 
                                                     'cetype2':['d', 'f']}, 
                                         'CommandExtensions':['TestExtension'],
                                         'Version':['v1r1','v2r2']}},
                  'CEs':{'grid1.example.com':{'GridCEType':'cetype1','Site':'site.example.com'}},
                  'DefaultSetup':'TestSetup'}, 
                 fp )
                
    sys.argv[1:] = ['--Name', 'grid1.example.com']

    self.pp = PilotParams()
  
  def tearDown( self ):
    try:
      os.remove( 'pilot.json' )
    except IOError:
      pass


class CommandsTestCase( PilotTestCase ):

  def test_InitJSON( self ):
    self.assertEqual( self.pp.commands, ['x', 'y', 'z'] )
    self.assertEqual( self.pp.commandExtensions, ['TestExtension'] )
    
  def test_CheckWorkerNode ( self ):
    CheckWorkerNode( self.pp )
        
  def test_ConfigureSite ( self ):
    self.pp.configureScript = 'echo'
    ConfigureSite( self.pp )
        

#############################################################################
# Test Suite run
#############################################################################

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( PilotTestCase )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( CommandsTestCase ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )

# EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#
