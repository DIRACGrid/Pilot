""" Message sender module for the remote logging system.
    It provides the general interface of the message sender and
    several implementations that e.g. allows to send the message
    to a REST interface or to a MQ server using the Stomp protocol.
    The instances of message senders should be created by using
    messageSenderFactory() that takes one string argument corresponding
    to message sender type we want to create (see messageSenderFactory docstring for details)
    and the optional parameters params that will be passed to sender message instance.
    For parameter details see given sender message implementation.
    e.g to create a message sender that will send messages to a local file 'myFile':
    myLocalSender = messageSenderFactory('LOCAL_FILE', params ={'LocalOutputFile': 'myFile'})
    myLocalSender.sendMessage("blabla", "myFlag")
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

import json
import os

try:
    import stomp
except ImportError:
    stomp = None

############################
# python 2 -> 3 "hacks"
try:
    import Queue as queue
except ImportError:
    import queue


try:
    from urlparse import urlunsplit
except ImportError:
    from urllib.parse import urlunsplit
try:
    from urllib2 import urlopen
    from urllib import urlencode
except ImportError:
    from urllib.request import urlopen
    from urllib.parse import urlencode

import ssl


def loadAndCreateObject(moduleName, className, params):
    """
    Function loads the class from the module and creates
    the instance of this class by using params arguments
    example usage: myObj = loadAndCreateObject('Pilot.MessageSender', 'StompSender',params)
    Args:
      moduleName(str): e.g. 'Pilot.MessageSender' or 'MessageSender'
      className(str): e.g. 'StompSender'
      params: arguments passed to __init__ of the class.
    Return:
      obj: Created instance of the class or None in case of errors.
    """
    myObj = None
    # In case of moduleName in the format of X.Y.Z, we have
    # mods =['X','Y','Z']. We are really interested in loading
    # 'Z' submodule.
    mods = moduleName.split(".")
    # The __import__ call with
    # fromlist option set to mods[-1]  will load Z submodule as expected.
    # Simpler X format will be also covered.
    module = __import__(moduleName, globals(), locals(), mods[-1])
    try:
        myClass = getattr(module, className)
        if params:
            myObj = myClass(params)
        else:
            myObj = myClass()

    except AttributeError:
        logging.error("Class %s  not found", className)
    return myObj


class MessageSender(object):
    """General interface of message sender."""

    def sendMessage(self, msg, flag):
        """Must be implemented by children classes."""
        raise NotImplementedError

    def finaliseLogs(self, myUUID):
        """Must be implemented by children classes."""
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
    typeToModuleAndClassName = {
        "LOCAL_FILE": {"module": "MessageSender", "class": "LocalFileSender"},
        "MQ": {"module": "MessageSender", "class": "StompSender"},
        "REST_API": {"module": "MessageSender", "class": "RESTSender"},
    }
    try:
        moduleName = typeToModuleAndClassName[senderType]["module"]
        className = typeToModuleAndClassName[senderType]["class"]

        logging.debug(
            "Trying to load and create object of module: %s, class: %s, params: %s",
            str(moduleName),
            str(className),
            str(params),
        )
        try:
            return loadAndCreateObject(moduleName, className, params)
        except ImportError:
            logging.warning("Module %s not found", moduleName)
            return loadAndCreateObject("Pilot." + moduleName, className, params)

    except ValueError:
        logging.error("Error initializing the message sender of type %s", senderType)
    return None


def createParamChecker(requiredKeys):
    """Function returns a function that can be used to check
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
    """
     Message sender to a REST interface.
    """

    REQUIRED_KEYS = ["Port", "Host"]

    def __init__(self, params):
        """
        Raises:
          ValueError: If params are not correct
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("in init of RESTSender")
        self._areParamsCorrect = createParamChecker(self.REQUIRED_KEYS)
        self.params = params
        if not self._areParamsCorrect(self.params):
            self.logger.error(
                "Parameters missing needed to send messages! Parameters:%s",
                str(self.params),
            )
            raise ValueError("Parameters missing needed to send messages")

    def sendMessage(self, msg, flag):
        """
        Send JSON encoded message.

        :param msg: JSON encoded python dict
        :type msg: str
        :param flag: an optional flag
        :type flag: str
        :return: True or False
        :rtype: bool
        """
        return self.invokeRemoteMethod("sendMessage", msg, flag)

    def finaliseLogs(self, myUUID):
        """
        Send pilot UUID (log file name) to the server. The server will mark a file as ready to
        be moved to the final location. The file might not be complete in the case when a pilot command
        exits with a code !=0, but it will still be saved.

        :param myUUID: pilot UUID (== temporary log file name)
        :type myUUID: string
        :return: True or False
        :rtype: bool
        """
        payload = json.dumps(myUUID)
        return self.invokeRemoteMethod("finaliseLogs", payload)

    def invokeRemoteMethod(self, method, msg, flag=None):
        """
        Invoke a remote method using REST interface.

        :param method: method name
        :type method: str
        :param msg: paylod (JSON encoded)
        :type msg: str
        :param flag: an optional flag
        :type flag: str
        :return: True on success or False
        :rtype: bool
        """

        # url might look like this: 'https://diractest.grid.hep.ph.ic.ac.uk:8444/WorkloadManagement/TornadoPilotLogging'
        host = self.params.get("Host")
        port = self.params.get("Port")
        netloc = ":".join((host, port))
        scheme = self.params.get("Scheme", "https")
        path = self.params.get("Path", "WorkloadManagement/TornadoPilotLogging")

        # hostKey = self.params.get('HostKey')
        # hostCertificate = self.params.get('HostCertificate')
        CACertificate = self.params.get("CACertificate")

        self.logger.debug("Sending message from the REST Sender %s", str(msg))
        try:
            # msg already encoded in json format
            # need to pass a single argument, as a json representation of a tuple:
            data = urlencode({"method": method, "args": json.dumps((msg,))})
            proxyLocation = os.environ.get("X509_USER_PROXY")
            caCertPath = os.environ.get("X509_CERT_DIR")
            context = ssl.create_default_context()
            context.load_verify_locations(capath=caCertPath)
            context.load_cert_chain(proxyLocation)
            url = urlunsplit((scheme, netloc, path, "", ""))
            res = urlopen(url, data, context=context)
            if res:
                result = res.read()
                self.logger.debug("Server response: %s ", str(result))
        except (IOError) as e:  # pylint: disable=undefined-variable
            self.logger.error(str(e))
            return False
        return True


def eraseFileContent(filename):
    """Erases the content of a given file."""
    with open(filename, "w+") as myFile:
        myFile.truncate()


def saveMessageToFile(msg, filename="myLocalQueueOfMessages"):
    """Adds the message to a file appended as a next line."""
    with open(filename, "a+") as myFile:
        myFile.write(msg + "\n")


def readMessagesFromFileAndEraseFileContent(filename="myLocalQueueOfMessages"):
    """Generates the queue FIFO and fills it
        with values from the file, assuming that one line
        corresponds to one message.
        Finally the file content is erased.
    Returns:
      Queue:
    """
    rqueue = queue.Queue()
    with open(filename, "r") as myFile:
        for line in myFile:
            rqueue.put(line)
    eraseFileContent(filename)
    return rqueue


class LocalFileSender(MessageSender):
    """Message sender to a local file."""

    REQUIRED_KEYS = ["LocalOutputFile"]

    def __init__(self, params):
        """
        Raises:
          ValueError: If params are not correct.
        """
        logging.debug("in init of LocalFileSender")
        self._areParamsCorrect = createParamChecker(self.REQUIRED_KEYS)
        self.params = params
        if not self._areParamsCorrect(self.params):
            logging.error(
                "Parameters missing needed to send messages! Parameters:%s",
                str(self.params),
            )
            raise ValueError("Parameters missing needed to send messages")

    def sendMessage(self, msg, flag):
        logging.debug("in sendMessage of LocalFileSender")
        filename = self.params.get("LocalOutputFile")
        saveMessageToFile(msg, filename=filename)
        return True


class StompSender(MessageSender):
    """Stomp message sender.
    It depends on stomp module.
    """

    REQUIRED_KEYS = [
        "HostKey",
        "HostCertificate",
        "CACertificate",
        "QueuePath",
        "LocalOutputFile",
    ]

    def __init__(self, params):
        """
        Raises:
          ValueError: If params are not correct.
        """

        self._areParamsCorrect = createParamChecker(self.REQUIRED_KEYS)
        self.params = params
        if not self._areParamsCorrect(self.params):
            logging.error(
                "Parameters missing needed to send messages! Parameters:%s",
                str(self.params),
            )
            raise ValueError("Parameters missing needed to send messages")

    def sendMessage(self, msg, flag):
        """Method first copies the message content to the
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

        wqueue = self.params.get("QueuePath")
        host = self.params.get("Host")
        port = int(self.params.get("Port"))
        hostKey = self.params.get("HostKey")
        hostCertificate = self.params.get("HostCertificate")
        CACertificate = self.params.get("CACertificate")
        filename = self.params.get("LocalOutputFile")

        saveMessageToFile(msg, filename)
        connection = self._connect(
            (host, port),
            {
                "key_file": hostKey,
                "cert_file": hostCertificate,
                "ca_certs": CACertificate,
            },
        )
        if not connection:
            return False
        self._sendAllLocalMessages(connection, wqueue, filename)
        self._disconnect(connection)
        return True

    def _connect(self, hostAndPort, sslCfg):
        """Connects to MQ server and returns connection
            handler or None in case of connection down.
            Stomp-depended function.
        Args:
          hostAndPort(list): of tuples, containing ip address and the port
                             where the message broker is listening for stomp
                             connections. e.g. [(127.0.0.1,6555)]
          sslCfg(dict): with three keys 'key_file', 'cert_file', and 'ca_certs'.
        Return:
          stomp.Connection: or None in case of errors.
        """
        if not sslCfg:
            logging.error("sslCfg argument is None")
            return None
        if not hostAndPort:
            logging.error("hostAndPort argument is None")
            return None
        if not all(key in sslCfg for key in ["key_file", "cert_file", "ca_certs"]):
            logging.error("Missing sslCfg keys")
            return None

        try:
            connection = stomp.Connection(
                host_and_ports=hostAndPort, use_ssl=True
            )  # pylint: disable=undefined-variable
            connection.set_ssl(
                for_hosts=hostAndPort,
                key_file=sslCfg["key_file"],
                cert_file=sslCfg["cert_file"],
                ca_certs=sslCfg["ca_certs"],
            )
            connection.start()  # pylint: disable=no-member
            connection.connect()  # pylint: disable=no-member
            return connection
        except stomp.exception.ConnectFailedException:  # pylint: disable=undefined-variable
            logging.error("Connection error")
            return None
        except IOError:
            logging.error("Could not find files with ssl certificates")
            return None

    def _send(self, msg, destination, connectHandler):
        """Sends a message and logs info.
        Stomp-depended function.
        """
        if not connectHandler:
            return False
        connectHandler.send(destination=destination, body=msg)
        logging.info(" [x] Sent %r ", msg)
        return True

    def _disconnect(self, connectHandler):
        """Disconnects.
        Stomp-depended function.
        """
        connectHandler.disconnect()

    def _sendAllLocalMessages(self, connectHandler, destination, filename):
        """Retrieves all messages from the local storage
        and sends it.
        """
        rqueue = readMessagesFromFileAndEraseFileContent(filename)
        while not rqueue.empty():
            msg = rqueue.get()
            self._send(msg, destination, connectHandler)
