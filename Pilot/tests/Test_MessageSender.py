""" Unit tests for MessageSender
"""

from __future__ import absolute_import, division, print_function

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import sys
import unittest
import os
from mock import MagicMock
from Pilot.MessageSender import LocalFileSender, StompSender, RESTSender, eraseFileContent, loadAndCreateObject
import Pilot.MessageSender as module

############################
# python 2 -> 3 "hacks"
try:
  ModuleNotFoundError
except NameError:
  ModuleNotFoundError = ImportError
############################


def removeFile(filename):
  try:
    os.remove(filename)
  except OSError:
    pass


class TestMessageSenderEraseFileContent(unittest.TestCase):
  def setUp(self):
    self.testFile = 'someStrangeFile'
    with open(self.testFile, 'a'):
      os.utime(self.testFile, None)

  def tearDown(self):
    removeFile(self.testFile)

  def test_success(self):
    try:
      eraseFileContent(self.testFile)
    except BaseException:
      self.fail("eraseFileContent() raised ExceptionType!")


class TestLoadAndCreateObject(unittest.TestCase):
  def setUp(self):
    pass

  def tearDown(self):
    pass

  def test_success(self):
    res = loadAndCreateObject('Pilot.MessageSender', 'LocalFileSender', {'LocalOutputFile': 'blabla'})
    self.assertTrue(res)

  def test_fail(self):
    self.assertRaises(ModuleNotFoundError, loadAndCreateObject, 'Bla.Bla', 'NonExistingClass', '')


class TestLocalFileSender(unittest.TestCase):
  def setUp(self):
    self.testFile = 'someLocalQueueOfMessages'
    self.testMessage = 'my test message'
    removeFile(self.testFile)

  def tearDown(self):
    removeFile(self.testFile)

  def test_success(self):
    msgSender = LocalFileSender({'LocalOutputFile': self.testFile})
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)
    lineFromFile = ''
    with open(self.testFile, 'r') as myFile:
      lineFromFile = next(myFile)
    self.assertEqual(self.testMessage + '\n', lineFromFile)

  def test_failure_badParams(self):
    self.assertRaises(ValueError, LocalFileSender, {'blabl': 'bleble'})


class TestStompSender(unittest.TestCase):

  def setUp(self):
    self.testFile = 'myFile'
    self.testMessage = 'my test message'
    module.stomp = MagicMock()
    module.stomp.Connection = MagicMock()
    connectionMock = MagicMock()
    connectionMock.is_connected.return_value = True
    module.stomp.Connection.return_value = connectionMock

  def tearDown(self):
    removeFile(self.testFile)

  def test_success(self):
    params = {'HostKey': 'key', 'HostCertificate': 'cert', 'CACertificate': 'caCert',
              'Host': 'test.host.ch', 'Port': '666', 'QueuePath': '/queue/myqueue', 'LocalOutputFile': self.testFile}
    msgSender = StompSender(params)
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)

  def test_failure_badParams(self):
    self.assertRaises(ValueError, StompSender, {'blabl': 'bleble'})


class TestRESTSender(unittest.TestCase):

  def setUp(self):
    self.testFile = 'myFile'
    self.testMessage = 'my test message'
    module.requests = MagicMock()
    module.requests.post = MagicMock()

  def test_success(self):
    params = {'HostKey': 'key', 'HostCertificate': 'cert', 'CACertificate': 'caCert',
              'Url': 'https://some.host.ch/messages', 'LocalOutputFile': self.testFile}
    msgSender = RESTSender(params)
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)

  def test_failure_badParams(self):
    self.assertRaises(ValueError, RESTSender, {'blabl': 'bleble'})


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestLocalFileSender)
  suite.addTest(
      unittest.defaultTestLoader.loadTestsFromTestCase(TestStompSender))
  suite.addTest(
      unittest.defaultTestLoader.loadTestsFromTestCase(TestRESTSender))
  suite.addTest(
      unittest.defaultTestLoader.loadTestsFromTestCase(TestMessageSenderEraseFileContent))
  testResult = unittest.TextTestRunner(verbosity=2).run(suite)
  sys.exit(not testResult.wasSuccessful())
