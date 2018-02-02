""" Unit tests for MessageSender
"""

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import unittest
import os
from mock import MagicMock
from Pilot.MessageSender import LocalFileSender, StompSender, RESTSender
import Pilot.MessageSender as module


class TestMessageSender(unittest.TestCase):

  def setUp(self):
    self.testFile = 'myLocalQueueOfMessages'
    self.testMessage = 'my test message'
    self.networkCfg = ('host', 123)
    self.sslCfg = {'key_file': 'a', 'cert_file': 'b', 'ca_certs': 'c'}

    try:
      os.remove(self.testFile)
    except OSError:
      pass

    module.stomp = MagicMock()
    module.stomp.Connection = MagicMock()
    connectionMock = MagicMock()
    connectionMock.is_connected.return_value = True
    module.stomp.Connection.return_value = connectionMock

  def tearDown(self):
    try:
      os.remove(self.testFile)
    except OSError:
      pass


class TestLocalFileSender(TestMessageSender):
  def test_success(self):
    msgSender = LocalFileSender()
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)
    lineFromFile = ''
    with open(self.testFile, 'r') as myFile:
      lineFromFile = next(myFile)
    self.assertEqual(self.testMessage+'\n', lineFromFile)


class TestStompSender(TestMessageSender):

  def test_success(self):
    msgSender = StompSender(self.networkCfg, self.sslCfg)
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)

  def test_failure_no_connectionParams(self):
    msgSender = StompSender(self.networkCfg, None)
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertFalse(res)


class TestRESTSender(TestMessageSender):

  def test_success(self):
    msgSender = RESTSender()
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMessageSender)
  suite.addTest(
    unittest.defaultTestLoader.loadTestsFromTestCase(TestLocalFileSender))
  suite.addTest(
    unittest.defaultTestLoader.loadTestsFromTestCase(TestStompSender))
  suite.addTest(
    unittest.defaultTestLoader.loadTestsFromTestCase(TestRESTSender))
  testResult = unittest.TextTestRunner(verbosity=2).run(suite)
