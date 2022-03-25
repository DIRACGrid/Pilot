""" Pilot logger module for the remote logging system.
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import logging

############################
# python 2 -> 3 "hacks"
try:
    from argparse import ArgumentTypeError
    from argparse import ArgumentParser
    from argparse import RawTextHelpFormatter
except ImportError:  # argparse is from python 2.7+
    from optparse import OptParseError as ArgumentTypeError
    from optparse import OptionParser as ArgumentParser

try:
    from Pilot.PilotLoggerTools import generateDict, encodeMessage
    from Pilot.PilotLoggerTools import generateTimeStamp
    from Pilot.PilotLoggerTools import isMessageFormatCorrect
    from Pilot.PilotLoggerTools import readPilotJSONConfigFile
    from Pilot.PilotLoggerTools import getUniqueIDAndSaveToFile
    from Pilot.MessageSender import messageSenderFactory
except ImportError:
    from PilotLoggerTools import generateDict, encodeMessage
    from PilotLoggerTools import generateTimeStamp
    from PilotLoggerTools import isMessageFormatCorrect
    from PilotLoggerTools import readPilotJSONConfigFile
    from PilotLoggerTools import getUniqueIDAndSaveToFile
    from MessageSender import messageSenderFactory
############################


def getPilotUUIDFromFile(filename="PilotUUID"):
    """Retrieves Pilot UUID from the file of given name.
    Returns:
      str: empty string in case of errors.
    """

    try:
        with open(filename, "r") as myFile:
            uniqueId = myFile.read()
        return uniqueId
    except IOError:
        logging.error("Could not open the file with UUID:" + filename)
        return ""


def addMissingConfiguration(config, defaultConfig=None):
    """Creates new dict which contains content of config with added missing keys
      and values  defined in defaultConfig.
      If a key from defaultConfig is absent in config set, the value,key pair is added.
      If a key is present but the value is None, then the value from defaultConfig is assigned.
      The default config contains the following structure:
      {'LoggingType':'LOCAL_FILE','LocalOutputFile': 'myLocalQueueOfMessages', 'FileWithID': 'PilotUUID'}
    Args:
      config(dict):
      defaultConfig(dict):
    Returns:
      dict:
    """
    if defaultConfig is None:
        defaultConfig = {
            "LoggingType": "LOCAL_FILE",
            "LocalOutputFile": "myLocalQueueOfMessages",
            "FileWithID": "PilotUUID",
        }
    if not config or not isinstance(config, dict):
        return defaultConfig

    currConfig = config.copy()
    for k, v in defaultConfig.items():
        if k not in currConfig:
            currConfig[k] = v
        else:
            if currConfig[k] is None:
                currConfig[k] = v
    return currConfig


class PilotLogger(object):
    """Base pilot logger class."""

    STATUSES = ["info", "warning", "error", "debug"]

    def __init__(
        self,
        configFile="pilot.json",
        messageSenderType="LOCAL_FILE",
        localOutputFile="myLocalQueueOfMessages",
        fileWithUUID="PilotUUID",
        setup="DIRAC-Certification",
    ):
        """ctr loads the configuration parameters from the json file
            or if the file does not exists, loads the default set
            of values. Next, if self.fileWithUUID is not set (this
            variable corresponds to the name of the file with Pilot
            Agent ID) the default value is used, and if the file does
            not exist, the Pilot ID is created and saved in this file.
        Args:
          configFile(str): Name of the file with the configuration parameters.
          messageSenderType(str): Type of the message sender to use e.g. to a REST interface,
            to a message queue or to a local file.
          localOutputFile(str): Name of the file that can be used to store the log messages locally.
          fileWithUUID(str): Name of the file used to store the Pilot identifier.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("In init of PilotLogger")
        self.STATUSES = PilotLogger.STATUSES

        self.params = addMissingConfiguration(
            config=readPilotJSONConfigFile(configFile, setup),
            defaultConfig={
                "LoggingType": messageSenderType,
                "LocalOutputFile": localOutputFile,
                "FileWithID": fileWithUUID,
            },
        )

        fileWithID = self.params["FileWithID"]
        if os.path.isfile(fileWithID):
            self.logger.warning(
                "The file: "
                + fileWithID
                + " already exists. The content will be used to get UUID."
            )
        else:
            result = getUniqueIDAndSaveToFile(filename=fileWithID)
            if not result:
                self.logger.error("Error while generating pilot logger id.")
        self.messageSender = messageSenderFactory(
            senderType=self.params["LoggingType"], params=self.params
        )
        if not self.messageSender:
            self.logger.error("Something went wrong - no messageSender created.")

    def _isCorrectStatus(self, status):
        """Checks if the flag corresponds to one of the predefined
        STATUSES, check constructor for current set.
        """
        return status in self.STATUSES

    def sendMessage(
        self, messageContent, source="unspecified", phase="unspecified", status="info"
    ):
        """
        Sends a message after creating the correct JSON format including content, timestamp, status,
        source, phase and the UUID of the pilot.

        :param messageContent: actual human-readable message
        :type messageContent: str
        :param source: source of the message (unused)
        :type source: str
        :param phase: phase of the pilot (unused)
        :type phase: str
        :param status: message status( level)
        :type status: str
        :return: false in case of any errors, True otherwise
        :rtype: bool
        """

        if not self._isCorrectStatus(status):
            self.logger.error("status: %s is not correct", str(status))
            return False
        myUUID = getPilotUUIDFromFile(self.params["FileWithID"])
        message = generateDict(
            myUUID, generateTimeStamp(), source, phase, status, messageContent
        )
        if not isMessageFormatCorrect(message):
            self.logger.warning("Message format is not correct.")
            return False
        self.logger.debug("sendMessage: %s ", message)
        encodedMsg = encodeMessage(message)
        return self.messageSender.sendMessage(encodedMsg, flag=status)

    def finaliseLogs(self):
        """
        Finalise logs. For the file cache server plugin trigger a 'os.rename file file.log' command to indicate that
        the target file is final (not necessarily complete in case when errors in pilot commands execution occur).

        :return: True if successful or False otherwise
        :rtype:  bool
        """
        myUUID = getPilotUUIDFromFile(self.params["FileWithID"])
        return self.messageSender.finaliseLogs({"pilotUUID": myUUID})


