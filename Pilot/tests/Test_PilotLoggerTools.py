"""Unit tests for PilotLoggerTools
"""
import unittest
import json
import os
import mock
from Pilot.PilotLoggerTools import generateDict, encodeMessage
from Pilot.PilotLoggerTools import decodeMessage, isMessageFormatCorrect
from Pilot.PilotLoggerTools import getUniqueIDAndSaveToFile
from Pilot.PilotLoggerTools import createPilotLoggerConfigFile
from Pilot.PilotLoggerTools import readPilotLoggerConfigFile
from Pilot.PilotLoggerTools import getUniqueIDFromOS


class TestPilotLoggerTools( unittest.TestCase ):
  """
  Test case base class
  """
  def setUp( self ):
    """
    Test setup
    """
    self.msg = {
        'status': 'info',
        'phase': 'Installing',
        'timestamp': '1427121370.7',
        'messageContent': 'Uname = Linux localhost 3.10.64-85.cernvm.x86_64',
        'pilotUUID': 'eda78924-d169-11e4-bfd2-0800275d1a0a',
        'source': 'InstallDIRAC'
    }
    self.testFile = 'test_file_to_remove'
    self.testFileCfg = 'TestConf.cfg'
    self.badFile = '////'

  def tearDown( self ):
    """
    Test tear down
    """
    try:
      os.remove( self.testFile )
      os.remove( self.testFileCfg )
    except OSError:
      pass

class TestPilotLoggerToolsCreatePilotLoggerConfigFile( TestPilotLoggerTools ):
  """
  Test for PilotLoggerToolsCreatePilotLoggerConfigFile
  """

  def test_success( self ):
    """ Test success """
    host = '127.0.0.1'
    port = 61614
    queuePath = '/queue/test_queue'
    key_file  = 'certificates/client/key.pem'
    cert_file = 'certificates/client/cert.pem'
    ca_certs = 'certificates/testca/cacert.pem'
    fileWithID = 'PilotAgentUUID_test'

    createPilotLoggerConfigFile( self.testFileCfg,
                                 host,
                                 port,
                                 queuePath,
                                 key_file,
                                 cert_file,
                                 ca_certs,
                                 fileWithID)
    with open(self.testFileCfg, 'r') as myFile:
      config = myFile.read()
    config = json.loads(config)
    self.assertEqual(int(config['port']), port)
    self.assertEqual(config['host'], host)
    self.assertEqual(config['queuePath'], queuePath)
    self.assertEqual(config['key_file'], key_file)
    self.assertEqual(config['cert_file'], cert_file)
    self.assertEqual(config['ca_certs'], ca_certs)
    self.assertEqual(config['fileWithID'], fileWithID)

  def test_failure( self ):
    """ Test Failure """
    pass

class TestPilotLoggerToolsReadPilotLoggerConfigFile ( TestPilotLoggerTools ):
  """ Test for PilotLoggerToolsReadPilotLoggerConfigFile """
  def test_success( self ):
    """ Test success """
    host = '127.0.0.1'
    port = 61614
    queuePath = '/queue/test_queue'
    key_file  = ' certificates/client/key.pem'
    cert_file = 'certificates/client/cert.pem'
    ca_certs = 'certificates/testca/cacert.pem'
    fileWithID = 'PilotAgentUUID_test'

    createPilotLoggerConfigFile( self.testFileCfg,
                                 host,
                                 port,
                                 queuePath,
                                 key_file,
                                 cert_file,
                                 ca_certs,
                                 fileWithID)
    config = readPilotLoggerConfigFile(self.testFileCfg)
    self.assertEqual(int(config['port']), port)
    self.assertEqual(config['host'], host)
    self.assertEqual(config['queuePath'], queuePath)
    self.assertEqual(config['key_file'], key_file)
    self.assertEqual(config['cert_file'], cert_file)
    self.assertEqual(config['ca_certs'], ca_certs)
    self.assertEqual(config['fileWithID'], fileWithID)

  def test_failure( self ):
    """ Test failure """
    pass

class TestPilotLoggerToolsGenerateDict( TestPilotLoggerTools ):
  """ Test for PilotLoggerToolsGenerateDict"""

  def test_success( self ):
    """ Test success """
    result = generateDict(
        pilotUUID = 'eda78924-d169-11e4-bfd2-0800275d1a0a',
        timestamp = '1427121370.7',
        source = 'InstallDIRAC',
        phase = 'Installing',
        status = 'info',
        messageContent = 'Uname = Linux localhost 3.10.64-85.cernvm.x86_64'
        )

    self.assertEqual( result, self.msg )

  def test_failure( self ):
    """ Test failure """
    result = generateDict(
        'eda78924-d169-11e4-bfd2-0800275d1a0a',
        '1427121370.7',
        'InstallDIRAC',
        'AAA Installation',
        'info',
        'Uname = Linux localhost 3.10.64-85.cernvm.x86_64',
        )
    self.assertNotEqual( result, self.msg )


class TestPilotLoggerToolsEncodeMessage( TestPilotLoggerTools ):
  """ Test for PilotLoggerToolsEncodeMessage"""

  def test_success( self ):
    """ Test success """
    result = encodeMessage( self.msg )
    standJSON = json.dumps( self.msg )

    self.assertEqual( result, standJSON )

  def test_failure( self ):
    """ Test failure """
    pass

