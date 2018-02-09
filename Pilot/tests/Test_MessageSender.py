""" Unit tests for MessageSender
"""

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import unittest
import os
from mock import MagicMock
from Pilot.MessageSender import LocalFileSender, StompSender, RESTSender
import Pilot.MessageSender as module


def removeFile(filename):
  try:
    os.remove(filename)
  except OSError:
    pass


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
    self.assertEqual(self.testMessage+'\n', lineFromFile)

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
    params = {'HostKey': 'key', 'HostCertififcate': 'cert', 'CACertificate': 'caCert',
              'Host': 'test.host.ch', 'Port': '666',  'QueuePath': '/queue/myqueue', 'LocalOutputFile': self.testFile}
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
    params = {'HostKey': 'key', 'HostCertififcate': 'cert', 'CACertificate': 'caCert',
              'Destination': 'https://some.host.ch/messages', 'LocalOutputFile': self.testFile}
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
  testResult = unittest.TextTestRunner(verbosity=2).run(suite)
