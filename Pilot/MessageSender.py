""" Message sender module for the remote loggin system.
    It provides the general interface of the message sender and
    several implementations that e.g. allows to send the message
    to a REST interface or to a MQ server using the Stomp protocol.
"""

import Queue
import logging
import stomp
import requests


class MessageSender(object):
  """ General interface of message sender.
  """

  def sendMessage(self, msg, flag):
    """ Must be implemented by children classes.
    """
    raise NotImplementedError


def createMessageSender(senderType, params):
  """
  Function creates MessageSender according to sender type.
  Args:
    senderType(str): sender type to be created.
                    The allowed types are 'LOCAL_FILE', 'MQ', 'REST_API',
    params(dict): additional parameters passed to init
  Return:
    MessageSender or None in case of errors

  """

  try:
    if senderType == 'LOCAL_FILE':
      return LocalFileSender(params)
    elif senderType == 'MQ':
      return StompSender(params)
    elif senderType == 'REST_API':
      return RESTSender(params)
    else:
      logging.error("Unknown message sender type")
  except ValueError:
    logging.error("Error initializing the message sender")
  return None


def createParamChecker(required_keys):
  """ Function returns a function that can be used to check
      if the parameters in form of the dictionnary (tuple) contain
      the required set of keys. Also it checks if the parameters
      are not empty.
    Args:
      required_keys(list)
    Return:
      function: or None if required_keys is None
  """
  if not required_keys:
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
    if not all(k in params for k in required_keys):
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
      Finallym the file content is erased.
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


def connect(host_and_port, ssl_cfg):
  """ Connects to RabbitMQ and returns connection
      handler or None in case of connection down.
      Stomp-depended function.
  """
  if not ssl_cfg:
    logging.error("ssl_cfg argument is None")
    return None
  if not host_and_port:
    logging.error("host_and_port argument is None")
    return None
  if not all(key in ssl_cfg for key in ['key_file', 'cert_file', 'ca_certs']):
    logging.error("Missing ssl_cfg keys")
    return None

  try:
    connection = stomp.Connection(host_and_ports=host_and_port, use_ssl=True)
    connection.set_ssl(for_hosts=host_and_port,
                       key_file=ssl_cfg['key_file'],
                       cert_file=ssl_cfg['cert_file'],
                       ca_certs=ssl_cfg['ca_certs'])
    connection.start()
    connection.connect()
    return connection
  except stomp.exception.ConnectFailedException:
    logging.error('Connection error')
    return None
  except IOError:
    logging.error('Could not find files with ssl certificates')
    return None


def send(msg, destination, connect_handler):
  """Sends a message and logs info.
     Stomp-depended function.
  """
  if not connect_handler:
    return False
  connect_handler.send(destination=destination,
                       body=msg)
  logging.info(" [x] Sent %r ", msg)
  return True


def disconnect(connect_handler):
  """Disconnects.
     Stomp-depended function.
  """
  connect_handler.disconnect()

def sendAllLocalMessages(connect_handler, destination, filename):
  """ Retrives all messages from the local storage
      and sends it.
  """
  queue = readMessagesFromFileAndEraseFileContent(filename)
  while not queue.empty():
    msg = queue.get()
    send(msg, destination, connect_handler)

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
        to RabbitMQ server is up,
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
