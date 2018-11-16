"""Unit tests for pilotTools
"""

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import unittest
import os
import json
import Queue
from Pilot.pilotTools import ExtendedLogger


def readMessagesFromFileQueue(filename):
  queue = Queue.Queue()
  with open(filename, 'r') as myFile:
    for line in myFile:
      queue.put(line)
  return queue


def dictWithoutKey(d, keyToRemove):
  new_d = d.copy()
  new_d.pop(keyToRemove, None)
  return new_d


class TestPilotTools(unittest.TestCase):

  def setUp(self):
    self.testOutputFile = 'fakeQueueFile'

  def tearDown(self):
    for fr in [self.testOutputFile, 'PilotUUID']:
      try:
        os.remove(fr)
      except OSError:
        pass


def removeTimeStampAndPilotUUID(message):
  msg_result = dictWithoutKey(message, 'timestamp')
  return dictWithoutKey(msg_result, 'pilotUUID')


class TestPilotToolsExtendedLogger(TestPilotTools):

  def tearDown(self):
    for fr in [self.testOutputFile, 'PilotUUID']:
      try:
        os.remove(fr)
      except OSError:
        pass

  def test_sendMessageToLocalFile(self):
    msg_pattern = {
        'status': 'error',
        'phase': 'testing',
        'messageContent': 'test message',
        'pilotUUID': 'eda78924-d169-11e4-bfd2-0800275d1a0a',
        'source': 'testSource'
    }
    logger = ExtendedLogger(
        name='Pilot',
        debugFlag=True,
        pilotOutput='pilot.out',
        localMessageQueue=self.testOutputFile,
        isPilotLoggerOn=True)
    logger.sendMessage(msg="test message", source="testSource", phase="testing", status='error', sendPilotLog=True)

    queue = readMessagesFromFileQueue(self.testOutputFile)
    msg_result = json.loads(queue.get())
    msg_result = removeTimeStampAndPilotUUID(msg_result)
    expected_msg = removeTimeStampAndPilotUUID(msg_pattern)
    self.assertEquals(expected_msg, msg_result)


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotTools)
  suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestPilotToolsExtendedLogger))
  testResult = unittest.TextTestRunner(verbosity=2).run(suite)
