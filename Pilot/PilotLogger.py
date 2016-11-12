""" Pilot logger module for the remote loggin system
    Only functions send and connect are depended on the client library used.
    The current implementation uses stomp.
"""

import os
import Queue
import logging
import stomp
import argparse
from PilotLoggerTools import generateDict, encodeMessage
from PilotLoggerTools import generateTimeStamp
from PilotLoggerTools import isMessageFormatCorrect
from PilotLoggerTools import readPilotLoggerConfigFile
from PilotLoggerTools import getUniqueIDAndSaveToFile

__RCSID__ = "$Id$"


def connect(host_and_port, ssl_cfg):
  """ Connects to RabbitMQ and returns connection
      handler or None in case of connection down.
      Stomp-depended function.
  """
  try:
    connection = stomp.Connection(host_and_ports=host_and_port, use_ssl = True)
    connection.set_ssl(for_hosts=host_and_port,
                       key_file = ssl_cfg['key_file'],
                       cert_file = ssl_cfg['cert_file'],
                       ca_certs = ssl_cfg['ca_certs'])
    connection.start()
    connection.connect()
    return connection
  except stomp.exception.ConnectFailedException:
    logging.error( 'Connection error')
    return None
  except IOError:
    logging.error('Could not find files with ssl certificates')
    return None

def send(msg ,destination, connect_handler):
  """Sends a message and logs info.
     Stomp-depended function.
  """
  if not connect_handler:
    return False
  connect_handler.send(destination=destination,
                       body=msg)
  logging.info(" [x] Sent %r ", msg )
  return True

def disconnect(connect_handler):
  """Disconnects.
     Stomp-depended function.
  """
  connect_handler.disconnect()


def getPilotUUIDFromFile( filename = 'PilotAgentUUID' ):
  """ Retrives Pilot UUID from the file of given name.
  Returns:
    str: empty string in case of errors.
  """

  try:
    with open ( filename, 'r' ) as myFile:
      uniqueId = myFile.read()
    return uniqueId
  except IOError:
    logging.error('Could not open the file with UUID:'+ filename)
    return ""

def eraseFileContent( filename ):
  """ Erases the content of a given file.
  """

  with open(filename, 'w+') as myFile:
    myFile.truncate()

def saveMessageToFile( msg, filename = 'myLocalQueueOfMessages' ):
  """ Adds the message to a file appended as a next line.
  """

  with open(filename, 'a+') as myFile:
    myFile.write(msg+'\n')

def readMessagesFromFileAndEraseFileContent( filename = 'myLocalQueueOfMessages' ):
  """ Generates the queue FIFO and fills it
      with values from the file, assuming that one line
      corresponds to one message.
      Finallym the file content is erased.
  Returns:
    Queue:
  """

  queue = Queue.Queue()
  with open( filename, 'r') as myFile:
    for line in myFile:
      queue.put(line)
  eraseFileContent( filename )
  return queue

class PilotLogger( object ):
  """ Base pilot logger class.
  """

  STATUSES = ['info', 'warning', 'error', 'debug']

  def __init__( self, configFile = 'PilotLogger.cfg'):
    """ ctr loads the configuration parameters from the file
        or if the file does not exists, loads the default set
        of values. Next, if self.fileWithUUID is not set (this
        variable corresponds to the name of the file with Pilot
        Agent ID) the default value is used, and if the file does
        not exist, the Pilot ID is created and saved in this file.
    Args:
      configFile(str): File with the configuration parameters.
    """
    self.STATUSES = PilotLogger.STATUSES
    self.fileWithUUID = ''
    self.networkCfg= None
    self.queuePath = ''
    self.sslCfg = None
    self._loadConfigurationFromFile(configFile)

    if not self.fileWithUUID:
      self.fileWithUUID = 'PilotAgentUUID'
      logging.warning('No pilot logger id file name was specified. The default file name will be used:'+self.fileWithUUID)
      if os.path.isfile(self.fileWithUUID):
        logging.warning('The default file: '+self.fileWithUUID + ' already exists. The content will be used to get UUID.')
      else:
        res = getUniqueIDAndSaveToFile(filename = self.fileWithUUID)
        if not res:
          logging.error('Error while generating pilot logger id.')

  def _loadConfigurationFromFile( self, filename ):
    """ Add comment
    """
    config = readPilotLoggerConfigFile (filename)
    if not config:
      logging.warning('Could not open or load configuration File! Pilot Logger will use some default values!!!')
      return False
    else:
      self.fileWithUUID = config['fileWithID']
      self.networkCfg= [(config['host'], int(config['port']))]
      self.queuePath = config['queuePath']
      self.sslCfg = dict((k, config[k]) for k  in ('key_file', 'cert_file', 'ca_certs'))
      return True

  def _isCorrectStatus( self, status ):

    """ Checks if the flag corresponds to one of the predefined
        STATUSES, check constructor for current set.
    """

    return status in self.STATUSES

  def _sendAllLocalMessages(self, connect_handler, flag = 'info' ):
    """ Retrives all messages from the local storage
        and sends it.
    """
    queue = readMessagesFromFileAndEraseFileContent()
    while not queue.empty():
      msg = queue.get()
      send(msg, self.queuePath, connect_handler)


  def _sendMessage( self, msg, flag ):
    """ Method first copies the message content to the
        local storage, then it checks if the connection
        to RabbitMQ server is up,
        If it is the case it sends all messages stored
        locally.  The string flag can be used as routing_key,
        it can contain:  'info', 'warning', 'error',
        'debug'. If the connection is down, the method
        does nothing and returns False
    Returns:
      bool: False in case of any errors, True otherwise
    """

    saveMessageToFile(msg)
    connection = connect(self.networkCfg, self.sslCfg)
    if not connection:
      return False
    self._sendAllLocalMessages(connection, flag)
    disconnect(connection)
    return True

  def sendMessage( self, messageContent, source = 'unspecified', phase = 'unspecified' , status='info',  localOutputFile = None ):
    """ Sends the message after
        creating the correct format:
        including content, timestamp, status, source, phase and the uuid
        of the pilot. If the localOutputFile is set, than the message is saved
        to the local file instead of the MQ system.
    Returns:
      bool: False in case of any errors, True otherwise
    """
    if not self._isCorrectStatus( status ):
      logging.error('status: ' + str(status) + ' is not correct')
      return False
    myUUID = getPilotUUIDFromFile(self.fileWithUUID)
    message = generateDict(
        myUUID,
        generateTimeStamp(),
        source,
        phase,
        status,
        messageContent
        )
    if not isMessageFormatCorrect( message ):
      logging.warning("Message format is not correct.")
      return False
    encodedMsg = encodeMessage( message )
    if localOutputFile:
      return saveMessageToFile(msg = encodedMsg, filename = localOutputFile)
    else:
      return self._sendMessage( encodedMsg, flag = status )

def main():
  """ main() function  is used to send a message
      before any DIRAC related part is installed.
      Remember that it is assumed that the PilotUUID was
      already generated and stored into some file.
  """

  def singleWord(arg):
    if len(arg.split()) !=1:
      msg = 'argument must be single word'
      raise argparse.ArgumentTypeError(msg)
    return arg

  parser = argparse.ArgumentParser(description="command line interface to send logs to MQ system.",
                                  formatter_class=argparse.RawTextHelpFormatter,
                                  epilog=
                                    'examples:\n'
                                    +'                   python PilotLogger.py InstallDIRAC installing info My message\n'
                                    +'                   python PilotLogger.py InstallDIRAC installing debug Debug message\n'
                                    +'                   python PilotLogger.py "My message"\n'
                                    +'                   python PilotLogger.py "My message" --output myFileName\n'
                                  )
  parser.add_argument('source',
                      type = singleWord,
                      nargs='?',
                      default ='unspecified',
                      help='Source of the message e.g. "InstallDIRAC". It must be one word. '
                           +'If not specified it is set to "unspecified".')
  parser.add_argument('phase',
                      type = singleWord,
                      nargs='?',
                      default ='unspecified',
                      help='Phase of the process e.g. "fetching". It must be one word. '
                            +'If not specified it is set to "unspecified".')
  parser.add_argument('status',
                      nargs = '?',
                      choices = PilotLogger.STATUSES,
                      default = 'info',
                      help = 'Allowed values are: '+ ', '.join(PilotLogger.STATUSES)
                      +'. If not specified it is set to "info".',
                      metavar='status ')
  parser.add_argument('message',
                      nargs='+',
                      help='Human readable content of the message. ')
  parser.add_argument('--output',
                      help = 'Log the content to the specified file'
                             +' instead of sending it to the Message Queue server.')
  args = parser.parse_args()

  if len(" ".join(args.message)) >= 200:
    raise argparse.ArgumentTypeError('message must be less than 200 characters')
  logger = PilotLogger()
  if args.output:
    print args.output
    logger.sendMessage( messageContent = " ".join(args.message),
                        source = args.source,
                        phase = args.phase,
                        status = args.status,
                        localOutputFile = args.output)
  else:
    logger.sendMessage( messageContent = " ".join(args.message),
                        source = args.source,
                        phase = args.phase,
                        status = args.status)

if __name__ == '__main__':
  main()
