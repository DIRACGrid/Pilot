""" Test class for agents
"""

# imports
import unittest
import json
import sys
import os

from Pilot.PilotTools import PilotParams
from Pilot.PilotCommands import CheckWorkerNode, ConfigureSite

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

    self.pilotParams = PilotParams()

  def tearDown( self ):
    try:
      os.remove( 'pilot.json' )
    except IOError:
      pass


class CommandsTestCase( PilotTestCase ):
  """ Command test cases """

  def test_InitJSON( self ):
    """ Test init Json"""
    self.assertEqual( self.pilotParams.commands, ['x', 'y', 'z'] )
    self.assertEqual( self.pilotParams.commandExtensions, ['TestExtension'] )

  def test_CheckWorkerNode ( self ):
    """ Test worker node """
    CheckWorkerNode( self.pilotParams )

  def test_ConfigureSite ( self ):
    """ Test configure Site """
    self.pilotParams.configureScript = 'echo'
    ConfigureSite( self.pilotParams )


#############################################################################
# Test Suite run
#############################################################################

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( PilotTestCase )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( CommandsTestCase ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )

# EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#