def main():
    """main() function  is used to send a message
    before any DIRAC related part is installed.
    Remember that it is assumed that the PilotUUID was
    already generated and stored into some file.
    """

    def singleWord(arg):
        if len(arg.split()) != 1:
            msg = "argument must be single word"
            raise ArgumentTypeError(msg)
        return arg

    parser = ArgumentParser(
        description="command line interface to send logs to MQ system.",
        formatter_class=RawTextHelpFormatter,
        epilog="examples:\n"
        + "                   python PilotLogger.py InstallDIRAC installing info My message\n"
        + "                   python PilotLogger.py InstallDIRAC installing debug Debug message\n"
        + '                   python PilotLogger.py "My message"\n'
        + '                   python PilotLogger.py "My message" --output myFileName\n',
    )

    parser.add_argument(
        "source",
        type=singleWord,
        nargs="?",
        default="unspecified",
        help='Source of the message e.g. "InstallDIRAC". It must be one word. '
        + 'If not specified it is set to "unspecified".',
    )
    parser.add_argument(
        "phase",
        type=singleWord,
        nargs="?",
        default="unspecified",
        help='Phase of the process e.g. "fetching". It must be one word. '
        + 'If not specified it is set to "unspecified".',
    )
    parser.add_argument(
        "status",
        nargs="?",
        choices=PilotLogger.STATUSES,
        default="info",
        help="Allowed values are: "
        + ", ".join(PilotLogger.STATUSES)
        + '. If not specified it is set to "info".',
        metavar="status ",
    )
    parser.add_argument(
        "message", nargs="+", help="Human readable content of the message. "
    )
    parser.add_argument(
        "--output",
        help="Log the content to the specified file"
        + " instead of sending it to the Message Queue server.",
    )
    args = parser.parse_args()

    if len(" ".join(args.message)) >= 200:
        raise ArgumentTypeError("message must be less than 200 characters")
    if args.output:
        logger = PilotLogger(localOutputFile=args.output)
    else:
        logger = PilotLogger()
    logger.sendMessage(
        messageContent=" ".join(args.message),
        source=args.source,
        phase=args.phase,
        status=args.status,
    )


if __name__ == "__main__":
    main()
