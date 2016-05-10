#!/usr/bin/env python

import PilotLogger
import consumeFromQueue
import os

def main():
  print simpleTestPilotLogger()

def simpleTestPilotLogger():
  uuid ="37356d94-15c6-11e6-a600-606c663dde16"
  filenameUUID = "PilotAgentUUID"
  expectedMsgs = []
  expectedMsgs.append('{"status": "Landed", "timestamp": "1462789339.68", "pilotUUID": "37356d94-15c6-11e6-a600-606c663dde16", "minorStatus": "I will send an SOS to the world!", "source": "pilot"}')

  with open ( filenameUUID , 'w' ) as myFile:
    myFile.write( uuid )

  os.system("python PilotLogger.py \"I will send an SOS to the world!\"")
  recvMsgs = consumeFromQueue.consume()
  #we get rid of the timestamp
  expectedMsgs = [x.pop("timestamp",None) for x in expectedMsgs]
  recvMsgs = [x.pop("timestamp",None) for x in expectedMsgs]
  if expectedMsgs == recvMsgs:
    print "ok"
  else:
    print expectedMsgs
    print recvMsgs
    print "not ok"

if __name__ == '__main__':
  main()
