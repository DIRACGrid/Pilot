"""Unit tests for PilotLoggerTools
"""
import unittest
import mock
import json
import os
from DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools import generateDict, encodeMessage
from DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools import decodeMessage, isMessageFormatCorrect
from DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools import getUniqueIDAndSaveToFile
from DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools import createPilotLoggerConfigFile
from DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools import readPilotLoggerConfigFile
from DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools import getUniqueIDFromOS


class TestPilotLoggerTools( unittest.TestCase ):

  def setUp( self ):
    self.msg = {
      'status': 'Installing',
      'timestamp': '1427121370.7',
      'minorStatus': 'Uname = Linux localhost 3.10.64-85.cernvm.x86_64',
      'pilotUUID': 'eda78924-d169-11e4-bfd2-0800275d1a0a',
      'source': 'pilot'
       }
    self.testFile = 'test_file_to_remove'
    self.testFileCfg = 'TestConf.cfg'
    self.badFile = '////'
  def tearDown( self ):
    try:
      os.remove( self.testFile )
      os.remove( self.testFileCfg )
    except OSError:
      pass

class TestPilotLoggerToolsCreatePilotLoggerConfigFile( TestPilotLoggerTools ):
  def test_success( self ):
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
    pass

class TestPilotLoggerToolsReadPilotLoggerConfigFile ( TestPilotLoggerTools ):
  def test_success( self ):
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
    pass

class TestPilotLoggerToolsGenerateDict( TestPilotLoggerTools ):

  def test_success( self ):
    result = generateDict(
        'eda78924-d169-11e4-bfd2-0800275d1a0a',
        'Installing',
        'Uname = Linux localhost 3.10.64-85.cernvm.x86_64',
        '1427121370.7',
        'pilot'
        )
    self.assertEqual( result, self.msg )
  def test_failure( self ):
    result = generateDict(
        'eda78924-d169-11e4-bfd2-0800275d1a0a',
        'AAA Installation',
        'Uname = Linux localhost 3.10.64-85.cernvm.x86_64',
        '1427121370.7',
        'pilot'
        )
    self.assertNotEqual( result, self.msg )


class TestPilotLoggerToolsEncodeMessage( TestPilotLoggerTools ):

  def test_success( self ):
    result = encodeMessage( self.msg )
    standJSON = json.dumps( self.msg )

    self.assertEqual( result, standJSON )
  def test_failure( self ):
    pass

class TestPilotLoggerToolsDecodeMessage( TestPilotLoggerTools ):

  def test_success( self ):
    standJSON = json.dumps( self.msg )
    result = decodeMessage( standJSON )
    self.assertEqual( result, self.msg )

  def test_cosistency( self ):
    result = decodeMessage( encodeMessage( self.msg ) )
    self.assertEqual( result, self.msg )

  def test_fail( self ):
    self.assertRaises( TypeError, decodeMessage, self.msg )


class TestPilotLoggerIsMessageFormatCorrect( TestPilotLoggerTools ):

  def test_success( self ):
    self.assertTrue( isMessageFormatCorrect( self.msg ) )

  def test_notDict( self ):
    self.assertFalse( isMessageFormatCorrect( ['a', 2] ) )

  def test_missingKey( self ):
    badDict = self.msg.copy()
    badDict.pop( 'source', None )  # removing one key
    self.assertFalse( isMessageFormatCorrect( badDict ) )

  def test_valuesNotStrings ( self ):
    badDict = self.msg.copy()
    badDict['source'] = 10
    self.assertFalse( isMessageFormatCorrect( badDict ) )

  def test_someValuesAreEmpty( self ):
    badDict = self.msg.copy()
    badDict['timestamp'] = ''
    self.assertFalse( isMessageFormatCorrect( badDict ) )


class TestPilotLoggerGetUniqueIDAndSaveToFile( TestPilotLoggerTools ):
  def test_success( self ):
    self.assertTrue( getUniqueIDAndSaveToFile( self.testFile ) )

  def test_fail( self ):
    self.assertFalse( getUniqueIDAndSaveToFile( self.badFile ) )


def helper_get(var):
  if var =='VM_UUID':
    return 'VM_uuid'
  if var == 'CE_NAME':
    return 'myCE'
  if var == 'VMTYPE':
    return 'myVMTYPE'
  return ''

  #environVars = ['CREAM_JOBID', 'GRID_GLOBAL_JOBID', 'VM_UUID']
class TestPilotLoggerGetUniqueIDFromOS( TestPilotLoggerTools ):

  @mock.patch('DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools.os.environ.__contains__',
              side_effect = lambda var: var =='CREAM_JOBID')
  @mock.patch('DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools.os.environ.get',
              side_effect = lambda var: 'CREAM_uuid' if var =='CREAM_JOBID' else '')
  def test_successCREAM( self, mock_environ_get, mock_environ_key):
    self.assertEqual(getUniqueIDFromOS(), 'CREAM_uuid')

  @mock.patch('DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools.os.environ.__contains__',
              side_effect = lambda var: var =='GRID_GLOBAL_JOBID')
  @mock.patch('DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools.os.environ.get',
              side_effect = lambda var: 'GRID_uuid' if var =='GRID_GLOBAL_JOBID' else '')
  def test_successGRID( self, mock_environ_get, mock_environ_key):
    self.assertEqual(getUniqueIDFromOS(), 'GRID_uuid')


  @mock.patch('DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools.os.environ.__contains__',
              side_effect = lambda var: var =='VM_UUID' or var == 'CE_NAME' or var == 'VMTYPE' )
  @mock.patch('DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools.os.environ.get',
              side_effect = helper_get)
  def test_successVM( self, mock_environ_get, mock_environ_key):
    self.assertEqual(getUniqueIDFromOS(), 'vm://myCE/myCE:myVMTYPE:VM_uuid')

  @mock.patch('DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools.os.environ.__contains__',
              side_effect = lambda var: False)
  @mock.patch('DIRAC.WorkloadManagementSystem.PilotAgent.PilotLogger.PilotLoggerTools.os.environ.get',
              side_effect = lambda var: None)
  def test_failVM( self, mock_environ_get, mock_environ_key):
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
