"""Unit tests for PilotTools
"""

import unittest
import os
import json
import Queue
from Pilot.PilotTools  import ExtendedLogger

def readMessagesFromFileQueue( filename ):
  """ read message helper """
  queue = Queue.Queue()
  with open( filename, 'r') as myFile:
    for line in myFile:
      queue.put(line)
  return queue

def dictWithoutKey(dictonary, keyToRemove):
  """ Key remover helper """
  new_d = dictonary.copy()
  new_d.pop(keyToRemove, None)
  return new_d


class TestPilotTools( unittest.TestCase ):
  """ Base class for tests """

  def setUp( self ):
    """ Set up """
    self.testOutputFile = 'fakeQueueFile'

  def tearDown( self ):
    """ Tear down """
    try:
      os.remove( self.testOutputFile )
    except OSError:
      pass

def removeTimeStampAndPilotUUID( message ):
  """ Remove time stamp and uuid from dict """
  msg_result  = dictWithoutKey(message, 'timestamp')
  return dictWithoutKey(msg_result, 'pilotUUID')

class TestPilotToolsExtendedLogger( TestPilotTools ):
  """ Test for PilotToolsExtendedLogger"""

  def test_sendMessageToLocalFile( self ):
    """ Test for send Message to local file """
    msg_pattern = {
        'status': 'error',
        'phase': 'testing',
        'messageContent': 'test message',
        'pilotUUID': 'eda78924-d169-11e4-bfd2-0800275d1a0a',
        'source': 'testSource'
    }
    logger = ExtendedLogger(name='Pilot', debugFlag = True, pilotOutput = 'pilot.out', isPilotLoggerOn = True)
    logger.sendMessage(msg = "test message", source = "testSource", phase = "testing",status ='error',
                       localFile =self.testOutputFile, sendPilotLog = True)
    queue = readMessagesFromFileQueue(self.testOutputFile)
    msg_result = json.loads(queue.get())
    msg_result = removeTimeStampAndPilotUUID (msg_result)
    expected_msg = removeTimeStampAndPilotUUID(msg_pattern)
    self.assertEquals(expected_msg,  msg_result)

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotTools )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( TestPilotToolsExtendedLogger))
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )
