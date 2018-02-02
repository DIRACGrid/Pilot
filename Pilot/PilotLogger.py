""" Pilot logger module for the remote loggin system
    Only functions send and connect are depended on the client library used.
    The current implementation uses stomp.
"""

import os
import logging
import argparse
from PilotLoggerTools import generateDict, encodeMessage
from PilotLoggerTools import generateTimeStamp
from PilotLoggerTools import isMessageFormatCorrect
from PilotLoggerTools import readPilotJSONConfigFile
from PilotLoggerTools import readPilotLoggerConfigFile
from PilotLoggerTools import getUniqueIDAndSaveToFile
from MessageSender import createMessageSender



def getPilotUUIDFromFile(filename='PilotUUID'):
  """ Retrives Pilot UUID from the file of given name.
  Returns:
    str: empty string in case of errors.
  """

  try:
    with open(filename, 'r') as myFile:
      uniqueId = myFile.read()
    return uniqueId
  except IOError:
    logging.error('Could not open the file with UUID:' + filename)
    return ""


class PilotLogger(object):
  """ Base pilot logger class.
  """

  STATUSES = ['info', 'warning', 'error', 'debug']

  DESTINATION_TYPES = ['MQ', 'LOCAL_FILE', 'REST_API']

  def __init__(self, configFile='pilot.json', messageSenderType='LOCAL_FILE', localOutputFile='myLocalQueueOfMessages'):
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
    self.DESTINATION_TYPES = PilotLogger.DESTINATION_TYPES
    self.messageSenderType = messageSenderType
    self.messageSender = None
    self.fileWithUUID = ''
    self.networkCfg = None
    self.queuePath = ''
    self.sslCfg = None
    self.localOutputFile = localOutputFile
    self._loadConfigurationFromFile(configFile)

    if not self.fileWithUUID:
      self.fileWithUUID = 'PilotUUID'
      logging.warning(
        'No pilot logger id file name was specified. The default file name will be used:'+self.fileWithUUID)
      if os.path.isfile(self.fileWithUUID):
        logging.warning('The default file: '+self.fileWithUUID +
                        ' already exists. The content will be used to get UUID.')
      else:
        res = getUniqueIDAndSaveToFile(filename=self.fileWithUUID)
        if not res:
          logging.error('Error while generating pilot logger id.')

    if not self.localOutputFile:
      self.localOutputFile = 'myLocalQueueOfMessages'
      logging.warning(
        'No local output file name was specified. The default file name will be used:'+self.localOutputFile)

    if not self.messageSenderType:
      self.messagaSenderType = 'MQ'
      logging.warning(
        'No message sender type was specified. The default sender will be used:'+self.messageSenderType)
    self.messageSender = createMessageSender(senderType=self.messageSenderType)

  def _loadConfigurationFromFile(self, filename):
    """ Add comment
    """
    config = readPilotJSONConfigFile(filename)
    if not config:
      logging.warning(
        'Could not open or load configuration File! Pilot Logger will use some default values!!!')
      return False
    else:
      self.fileWithUUID = config['fileWithID']
      self.networkCfg = [(config['host'], int(config['port']))]
      self.queuePath = config['queuePath']
      self.sslCfg = dict((k, config[k])
                         for k in ('key_file', 'cert_file', 'ca_certs'))
      self.localOutputFile = config.get('outputFile', '')
      self.messageSenderType = config.get('messageSender', 'LOCAL_FILE')
      return True

  def _isCorrectStatus(self, status):
    """ Checks if the flag corresponds to one of the predefined
        STATUSES, check constructor for current set.
    """
    return status in self.STATUSES

  def _isCorrectDestinationType(self, destType):
    """ Checks if the destType corresponds to one of the predefined
        DESTINATION_TYPES, check constructor for current set.
    """
    return destType in self.DESTINATION_TYPES

  def sendMessage(self,
                  messageContent,
                  source='unspecified',
                  phase='unspecified',
                  status='info'):
    """ Sends the message after
        creating the correct format:
        including content, timestamp, status, source, phase and the uuid
        of the pilot.
    Returns:
      bool: False in case of any errors, True otherwise
    """
    if not self._isCorrectStatus(status):
      logging.error('status: ' + str(status) + ' is not correct')
      return False
    # if not self._isCorrectDestinationType( destinationType ):
      #logging.error('destination type: ' + str(destinationType ) + ' is not correct')
      # return False
    myUUID = getPilotUUIDFromFile(self.fileWithUUID)
    message = generateDict(
      myUUID,
      generateTimeStamp(),
      source,
      phase,
      status,
      messageContent
    )
    if not isMessageFormatCorrect(message):
      logging.warning("Message format is not correct.")
      return False
    encodedMsg = encodeMessage(message)
    self.messageSender.sendMessage(encodedMsg, flag=status)
    return False


def main():
  """ main() function  is used to send a message
      before any DIRAC related part is installed.
      Remember that it is assumed that the PilotUUID was
      already generated and stored into some file.
  """

  def singleWord(arg):
    if len(arg.split()) != 1:
      msg = 'argument must be single word'
      raise argparse.ArgumentTypeError(msg)
    return arg

  parser = argparse.ArgumentParser(description="command line interface to send logs to MQ system.",
                                   formatter_class=argparse.RawTextHelpFormatter,
                                   epilog='examples:\n'
                                   + '                   python PilotLogger.py InstallDIRAC installing info My message\n'
                                   + '                   python PilotLogger.py InstallDIRAC installing debug Debug message\n'
                                   + '                   python PilotLogger.py "My message"\n'
                                   + '                   python PilotLogger.py "My message" --output myFileName\n'
                                  )
  parser.add_argument('source',
                      type=singleWord,
                      nargs='?',
                      default='unspecified',
                      help='Source of the message e.g. "InstallDIRAC". It must be one word. '
                      + 'If not specified it is set to "unspecified".')
  parser.add_argument('phase',
                      type=singleWord,
                      nargs='?',
                      default='unspecified',
                      help='Phase of the process e.g. "fetching". It must be one word. '
                      + 'If not specified it is set to "unspecified".')
  parser.add_argument('status',
                      nargs='?',
                      choices=PilotLogger.STATUSES,
                      default='info',
                      help='Allowed values are: ' +
                      ', '.join(PilotLogger.STATUSES)
                      + '. If not specified it is set to "info".',
                      metavar='status ')
  parser.add_argument('message',
                      nargs='+',
                      help='Human readable content of the message. ')
  parser.add_argument('--output',
                      help='Log the content to the specified file'
                      + ' instead of sending it to the Message Queue server.')
  args = parser.parse_args()

  if len(" ".join(args.message)) >= 200:
    raise argparse.ArgumentTypeError(
      'message must be less than 200 characters')
  if args.output:
    logger = PilotLogger(localOutputFile=args.output)
  else:
    logger = PilotLogger()
  logger.sendMessage(messageContent=" ".join(args.message),
                     source=args.source,
                     phase=args.phase,
                     status=args.status)


if __name__ == '__main__':
  main()
