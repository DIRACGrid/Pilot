""" Message sender module for the remote loggin system.
    It provides the general interface of the message sender and
    several implementations that e.g. allows to send the message
    to a REST interface or to a MQ server using the Stomp protocol.
"""

import Queue
import logging
import stomp


class MessageSender(object):
  """ General interface of message sender.
  """

  def sendMessage(self, msg, flag):
    """ Must be implemented by children classes.
    """
    raise NotImplementedError


def createMessageSender(senderType):
  """
  Function creates MessageSender according to sender type.
  Args:
    senderType(str):sender type to be created. 
                    The allowed types are 'MQ', 'REST_API', 'LOCAL_FILE' 
  Returns:
    MessageSender or None if senderType is unknown

  """

  if senderType == 'MQ':
    return StompSender
  elif senderType == 'REST_API':
    return RESTSender
  elif senderType == 'LOCAL_FILE':
    return LocalFileSender
  logging.error("Unknown message sender type")
  return None


class RESTSender(MessageSender):
  """ Message sender to a REST interface.
  """

  def sendMessage(self, msg, flag):
    return False
    #r = requests.post('https://localhost:8888/my', json=msg, cert=('/home/krzemien/workdir/lhcb/dirac_development/etc/grid-security/hostcert.pem', '/home/krzemien/workdir/lhcb/dirac_development/etc/grid-security/hostkey.pem'), verify='/home/krzemien/workdir/lhcb/dirac_development/etc/grid-security/allCAs.pem')
    #r = requests.post('https://localhost:8888/my', json=msg, cert=('/home/krzemien/workdir/lhcb/dirac_development/etc/grid-security/hostcert.pem', '/home/krzemien/workdir/lhcb/dirac_development/etc/grid-security/hostkey.pem'), verify=False)
    # r.text
    # return True


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

  def sendMessage(self, msg, flag):
    # to change
    saveMessageToFile(msg, filename='myLocalQueueOfMessages')
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


class StompSender(MessageSender):
  """ Stomp message sender.
  """

  def __init__(self, networkCfg, sslConfig):
    self.fileWithUUID = ''
    self.networkCfg = None
    self.queuePath = ''
    self.sslCfg = None
    # maybe directly from json
    # for a moment from args
    self.networkCfg = networkCfg
    self.sslCfg = sslConfig

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

    saveMessageToFile(msg)
    connection = connect(self.networkCfg, self.sslCfg)
    if not connection:
      return False
    self._sendAllLocalMessages(connection, flag)
    disconnect(connection)
    return True

  def _sendAllLocalMessages(self, connect_handler, flag='info'):
    """ Retrives all messages from the local storage
        and sends it.
    """
    queue = readMessagesFromFileAndEraseFileContent()
    while not queue.empty():
      msg = queue.get()
      send(msg, self.queuePath, connect_handler)
