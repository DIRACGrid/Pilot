"""Unit tests for PilotLoggerTools
"""

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import json
import os
import unittest
import mock
from Pilot.PilotLoggerTools import generateDict, encodeMessage
from Pilot.PilotLoggerTools import decodeMessage, isMessageFormatCorrect
from Pilot.PilotLoggerTools import getUniqueIDAndSaveToFile
from Pilot.PilotLoggerTools import createPilotLoggerConfigFile
from Pilot.PilotLoggerTools import getUniqueIDFromOS
from Pilot.PilotLoggerTools import readPilotJSONConfigFile


class TestPilotLoggerTools(unittest.TestCase):

  def setUp(self):
    self.msg = {
        'status': 'info',
        'phase': 'Installing',
        'timestamp': '1427121370.7',
        'messageContent': 'Uname = Linux localhost 3.10.64-85.cernvm.x86_64',
        'pilotUUID': 'eda78924-d169-11e4-bfd2-0800275d1a0a',
        'source': 'InstallDIRAC'
    }
    self.testFile = 'test_file_to_remove'
    self.testFileCfg = 'TestConf.json'
    self.badFile = '////'

  def tearDown(self):
    # for fileProd in [self.testFile, self.testFileCfg, 'PilotUUID']:
    for fileProd in [self.testFile, 'PilotUUID']:
      try:
        os.remove(fileProd)
      except OSError:
        pass


class TestPilotLoggerToolsreadPilotJSONConfigFile  (TestPilotLoggerTools):
  def setUp(self):
    jsonContent_MQ = """
			{
				"Setups": {
					"Dirac-Certification": {
						"Logging": {
							"Queue": {
								"test": {
								"Persistent": "False",
								"Acknowledgement": "False"
								}
							},
              "LoggingType":"MQ",
              "LocalOutputFile":"myLocalQueueOfMessages",
							"Host": "testMachineMQ.cern.ch",
							"Port": "61614",
							"HostKey": "/path/to/certs/hostkey.pem",
							"HostCertificate": "/path/to/certs/hostcert.pem",
							"CACertificate": "/path/to/certs/ca-bundle.crt"
						}
					}
				},
				"DefaultSetup": "Dirac-Certification"
			}
			"""
    self.pilotJSON_MQ = 'pilotMQ.json'
    with open(self.pilotJSON_MQ, 'w') as myF:
      myF.write(jsonContent_MQ)

    jsonContent_REST = """
			{
				"Setups": {
					"Dirac-Certification": {
						"Logging": {
              "LoggingType":"REST_API",
              "LocalOutputFile":"myLocalQueueOfMessages",
              "Url": "https://testMachineREST.cern.ch:666/msg",
							"HostKey": "/path/to/certs/hostkey.pem",
							"HostCertificate": "/path/to/certs/hostcert.pem",
							"CACertificate": "/path/to/certs/ca-bundle.crt"
						}
					}
				},
				"DefaultSetup": "Dirac-Certification"
			}
			"""
    self.pilotJSON_REST = 'pilotREST.json'
    with open(self.pilotJSON_REST, 'w') as myF:
      myF.write(jsonContent_REST)

    jsonContent_LOCAL = """
			{
				"Setups": {
					"Dirac-Certification": {
						"Logging": {
              "LoggingType":"LOCAL_FILE",
              "LocalOutputFile":"myLocalQueueOfMessages"
						}
					}
				},
				"DefaultSetup": "Dirac-Certification"
			}
			"""
    self.pilotJSON_LOCAL = 'pilotLOCAL.json'
    with open(self.pilotJSON_LOCAL, 'w') as myF:
      myF.write(jsonContent_LOCAL)

  def tearDown(self):
    for fileProd in [self.pilotJSON_MQ, self.pilotJSON_REST, self.pilotJSON_LOCAL]:
      try:
        os.remove(fileProd)
      except OSError:
        pass

  def test_success_MQ(self):
    config = readPilotJSONConfigFile(self.pilotJSON_MQ)
    host = 'testMachineMQ.cern.ch'
    port = 61614
    queuePath = '/queue/test'
    key_file = '/path/to/certs/hostkey.pem'
    cert_file = '/path/to/certs/hostcert.pem'
    ca_certs = '/path/to/certs/ca-bundle.crt'
    config = readPilotJSONConfigFile(self.pilotJSON_MQ)

    self.assertEqual(config['LoggingType'], 'MQ')
    self.assertEqual(config['LocalOutputFile'], 'myLocalQueueOfMessages')
    self.assertEqual(int(config['Port']), port)
    self.assertEqual(config['Host'], host)
    self.assertEqual(config['QueuePath'], queuePath)
    self.assertEqual(config['HostKey'], key_file)
    self.assertEqual(config['HostCertificate'], cert_file)
    self.assertEqual(config['CACertificate'], ca_certs)
    self.assertEqual(config['FileWithID'], 'PilotUUID')

    #self.assertEqual(config['fileWithID'], fileWithID)

  def test_success_REST(self):
    config = readPilotJSONConfigFile(self.pilotJSON_REST)
    url = 'https://testMachineREST.cern.ch:666/msg'
    key_file = '/path/to/certs/hostkey.pem'
    cert_file = '/path/to/certs/hostcert.pem'
    ca_certs = '/path/to/certs/ca-bundle.crt'
    config = readPilotJSONConfigFile(self.pilotJSON_REST)
    self.assertEqual(config['LoggingType'], 'REST_API')
    self.assertEqual(config['LocalOutputFile'], 'myLocalQueueOfMessages')
    self.assertEqual(config['Url'], url)
    self.assertEqual(config['HostKey'], key_file)
    self.assertEqual(config['HostCertificate'], cert_file)
    self.assertEqual(config['CACertificate'], ca_certs)
    self.assertEqual(config['FileWithID'], 'PilotUUID')

    self.assertFalse(config['QueuePath'])

    #self.assertEqual(config['fileWithID'], fileWithID)

  def test_success_LOCAL(self):
    config = readPilotJSONConfigFile(self.pilotJSON_LOCAL)
    self.assertEqual(config['LoggingType'], 'LOCAL_FILE')
    self.assertEqual(config['LocalOutputFile'], 'myLocalQueueOfMessages')
    self.assertEqual(config['FileWithID'], 'PilotUUID')

    self.assertFalse(config['QueuePath'])
    self.assertFalse(config['Port'])
    self.assertFalse(config['Host'])
    self.assertFalse(config['HostKey'])
    self.assertFalse(config['HostCertificate'])
    self.assertFalse(config['CACertificate'])

  def test_failure(self):
    pass


class TestPilotLoggerToolsCreatePilotLoggerConfigFile(TestPilotLoggerTools):

  def test_success(self):
    loggingType = 'MQ'
    host = '127.0.0.1'
    port = '61614'
    url = ''
    key_file = 'certificates/client/key.pem'
    cert_file = 'certificates/client/cert.pem'
    ca_certs = 'certificates/testca/cacert.pem'
    fileWithID = 'PilotUUID_test'
    queue = {'test.cern.ch': {}}

    createPilotLoggerConfigFile(filename=self.testFileCfg,
                                loggingType=loggingType,
                                host=host,
                                port=port,
                                url=url,
                                key_file=key_file,
                                cert_file=cert_file,
                                ca_certs=ca_certs,
                                fileWithID=fileWithID,
                                queue=queue)
    with open(self.testFileCfg, 'r') as myFile:
      config = myFile.read()
    config = json.loads(config)
    partial = config['Setups']['Dirac-Certification']['Logging']
    self.assertEqual(partial['LoggingType'], 'MQ')
    self.assertEqual(partial['Port'], port)
    self.assertEqual(partial['Host'], host)
    self.assertEqual(partial['Url'], url)
    self.assertEqual(partial['HostKey'], key_file)
    self.assertEqual(partial['HostCertificate'], cert_file)
    self.assertEqual(partial['CACertificate'], ca_certs)
    self.assertEqual(partial['FileWithID'], fileWithID)
    self.assertEqual(partial['Queue'], queue)

  def test_failure(self):
    pass


class TestPilotLoggerToolsGenerateDict(TestPilotLoggerTools):

  def test_success(self):
    result = generateDict(
        pilotUUID='eda78924-d169-11e4-bfd2-0800275d1a0a',
        timestamp='1427121370.7',
        source='InstallDIRAC',
        phase='Installing',
        status='info',
        messageContent='Uname = Linux localhost 3.10.64-85.cernvm.x86_64'
    )

    self.assertEqual(result, self.msg)

  def test_failure(self):
    result = generateDict(
        'eda78924-d169-11e4-bfd2-0800275d1a0a',
        '1427121370.7',
        'InstallDIRAC',
        'AAA Installation',
        'info',
        'Uname = Linux localhost 3.10.64-85.cernvm.x86_64',
    )
    self.assertNotEqual(result, self.msg)


