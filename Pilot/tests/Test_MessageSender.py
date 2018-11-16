""" Unit tests for MessageSender
"""

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import unittest
import os
from mock import MagicMock, patch
from Pilot.MessageSender import LocalFileSender, StompSender, RESTSender, eraseFileContent, loadAndCreateObject


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
    res = loadAndCreateObject('MessageSender', 'LocalFileSender', {'LocalOutputFile': 'blabla'})
    self.assertTrue(res)

  def test_fail(self):
    res = loadAndCreateObject('MessageSender', 'NonExistingClass', '')
    self.assertFalse(res)

  def test_fail2(self):
    res = loadAndCreateObject('Bla.Bla', 'NonExistingClass', '')
    self.assertFalse(res)


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

  def tearDown(self):
    removeFile('myFile')

  @patch("Pilot.MessageSender.stompConnect", return_value=MagicMock())
  def test_success(self, _mockFun):
    params = {'HostKey': 'key', 'HostCertififcate': 'cert', 'CACertificate': 'caCert',
              'Host': 'localhost', 'Port': '61613', 'QueuePath': '/queue/myqueue', 'LocalOutputFile': 'myFile'}
    msgSender = StompSender(params)
    res = msgSender.sendMessage('my test message', 'info')
    self.assertTrue(res)

  def test_failure_badParams(self):
    self.assertRaises(ValueError, StompSender, {'blabl': 'bleble'})


class TestRESTSender(unittest.TestCase):

  @patch("Pilot.MessageSender.restSend", return_value=True)
  def test_success(self, _patch):
    params = {'HostKey': 'key', 'HostCertififcate': 'cert', 'CACertificate': 'caCert',
              'Url': 'https://some.host.ch/messages', 'LocalOutputFile': 'myFile'}
    msgSender = RESTSender(params)
    res = msgSender.sendMessage('my test message', 'info')
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
