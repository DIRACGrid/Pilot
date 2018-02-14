""" Unit tests for PilotLogger
"""

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import unittest
import os
from Pilot.PilotLogger import PilotLogger, getPilotUUIDFromFile
from Pilot.PilotLoggerTools import getUniqueIDAndSaveToFile

class TestPilotLogger(unittest.TestCase):
  pass


class TestGetPilotUUIDFromFile(TestPilotLogger):

  def setUp(self):
    self.testFile = 'UUID_to_store'
    getUniqueIDAndSaveToFile(self.testFile)
    self.badFile = '////'
    self.nonExistentFile = 'abrakadabraToCzaryIMagia'

  def tearDown(self):
    try:
      os.remove(self.testFile)
    except OSError:
      pass

  def test_success(self):
    uuid = getPilotUUIDFromFile(self.testFile)
    self.assertTrue(uuid)

  def test_failureBadFile(self):
    uuid = getPilotUUIDFromFile(self.badFile)
    self.assertFalse(uuid)

  def test_failureNonExistent(self):
    uuid = getPilotUUIDFromFile(self.nonExistentFile)
    self.assertFalse(uuid)

class TestPilotLogger_isCorrectStatus(TestPilotLogger):

  def setUp(self):
    self.uuidFile = 'PilotUUID'
    self.logger = PilotLogger()

  def tearDown(self):
    try:
      os.remove(self.uuidFile)
    except OSError:
      pass

  def test_success(self):
    for status in self.logger.STATUSES:
      self.assertTrue(self.logger._isCorrectStatus(status))

  def test_failure(self):
    self.assertFalse(self.logger._isCorrectStatus('mamma Mia'))

  def test_failureEmpty(self):
    self.assertFalse(self.logger._isCorrectStatus(''))


class TestPilotLogger_init(TestPilotLogger):

  def setUp(self):
    self.uuidFile = 'PilotUUID'

  def tearDown(self):
    try:
      os.remove(self.uuidFile)
    except OSError:
      pass

  def test_DefaultCtrNonJsonFile(self):
    logger = PilotLogger()
    self.assertEqual(logger.messageSenderType, 'LOCAL_FILE')
    self.assertEqual(logger.localOutputFile, 'myLocalQueueOfMessages')
    self.assertEqual(logger.fileWithUUID, 'PilotUUID')

class TestPilotLogger_loadConfiguration(TestPilotLogger):

  def setUp(self):
    self.uuidFile = 'PilotUUID'
    self.logger = PilotLogger()

  def tearDown(self):
    try:
      os.remove(self.uuidFile)
    except OSError:
      pass

  def test_success(self):
    config = {'LoggingType': 'MQ',
              'LocalOutputFile': 'blabla', 'FileWithID': 'myUUUID'}
    self.logger._loadConfiguration(config)
    self.assertEqual(self.logger.messageSenderType, 'MQ')
    self.assertEqual(self.logger.localOutputFile, 'blabla')
    self.assertEqual(self.logger.fileWithUUID, 'myUUUID')

  def test_emptyConfig(self):
    self.assertFalse(self.logger._loadConfiguration(None))


class TestPilotLogger_sendMessage(TestPilotLogger):
  pass
  # here some mocks needed


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger)
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestGetPilotUUIDFromFile))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger_isCorrectStatus))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger_init))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger_loadConfiguration))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger_sendMessage))
  testResult = unittest.TextTestRunner(verbosity=2).run(suite)