class TestPilotLoggerToolsDecodeMessage( TestPilotLoggerTools ):
  """ Test for PilotLoggerToolsDecodeMessage"""

  def test_success( self ):
    """ Test success """
    standJSON = json.dumps( self.msg )
    result = decodeMessage( standJSON )
    self.assertEqual( result, self.msg )

  def test_cosistency( self ):
    """ Test consistency """
    result = decodeMessage( encodeMessage( self.msg ) )
    self.assertEqual( result, self.msg )

  def test_fail( self ):
    """ Test failure """
    self.assertRaises( TypeError, decodeMessage, self.msg )


class TestPilotLoggerIsMessageFormatCorrect( TestPilotLoggerTools ):
  """ Test for PilotLoggerIsMessageFormatCorrect """

  def test_success( self ):
    """ Test success """
    self.assertTrue( isMessageFormatCorrect( self.msg ) )

  def test_notDict( self ):
    """ Test wrong format """
    self.assertFalse( isMessageFormatCorrect( ['a', 2] ) )

  def test_missingKey( self ):
    """ Test missing key"""
    badDict = self.msg.copy()
    badDict.pop( 'source', None )  # removing one key
    self.assertFalse( isMessageFormatCorrect( badDict ) )

  def test_valuesNotStrings ( self ):
    """ Test wrong values types """
    badDict = self.msg.copy()
    badDict['source'] = 10
    self.assertFalse( isMessageFormatCorrect( badDict ) )

  def test_someValuesAreEmpty( self ):
    """ Test empty values """
    badDict = self.msg.copy()
    badDict['timestamp'] = ''
    self.assertFalse( isMessageFormatCorrect( badDict ) )


class TestPilotLoggerGetUniqueIDAndSaveToFile( TestPilotLoggerTools ):
  """ Test for PilotLoggerGetUniqueIDAndSaveToFile"""

  def test_success( self ):
    """ Test success """
    self.assertTrue( getUniqueIDAndSaveToFile( self.testFile ) )

  def test_fail( self ):
    """ Test failure """
    self.assertFalse( getUniqueIDAndSaveToFile( self.badFile ) )


def helper_get(var):
  """ Hepler Getter """
  if var =='VM_UUID':
    return 'VM_uuid'
  if var == 'CE_NAME':
    return 'myCE'
  if var == 'VMTYPE':
    return 'myVMTYPE'
  return ''

  #environVars = ['CREAM_JOBID', 'GRID_GLOBAL_JOBID', 'VM_UUID']
class TestPilotLoggerGetUniqueIDFromOS( TestPilotLoggerTools ):
  """ Test for PilotLoggerGetUniqueIDFromOS"""

  @mock.patch('Pilot.PilotLoggerTools.os.environ.__contains__',
              side_effect = lambda var: var =='CREAM_JOBID')
  @mock.patch('Pilot.PilotLoggerTools.os.environ.get',
              side_effect = lambda var: 'CREAM_uuid' if var =='CREAM_JOBID' else '')

  def test_successCREAM( self, mock_environ_get, mock_environ_key): # pylint: disable=W0613
    """ Test success Cream """
    self.assertEqual(getUniqueIDFromOS(), 'CREAM_uuid')

  @mock.patch('Pilot.PilotLoggerTools.os.environ.__contains__',
              side_effect = lambda var: var =='GRID_GLOBAL_JOBID')
  @mock.patch('Pilot.PilotLoggerTools.os.environ.get',
              side_effect = lambda var: 'GRID_uuid' if var =='GRID_GLOBAL_JOBID' else '')

  def test_successGRID( self, mock_environ_get, mock_environ_key): # pylint: disable=W0613
    """ Test success grid """
    self.assertEqual(getUniqueIDFromOS(), 'GRID_uuid')


  @mock.patch('Pilot.PilotLoggerTools.os.environ.__contains__',
              side_effect = lambda var: var =='VM_UUID' or var == 'CE_NAME' or var == 'VMTYPE' )
  @mock.patch('Pilot.PilotLoggerTools.os.environ.get',
              side_effect = helper_get)

  def test_successVM( self, mock_environ_get, mock_environ_key): # pylint: disable=W0613
    """ Test success wm """
    self.assertEqual(getUniqueIDFromOS(), 'vm://myCE/myCE:myVMTYPE:VM_uuid')

  @mock.patch('Pilot.PilotLoggerTools.os.environ.__contains__',
              side_effect = lambda var: False)
  @mock.patch('Pilot.PilotLoggerTools.os.environ.get',
              side_effect = lambda var: None)

  def test_failVM( self, mock_environ_get, mock_environ_key): # pylint: disable=W0613
    """ Test Fail VM """
    self.assertFalse(getUniqueIDFromOS())

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerTools )

  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerToolsReadPilotLoggerConfigFile ))
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerToolsCreatePilotLoggerConfigFile ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerToolsGenerateDict ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerToolsEncodeMessage ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerToolsDecodeMessage ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerIsMessageFormatCorrect ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerGetUniqueIDAndSaveToFile ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerGetUniqueIDFromOS ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )
