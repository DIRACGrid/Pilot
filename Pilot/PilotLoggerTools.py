"""A set of tools for the remote pilot agent logging system
"""


import sys
import os
import logging
import time
import json
from uuid import uuid1

__RCSID__ = "$Id$"


def createPilotLoggerConfigFile(filename='PilotLogger.json',
                                loggingType='',
                                localOutputFile='',
                                host='',
                                port='',
                                url='',
                                key_file='',
                                cert_file='',
                                ca_certs='',
                                fileWithID='',
                                queue=None,
                                setup='DIRAC-Certification'):
  """Helper function that creates a test configuration file.
     The format is json encoded file.
     The created file can be mainy used for testing of PilotLogger setups, since
     the included parameters are related only to communication settings, and  many
     other parameters are not present.
     Arguments:
      queue(dict): e.g. {"lhcb.test.*":{"Persitent":"False", "Ackonwledgement":"False"}}
  """
  if queue is None:
    queue = {}
  keys = [
      'LoggingType',
      'LocalOutputFile',
      'Host',
      'Port',
      'Url',
      'HostKey',
      'HostCertificate',
      'CACertificate',
      'FileWithID',
      'Queue'
  ]
  values = [
      loggingType,
      localOutputFile,
      host,
      port,
      url,
      key_file,
      cert_file,
      ca_certs,
      fileWithID,
      queue
  ]
  config = dict(zip(keys, values))
  content = dict()
  content['Setups'] = {}
  content['Setups'][setup] = {}
  content['Setups'][setup]['Logging'] = config
  config = json.dumps(content)
  with open(filename, 'w') as myFile:
    myFile.write(config)


def readPilotJSONConfigFile(filename, setup='DIRAC-Certification'):
  """Helper function that loads configuration settings from a pilot json file.
     It is assumed that the json file contains the section "Logging" embedded in
     the following form:
      {
        "Setups": {
          "DIRAC-Certification": {
            "Logging": {
            }
          }
        }
      }
      Only information from Logging section are considered. If any of the
      corresponding key is missing, then the None is a assigned
  Args:
    str(filename):
  Returns:
    dict: with the following keys (not all are obligatory):
      'LoggingType', 'LocalOutputFile', 'Host','Port','QueuePath','HostKey','HostCertificate','Url',
      'CACertificate','FileWithID' or None in case of errors.
  """
  pilotJSON = None
  try:
    with open(filename, 'r') as myFile:
      pilotJSON = json.load(myFile)
  except (IOError, ValueError):
    logging.warning('Could not open or load the configuration file:' + filename)
    return None
  try:
    partial = pilotJSON['Setups'][setup]['Logging']
  except KeyError:
    logging.error('Loaded data does not have the correct section format')
    return None
  keys = [
      "LoggingType",
      "LocalOutputFile",
      'Host',
      'Port',
      'Url',
      'HostKey',
      'HostCertificate',
      'CACertificate',
      'FileWithID'

  ]
  config = dict((k, partial.get(k)) for k in keys)
  # two special cases:
  try:
    config['QueuePath'] = '/queue/' + next(iter(partial.get('Queue')))
  except TypeError:
    config['QueuePath'] = None

  if config['FileWithID'] is None:
    config['FileWithID'] = 'PilotUUID'

  return config


def generateDict(pilotUUID, timestamp, source, phase, status, messageContent):
  """Helper function that returs a dictionnary based on the
     set of input values.
  Returns
    dict:
  """

  keys = [
      'pilotUUID',
      'timestamp',
      'source',
      'phase',
      'status',
      'messageContent'
  ]
  values = [
      pilotUUID,
      timestamp,
      source,
      phase,
      status,
      messageContent
  ]
  return dict(zip(keys, values))


def encodeMessage(content):
  """Method encodes the message in form of the serialized JSON string
     see https://docs.python.org/2/library/json.html#py-to-json-table
  Args:
    content(dict):
  Returns:
    str: in the JSON format.
  Raises:
    TypeError:if cannont encode json properly
  """
  return json.dumps(content)


def decodeMessage(msgJSON):
  """Decodes the message from the serialized JSON string
     See https://docs.python.org/2/library/json.html#py-to-json-table.
  Args:
    msgJSON(str):in the JSON format.
  Returns:
    str: decoded objecst.
  Raises:
    TypeError: if cannot decode JSON properly.
  """
  return json.loads(msgJSON)


def isMessageFormatCorrect(content):
  """Checks if input format is correct.
     Function checks if the input format is a dictionnary
     in the following format:
     0) content is a dictionary,
     1) it contains only those keys of basestring types:
     'pilotUUID', 'status', 'messageContent', 'timestamp', 'source','phase'
     2) it contains only values of basestring types.
  Args:
    content(dict): all values must be non-empty
  Returns:
    bool: True if message format is correct, False otherwise
  Example:
    {"status": "info",
     "timestamp": "1427121370.7",
      "messageContent": "Uname = Linux localhost 3.10.64-85.cernvm.x86_64",
      "pilotUUID": "eda78924-d169-11e4-bfd2-0800275d1a0a",
      "phase": "Installing",
      "source": "InstallDIRAC"
      }
  """
  if not isinstance(content, dict):
    return False
  refKeys = sorted([
      'pilotUUID',
      'status',
      'messageContent',
      'timestamp',
      'phase',
      'source'
  ])
  keys = sorted(content.keys())
  if not keys == refKeys:
    return False
  values = content.values()
  # if any value is not of basestring type
  if any(not isinstance(val, basestring) for val in values):
    return False
  # checking if all elements are not empty
  if any(not val for val in values):
    return False
  return True


def generateTimeStamp():
  """Generates the current timestamp in Epoch format.
  Returns:
    str: with number of seconds since the Epoch.
  """
  return str(time.time())


def generateUniqueID():
  """Generates a unique identifier based on uuid1 function
  Returns:
    str: containing uuid
  """
  return str(uuid1())


def getUniqueIDAndSaveToFile(filename='PilotUUID'):
  """Generates the unique id and writes it to a file
     of given name.
     First, we try to receive the UUID from the OS, if that fails
     the local uuid is generated.
  Args:
    filename(str): file to which the UUID will be saved
  Returns:
    bool: True if everything went ok False if there was an error with the file
  """
  myId = getUniqueIDFromOS()
  if not myId:
    myId = generateUniqueID()
  try:
    with open(filename, 'w') as myFile:
      myFile.write(myId)
    return True
  except IOError:
    logging.error('could not open file')
    return False


def getUniqueIDFromOS():
  """Retrieves unique identifier based on specific OS.
    The OS type is identified based on some predefined
    environmental variables that should contain identifiers
    for given node. For VM the combination of 3 variables is used to
    create the identifier. Only the first found identifier is returned
  Returns:
    str: If variable(s)  found the generated identifier is returned. Empty
          string is returned if all checks fails. If there are more than one
          valid identifier, only the first one is returned.
  """
  # VM case: vm://$CE_NAME/$CE_NAME:$VMTYPE:$VM_UUID
  vmEnvVars = ['CE_NAME', 'VMTYPE', 'VM_UUID']
  if all(var in os.environ for var in vmEnvVars):
    ce_name = os.environ.get('CE_NAME')
    partial_id = ':'.join((os.environ.get(var) for var in vmEnvVars))
    return 'vm://' + ce_name + '/' + partial_id
  # Other cases: $envVar
  envVars = ['CREAM_JOBID', 'GRID_GLOBAL_JOBID']
  ids = (os.environ.get(var) for var in envVars if var in os.environ)
  return next(ids, '')


def main():
  """Is used to generate the pilot uuid
     and save it to a file even
     before any DIRAC related part is installed.
  """
  filename = ' '.join(sys.argv[1:])
  if not filename:
    getUniqueIDAndSaveToFile()
  else:
    getUniqueIDAndSaveToFile(filename)


if __name__ == '__main__':
  main()
