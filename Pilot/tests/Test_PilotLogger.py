""" Unit tests for PilotLogger
"""

# pylint: skip-file

import os

import pytest

from Pilot.PilotLogger import PilotLogger, getPilotUUIDFromFile
from Pilot.PilotLoggerTools import getUniqueIDAndSaveToFile


testFile = 'UUID_to_store'
badFile = '////'
nonExistentFile = 'abrakadabraToCzaryIMagia'
uuidFile = 'PilotUUID'


@pytest.fixture
def rmFiles():
  yield
  for fr in [testFile, 'PilotUUID', 'PilotAgentUUID']:
    try:
      os.remove(fr)
    except OSError:
      pass


def test_success(rmFiles):
  getUniqueIDAndSaveToFile(testFile)
  uuid = getPilotUUIDFromFile(testFile)
  assert uuid


def test_failureBadFile(rmFiles):
  getUniqueIDAndSaveToFile(testFile)
  uuid = getPilotUUIDFromFile(badFile)
  assert not uuid


def test_failureNonExistent(rmFiles):
  uuid = getPilotUUIDFromFile(nonExistentFile)
  assert not uuid


def test_PilotLogger_success(rmFiles):
  logger = PilotLogger()
  for status in logger.STATUSES:
    assert logger._isCorrectStatus(status) is True


def test_failure(rmFiles):
  logger = PilotLogger()
  assert logger._isCorrectStatus('mamma Mia') is False


def test_failureEmpty(rmFiles):
  logger = PilotLogger()
  assert logger._isCorrectStatus('') is False
