""" Unit tests for PilotLogger
"""

from __future__ import absolute_import, division, print_function

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import sys
import unittest
import os
from Pilot.PilotLogger import PilotLogger, getPilotUUIDFromFile, addMissingConfiguration
from Pilot.PilotLoggerTools import getUniqueIDAndSaveToFile


class TestGetPilotUUIDFromFile(unittest.TestCase):

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


class TestPilotLogger_isCorrectStatus(unittest.TestCase):

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


class TestPilotLogger_init(unittest.TestCase):

  def setUp(self):
    self.uuidFile = 'PilotUUID'

  def tearDown(self):
    try:
      os.remove(self.uuidFile)
    except OSError:
      pass

  def test_DefaultCtrNonJsonFile(self):
    logger = PilotLogger()
    self.assertEqual(logger.params['LoggingType'], 'LOCAL_FILE')
    self.assertEqual(logger.params['LocalOutputFile'], 'myLocalQueueOfMessages')
    self.assertEqual(logger.params['FileWithID'], 'PilotUUID')


class TestPilotLogger_addMissingConfiguration(unittest.TestCase):

  def setUp(self):
    self.uuidFile = 'PilotUUID'

  def tearDown(self):
    try:
      os.remove(self.uuidFile)
    except OSError:
      pass

  def test_success(self):
    config = {'LoggingType': 'MQ',
              'LocalOutputFile': 'blabla', 'FileWithID': 'myUUUID'}
    res = addMissingConfiguration(config)
    self.assertEqual(res, config)

  def test_emptyConfig(self):
    self.assertEqual(addMissingConfiguration(None),
                     {'LoggingType': 'LOCAL_FILE',
                      'LocalOutputFile': 'myLocalQueueOfMessages',
                      'FileWithID': 'PilotUUID'})


class TestPilotLogger_sendMessage(unittest.TestCase):
  pass
  # here some mocks needed


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestGetPilotUUIDFromFile)
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger_isCorrectStatus))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger_init))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger_addMissingConfiguration))
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotLogger_sendMessage))
  testResult = unittest.TextTestRunner(verbosity=2).run(suite)
  sys.exit(not testResult.wasSuccessful())
