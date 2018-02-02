""" Unit tests for MessageSender
"""

#pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

import unittest
import os
from Pilot.MessageSender import MessageSender, LocalFileSender

class TestMessageSender( unittest.TestCase ):

  def setUp( self ):
    self.testFile = 'myLocalQueueOfMessages'
    self.testMessage= 'my test message'
    #self.testCfgFile = 'TestMessageSender.cfg'
    #getUniqueIDAndSaveToFile( self.testFile )
    #self.logger = MessageSender(self.testCfgFile)
    #self.badFile = '////'
    #self.nonExistentFile = 'abrakadabraToCzaryIMagia'
  def tearDown( self ):
    try:
      os.remove( self.testFile )
    except OSError:
      pass

class TestLocalFileSender( TestMessageSender ):
  def test_success( self ):
    msgSender = LocalFileSender()
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)
    lineFromFile =''
    with open( self.testFile, 'r') as myFile:
      lineFromFile = next(myFile)
    self.assertEqual(self.testMessage+'\n', lineFromFile)

class TestLocalFileSender( TestMessageSender ):
  def test_success( self ):
    msgSender = LocalFileSender()
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)
    lineFromFile =''
    with open( self.testFile, 'r') as myFile:
      lineFromFile = next(myFile)
    self.assertEqual(self.testMessage+'\n', lineFromFile)

#class TestLocalFileSender( MessageSender ):

  #def test_success( self ):
    #uuid = getPilotUUIDFromFile( self.testFile )
    #self.assertTrue( uuid )

  #def test_failureBadFile( self ):
    #uuid = getPilotUUIDFromFile( self.badFile )
    #self.assertFalse( uuid )

  #def test_failureNonExistent( self ):
    #uuid = getPilotUUIDFromFile( self.nonExistentFile )
    #self.assertFalse( uuid )

#class TestMessageSender_isCorrectStatus( TestMessageSender ):

  #def test_success( self ):
    #for status in self.logger.STATUSES:
      #self.assertTrue( self.logger._isCorrectStatus( status ) )

  #def test_failure( self ):
    #self.assertFalse( self.logger._isCorrectStatus( 'mamma Mia' ) )

  #def test_failureEmpty( self ):
    #self.assertFalse( self.logger._isCorrectStatus( '' ) )

#class TestMessageSender_connect( TestMessageSender ):
  #pass
#class TestMessageSender_sendMessage( TestMessageSender ):

  ## here some mocks needed
  #def test_success( self ):
    #pass
  #def test_failure( self ):
    #pass

  #def test_NotCorrectFlag( self ):
    #self.assertFalse( self.logger.sendMessage( '', 'badFlag' ) )

#class TestMessageSender_sendMessageToREST( TestMessageSender ):

  #def test_success( self ):
    #self.logger._sendMessageToREST('wowow', 'badFlag')
  #def test_failure( self ):
    #pass


if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( TestMessageSender )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestLocalFileSender) )
  #suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestGetPilotUUIDFromFile ) )

  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )
