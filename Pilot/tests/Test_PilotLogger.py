""" Unit tests for PilotLogger
"""

import unittest
import os
from Pilot.PilotLogger import PilotLogger, getPilotUUIDFromFile
from Pilot.PilotLoggerTools import getUniqueIDAndSaveToFile

class TestPilotLogger( unittest.TestCase ):
  """
  Test case base class
  """
  def setUp( self ):
    self.testFile = 'UUID_to_store'
    self.testCfgFile = 'TestPilotLogger.cfg'
    getUniqueIDAndSaveToFile( self.testFile )
    self.logger = PilotLogger(self.testCfgFile)
    self.badFile = '////'
    self.nonExistentFile = 'abrakadabraToCzaryIMagia'
  def tearDown( self ):
    try:
      os.remove( self.testFile )
    except OSError:
      pass


class TestGetPilotUUIDFromFile( TestPilotLogger ):
  """
  PILOT UUIDF from file test class
  """

  def test_success( self ):
    """
    Test success
    """
    uuid = getPilotUUIDFromFile( self.testFile )
    self.assertTrue( uuid )

  def test_failureBadFile( self ):
    """
    Test failure with bad file
    """
    uuid = getPilotUUIDFromFile( self.badFile )
    self.assertFalse( uuid )

  def test_failureNonExistent( self ):
    """
    Test failure with missing file
    """
    uuid = getPilotUUIDFromFile( self.nonExistentFile )
    self.assertFalse( uuid )

class TestPilotLoggerisCorrectStatus( TestPilotLogger ):
  """
  Test correct status class
  """
  def test_success( self ):
    """
    Test success
    """
    for status in self.logger.STATUSES:
      self.assertTrue( self.logger.isCorrectStatus( status ) )

  def test_failure( self ):
    """ Test failure """
    self.assertFalse( self.logger.isCorrectStatus( 'mamma Mia' ) )

  def test_failureEmpty( self ):
    """ Test failure with emptiness """
    self.assertFalse( self.logger.isCorrectStatus( '' ) )

class TestPilotLoggerConnect( TestPilotLogger ):
  """ Test for loggger connection """
  pass

class TestPilotLoggerSendMessage( TestPilotLogger ):
  """
  Test for logger send message
  """

  # here some mocks needed
  def test_success( self ):
    """
    Test success
    """
    pass

  def test_failure( self ):
    """ Test failure """
    pass

class TestPilotLoggersendMessage( TestPilotLogger ):
  """
  Test for logger send message
  """

  # here some mocks needed
  def test_success( self ):
    """
    Test success
    """
    pass

  def test_NotCorrectFlag( self ):
    """ Test incorrect flag """
    self.assertFalse( self.logger.sendMessage( '', 'badFlag' ) )

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLogger )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestGetPilotUUIDFromFile ) )
  # suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerisCorrectFlag ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerisCorrectStatus ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggerSendMessage ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotLoggersendMessage ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )
