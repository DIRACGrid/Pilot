""" Message sender module for the remote logging system.
    It provides the general interface of the message sender and
    several implementations that e.g. allows to send the message
    to a REST interface or to a MQ server using the Stomp protocol.
"""

import Queue
import logging
import stomp
import requests

import importlib

def objectLoader(moduleName, className, params):
  module = importlib.import_module(moduleName)
  my_class = getattr(module, className)
  my_instance = my_class(params)
  return my_instance

class MessageSender(object):
  """ General interface of message sender.
  """

  def sendMessage(self, msg, flag):
    """ Must be implemented by children classes.
    """
    raise NotImplementedError

def messageSenderFactory(senderType, params):
  """
  Function creates MessageSender according to sender type.
  Args:
    senderType(str): sender type to be created.
                    The allowed types are 'LOCAL_FILE', 'MQ', 'REST_API',
    params(dict): additional parameters passed to init
  Return:
    MessageSender or None in case of errors

  """
  senderTypeToClassName={'LOCAL_FILE':'LocalFileSender','MQ':'StompSender', 'REST_API':'RESTSender'}
  try:
    return objectLoader('Pilot.MessageSender', senderTypeToClassName[senderType], params)
  except ValueError:
    logging.error("Error initializing the message sender")
  return None

def createParamChecker(requiredKeys):
  """ Function returns a function that can be used to check
      if the parameters in form of a dictionary contain
      the required set of keys. Also it checks if the parameters
      are not empty.
    Args:
      requiredKeys(list)
    Return:
      function: or None if requiredKeys is None
  """
  if not requiredKeys:
    return None

  def areParamsCorrect(params):
    """
      Args:
        params(dict):
      Return:
        bool:
    """
    if not params:
      return False
    if not all(k in params for k in requiredKeys):
      return False
    return True
  return areParamsCorrect


class RESTSender(MessageSender):
  """ Message sender to a REST interface.
  """

  REQUIRED_KEYS = ['HostKey', 'HostCertififcate',
                   'CACertificate', 'Url', 'LocalOutputFile']

  def __init__(self, params):
    """
      Raises:
        ValueError: If params are not correct.
    """
    self._areParamsCorrect = createParamChecker(self.REQUIRED_KEYS)
    self.params = params
    if not self._areParamsCorrect(self.params):
      raise ValueError("Parameters missing needed to send messages")

  def sendMessage(self, msg, flag):
    url = self.params.get('Url')
    hostKey = self.params.get('HostKey')
    hostCertificate = self.params.get('HostCertificate')
    CACertificate = self.params.get('CACertificate')

    try:
      requests.post(url, json=msg, cert=(
        hostCertificate, hostKey), verify=CACertificate)
    except (requests.exceptions.RequestException, IOError) as e:
      logging.error(e)
      return False
    return True


def eraseFileContent(filename):
  """ Erases the content of a given file.
  """
  with open(filename, 'w+') as myFile:
    myFile.truncate()


def saveMessageToFile(msg, filename='myLocalQueueOfMessages'):
  """ Adds the message to a file appended as a next line.
  """
  with open(filename, 'a+') as myFile:
    myFile.write(msg+'\n')


def readMessagesFromFileAndEraseFileContent(filename='myLocalQueueOfMessages'):
  """ Generates the queue FIFO and fills it
      with values from the file, assuming that one line
      corresponds to one message.
      Finally the file content is erased.
  Returns:
    Queue:
  """
  queue = Queue.Queue()
  with open(filename, 'r') as myFile:
    for line in myFile:
      queue.put(line)
  eraseFileContent(filename)
  return queue


class LocalFileSender(MessageSender):
  """ Message sender to a local file.
  """

  REQUIRED_KEYS = ['LocalOutputFile']

  def __init__(self, params):
    """
      Raises:
        ValueError: If params are not correct.
    """
    self._areParamsCorrect = createParamChecker(self.REQUIRED_KEYS)
    self.params = params
    if not self._areParamsCorrect(self.params):
      raise ValueError("Parameters missing needed to send messages")

  def sendMessage(self, msg, flag):
    filename = self.params.get('LocalOutputFile')
    saveMessageToFile(msg, filename=filename)
    return True


def connect(hostAndPort, sslCfg):
  """ Connects to MQ server and returns connection
      handler or None in case of connection down.
      Stomp-depended function.
  """
  if not sslCfg:
    logging.error("sslCfg argument is None")
    return None
  if not hostAndPort:
    logging.error("hostAndPort argument is None")
    return None
  if not all(key in sslCfg for key in ['key_file', 'cert_file', 'ca_certs']):
    logging.error("Missing ssl_cfg keys")
    return None

  try:
    connection = stomp.Connection(host_and_ports=hostAndPort, use_ssl=True)
    connection.set_ssl(for_hosts=hostAndPort,
                       key_file=sslCfg['key_file'],
                       cert_file=sslCfg['cert_file'],
                       ca_certs=sslCfg['ca_certs'])
    connection.start()
    connection.connect()
    return connection
  except stomp.exception.ConnectFailedException:
    logging.error('Connection error')
    return None
  except IOError:
    logging.error('Could not find files with ssl certificates')
    return None


def send(msg, destination, connectHandler):
  """Sends a message and logs info.
     Stomp-depended function.
  """
  if not connectHandler:
    return False
  connectHandler.send(destination=destination,
                      body=msg)
  logging.info(" [x] Sent %r ", msg)
  return True


def disconnect(connectHandler):
  """Disconnects.
     Stomp-depended function.
  """
  connectHandler.disconnect()

def sendAllLocalMessages(connectHandler, destination, filename):
  """ Retrieves all messages from the local storage
      and sends it.
  """
  queue = readMessagesFromFileAndEraseFileContent(filename)
  while not queue.empty():
    msg = queue.get()
    send(msg, destination, connectHandler)

class StompSender(MessageSender):
  """ Stomp message sender.
  """

  REQUIRED_KEYS = ['HostKey', 'HostCertififcate',
                   'CACertificate', 'QueuePath', 'LocalOutputFile']

  def __init__(self, params):
    """
      Raises:
        ValueError: If params are not correct.
    """

    self._areParamsCorrect = createParamChecker(self.REQUIRED_KEYS)
    self.params = params
    if not self._areParamsCorrect(self.params):
      raise ValueError("Parameters missing needed to send messages")

  def sendMessage(self, msg, flag):
    """ Method first copies the message content to the
        local storage, then it checks if the connection
        to the MQ server is up,
        If it is the case it sends all messages stored
        locally.  The string flag can be used as routing_key,
        it can contain:  'info', 'warning', 'error',
        'debug'. If the connection is down, the method
        does nothing and returns False
    Returns:
      bool: False in case of any errors, True otherwise
    """

    queue = self.params.get('QueuePath')
    host = self.params.get('Host')
    port = int(self.params.get('Port'))
    hostKey = self.params.get('HostKey')
    hostCertificate = self.params.get('HostCertificate')
    CACertificate = self.params.get('CACertificate')
    filename = self.params.get('LocalOutputFile')

    saveMessageToFile(msg, filename)
    connection = connect((host, port), {
      'key_file': hostKey, 'cert_file': hostCertificate, 'ca_certs': CACertificate})
    if not connection:
      return False
    sendAllLocalMessages(connection, queue, filename)
    disconnect(connection)
    return True