class TestPilotLoggerToolsEncodeMessage(TestPilotLoggerTools):

  def test_success(self):
    result = encodeMessage(self.msg)
    standJSON = json.dumps(self.msg)

    self.assertEqual(result, standJSON)

  def test_failure(self):
    pass


class TestPilotLoggerToolsDecodeMessage(TestPilotLoggerTools):

  def test_success(self):
    standJSON = json.dumps(self.msg)
    result = decodeMessage(standJSON)
    self.assertEqual(result, self.msg)

  def test_cosistency(self):
    result = decodeMessage(encodeMessage(self.msg))
    self.assertEqual(result, self.msg)

  def test_fail(self):
    self.assertRaises(TypeError, decodeMessage, self.msg)


class TestPilotLoggerIsMessageFormatCorrect(TestPilotLoggerTools):

  def test_success(self):
    self.assertTrue(isMessageFormatCorrect(self.msg))

  def test_notDict(self):
    self.assertFalse(isMessageFormatCorrect(['a', 2]))

  def test_missingKey(self):
    badDict = self.msg.copy()
    badDict.pop('source', None)  # removing one key
    self.assertFalse(isMessageFormatCorrect(badDict))

  def test_valuesNotStrings(self):
    badDict = self.msg.copy()
    badDict['source'] = 10
    self.assertFalse(isMessageFormatCorrect(badDict))

  def test_someValuesAreEmpty(self):
    badDict = self.msg.copy()
    badDict['timestamp'] = ''
    self.assertFalse(isMessageFormatCorrect(badDict))


class TestPilotLoggerGetUniqueIDAndSaveToFile(TestPilotLoggerTools):
  def test_success(self):
    self.assertTrue(getUniqueIDAndSaveToFile(self.testFile))

  def test_fail(self):
    self.assertFalse(getUniqueIDAndSaveToFile(self.badFile))


def helper_get(var):
  if var == 'VM_UUID':
    return 'VM_uuid'
  if var == 'CE_NAME':
    return 'myCE'
  if var == 'VMTYPE':
    return 'myVMTYPE'
  return ''

  #environVars = ['CREAM_JOBID', 'GRID_GLOBAL_JOBID', 'VM_UUID']


class TestPilotLoggerGetUniqueIDFromOS(TestPilotLoggerTools):

  @mock.patch('Pilot.PilotLoggerTools.os.environ.__contains__',
              side_effect=lambda var: var == 'CREAM_JOBID')
  @mock.patch('Pilot.PilotLoggerTools.os.environ.get',
              side_effect=lambda var: 'CREAM_uuid' if var == 'CREAM_JOBID' else '')
  def test_successCREAM(self, mock_environ_get, mock_environ_key):
    self.assertEqual(getUniqueIDFromOS(), 'CREAM_uuid')

  @mock.patch('Pilot.PilotLoggerTools.os.environ.__contains__',
              side_effect=lambda var: var == 'GRID_GLOBAL_JOBID')
  @mock.patch('Pilot.PilotLoggerTools.os.environ.get',
              side_effect=lambda var: 'GRID_uuid' if var == 'GRID_GLOBAL_JOBID' else '')
  def test_successGRID(self, mock_environ_get, mock_environ_key):
    self.assertEqual(getUniqueIDFromOS(), 'GRID_uuid')

  @mock.patch('Pilot.PilotLoggerTools.os.environ.__contains__',
              side_effect=lambda var: var == 'VM_UUID' or var == 'CE_NAME' or var == 'VMTYPE')
  @mock.patch('Pilot.PilotLoggerTools.os.environ.get',
              side_effect=helper_get)
  def test_successVM(self, mock_environ_get, mock_environ_key):
    self.assertEqual(getUniqueIDFromOS(), 'vm://myCE/myCE:myVMTYPE:VM_uuid')

  @mock.patch('Pilot.PilotLoggerTools.os.environ.__contains__',
              side_effect=lambda var: False)
  @mock.patch('Pilot.PilotLoggerTools.os.environ.get',
              side_effect=lambda var: None)
  def test_failVM(self, mock_environ_get, mock_environ_key):
    self.assertFalse(getUniqueIDFromOS())


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerTools)

  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerToolsreadPilotJSONConfigFile))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerToolsCreatePilotLoggerConfigFile))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerToolsGenerateDict))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerToolsEncodeMessage))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerToolsDecodeMessage))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerIsMessageFormatCorrect))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerGetUniqueIDAndSaveToFile))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLoggerGetUniqueIDFromOS))
  testResult = unittest.TextTestRunner(verbosity=2).run(suite)
