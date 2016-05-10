#!/usr/bin/env python

import PilotLogger
import consumeFromQueue
import os

def main():
  print simpleTestPilotLogger()

def simpleTestPilotLogger():
  uuid ="37356d94-15c6-11e6-a600-606c663dde16"
  filenameUUID = "PilotAgentUUID"
  expectedMsg='{"status": "Landed", "timestamp": "1462789339.68", "pilotUUID": "37356d94-15c6-11e6-a600-606c663dde16", "minorStatus": "I will send an SOS to the world!", "source": "pilot"}'
  with open ( filenameUUID , 'w' ) as myFile:
    myFile.write( uuid )

  os.system("python PilotLogger.py \"I will send an SOS to the world!\"")
  consumeFromQueue.consume()
  return "blabla"

if __name__ == '__main__':
  main()
