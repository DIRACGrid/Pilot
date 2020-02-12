"""Unit tests for pilotTools
"""

from __future__ import absolute_import, division, print_function

# pylint: skip-file

import os
import json

import pytest
from mock import MagicMock

############################
# python 2 -> 3 "hacks"
try:
  import Queue as queue
except ImportError:
  import queue
############################

from Pilot.pilotTools import ExtendedLogger


testOutputFile = 'fakeQueueFile'


@pytest.fixture
def rmFiles():
  yield
  for fr in ['PilotUUID', 'PilotAgentUUID', 'myLocalQueueOfMessages']:
    try:
      os.remove(fr)
    except OSError:
      pass


def readMessagesFromFileQueue(filename):
  rqueue = queue.Queue()
  with open(filename, 'r') as myFile:
    for line in myFile:
      rqueue.put(line)
  return rqueue


def dictWithoutKey(d, keyToRemove):
  new_d = d.copy()
  new_d.pop(keyToRemove, None)
  return new_d


def removeTimeStampAndPilotUUID(message):
  msg_result = dictWithoutKey(message, 'timestamp')
  return dictWithoutKey(msg_result, 'pilotUUID')


# FIXME: this fails
def fixme_test_sendMessageToLocalFile(mocker, rmFiles):
  mocker.patch("stomp.Connection", new=MagicMock())

  msg_pattern = {
      'status': 'error',
      'phase': 'testing',
      'messageContent': 'test message',
      'pilotUUID': 'eda78924-d169-11e4-bfd2-0800275d1a0a',
      'source': 'testSource'
  }

  with open(testOutputFile, 'w'):
    pass

  logger = ExtendedLogger(
      name='Pilot',
      debugFlag=True,
      pilotOutput='pilot.out',
      isPilotLoggerOn=True)

  logger.sendMessage(msg="test message", source="testSource", phase="testing", status='error', sendPilotLog=True)
  rqueue = readMessagesFromFileQueue(testOutputFile)

  msg_result = json.loads(rqueue.get(block=False))
  msg_result = removeTimeStampAndPilotUUID(msg_result)
  expected_msg = removeTimeStampAndPilotUUID(msg_pattern)
  assert expected_msg == msg_result
