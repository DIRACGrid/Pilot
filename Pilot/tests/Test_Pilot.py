""" Test class for agents
"""

# imports
import unittest
import json
import stat
import sys
import os

from Pilot.pilotTools import PilotParams
from Pilot.pilotCommands import GetPilotVersion, CheckWorkerNode, ConfigureSite, NagiosProbes

class PilotTestCase( unittest.TestCase ):
  """ Base class for the Agents test cases
  """
  def setUp( self ):
    # Define a local file for test, and all the necessary parameters
    with open ( 'pilot.json', 'w' ) as fp:
      json.dump( {'Setups':{'TestSetup':{'Commands':{'cetype1':['x', 'y', 'z'], 
                                                     'cetype2':['d', 'f']}, 
                                         'CommandExtensions':['TestExtension'],
                                         'NagiosProbes':'Nagios1,Nagios2',
                                         'NagiosPutURL':'https://127.0.0.2/',
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
        
  def test_NagiosProbes ( self ):
    # Check pilot.json has been read correctly
    nagios = NagiosProbes( self.pp )
    self.assertEqual( nagios.nagiosProbes, ['Nagios1', 'Nagios2'] )
    self.assertEqual( nagios.nagiosPutURL, 'https://127.0.0.2/' )

    # Now try creating and running some probe scripts
    with open ( 'Nagios1', 'w') as fp:
      fp.write('#!/bin/sh\necho 123\n')
      
    os.chmod( 'Nagios1', stat.S_IRWXU )

    with open ( 'Nagios2', 'w') as fp:
      fp.write('#!/bin/sh\necho 567\n')
      
    os.chmod( 'Nagios2', stat.S_IRWXU )
  
    nagios.execute()

#############################################################################
# Test Suite run
#############################################################################

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( PilotTestCase )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( CommandsTestCase ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )

# EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#
