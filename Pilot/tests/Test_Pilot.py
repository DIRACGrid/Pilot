""" Test class for agents
"""

# imports
import unittest
import json
import stat
import sys
import os

from Pilot.pilotTools import PilotParams
from Pilot.pilotCommands import CheckWorkerNode, ConfigureSite, NagiosProbes

class PilotTestCase( unittest.TestCase ):
  """ Base class for the Agents test cases
  """
  def setUp( self ):
    # Define a local file for test, and all the necessary parameters
    with open ( 'pilot.json', 'w' ) as fp:
      json.dump( {'Setups':{'TestSetup':{'Commands':{'cetype1': 'x,y, z' ,
                                                     'cetype2':['d', 'f']},
                                         'CommandExtensions':'TestExtension1,TestExtension2',
                                         'NagiosProbes':'Nagios1,Nagios2',
                                         'NagiosPutURL':'https://127.0.0.2/',
                                         'Version':['v1r1','v2r2']}},
                  'CEs':{'grid1.example.com':{'GridCEType':'cetype1','Site':'site.example.com'}},
                  'DefaultSetup':'TestSetup'},
                 fp )

    sys.argv[1:] = ['--Name', 'grid1.example.com', '--commandOptions', 'a=1,b=2', '-Z', 'c=3' ]

    self.pp = PilotParams()
    
  def tearDown( self ):
    try:
      os.remove( 'pilot.json' )
    except IOError:
      pass

class CommandsTestCase( PilotTestCase ):
  """ Test case for each pilot command
  """

  def test_InitJSON( self ):
    """ Test the pilot.json and command line parsing
    """
    self.assertEqual( self.pp.commands, ['x', 'y', 'z'] )
    self.assertEqual( self.pp.commandExtensions, ['TestExtension1','TestExtension2'] )

    self.assertEqual( self.commandOptions['a'], '1' )
    self.assertEqual( self.commandOptions['b'], '2' )
    self.assertEqual( self.commandOptions['c'], '3' )

  def test_CheckWorkerNode ( self ):
    """ Test CheckWorkerNode command
    """
    CheckWorkerNode( self.pp )

  def test_ConfigureSite ( self ):
    """ Test ConfigureSite command
    """
    self.pp.configureScript = 'echo'
    ConfigureSite( self.pp )

  def test_NagiosProbes ( self ):
    """ Test NagiosProbes command
    """
    nagios = NagiosProbes( self.pp )

    with open ( 'Nagios1', 'w') as fp:
      fp.write('#!/bin/sh\necho 123\n')

    os.chmod( 'Nagios1', stat.S_IRWXU )

    with open ( 'Nagios2', 'w') as fp:
      fp.write('#!/bin/sh\necho 567\n')

    os.chmod( 'Nagios2', stat.S_IRWXU )

    nagios.execute()

    self.assertEqual( nagios.nagiosProbes, ['Nagios1', 'Nagios2'] )
    self.assertEqual( nagios.nagiosPutURL, 'https://127.0.0.2/' )

  def test_UnpackDev ( self ):
    """ Test UnpackDev command
    """
    # Set up the dev.tgz file
    os.system( 'echo 123 > 123.txt ; tar zcvf dev.tgz 123.txt ; rm -f 123.txt ' )

    # Fails if tar zxvf command fails
    UnpackDev( self.pp )

#############################################################################
# Test Suite run
#############################################################################

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( PilotTestCase )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( CommandsTestCase ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )

# EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#
