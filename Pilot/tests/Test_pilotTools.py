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

from Pilot.pilotTools import ExtendedLogger, parseVersion


testOutputFile = 'fakeQueueFile'


@pytest.fixture
def rmFiles():
  yield
  for fr in ['PilotUUID', 'PilotAgentUUID', 'myLocalQueueOfMessages']:
    try:
      os.remove(fr)
    except OSError:
      pass


@pytest.mark.parametrize("releaseVersion, useLegacyStyle, expected", [
    ("invalid-version", True, "invalid-version"),
    ("invalid-version", False, "invalid-version"),
    ("v10r2-pre9", True, "v10r2-pre9"),
    ("v10r2-pre9", False, "10.2.0a9"),
    ("v10r2", True, "v10r2"),
    ("v10r2", False, "10.2.0"),
    ("v10r2p0", True, "v10r2p0"),
    ("v10r2p0", False, "10.2.0"),
    ("v10r2p1", True, "v10r2p1"),
    ("v10r2p1", False, "10.2.1"),
    ("v10r2p10", True, "v10r2p10"),
    ("v10r2p10", False, "10.2.10"),
    ("v10r2p15", True, "v10r2p15"),
    ("v10r2p15", False, "10.2.15"),
    ("v10r3", True, "v10r3"),
    ("v10r3", False, "10.3.0"),
    ("v11r0-pre1", True, "v11r0-pre1"),
    ("v11r0-pre1", False, "11.0.0a1"),
    ("v11r0-pre12", True, "v11r0-pre12"),
    ("v11r0-pre12", False, "11.0.0a12"),
    ("v11r0", True, "v11r0"),
    ("v11r0", False, "11.0.0"),
    ("v11r1", True, "v11r1"),
    ("v11r1", False, "11.1.0"),
])
def test_version_conversion(releaseVersion, useLegacyStyle, expected):
    assert parseVersion(releaseVersion, useLegacyStyle) == expected


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
