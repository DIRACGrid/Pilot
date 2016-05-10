#!/usr/bin/env python

import PilotLogger
import stomp
def main():
  print simpleTestPilotLogger()

def simpleTestPilotLogger():
  return "blabla"
#PILOT_UUID="37356d94-15c6-11e6-a600-606c663dde16  
  #echo -n "$PILOT_UUID" > "PilotAgentUUID"
  #EXPECTED_MSG='{"status": "Landed", "timestamp": "1462789339.68", "pilotUUID": "37356d94-15c6-11e6-a600-606c663dde16", "minorStatus": "I will send an SOS to the world!", "source": "pilot"}'
  #python PilotLogger.py "I will send an SOS to the world!"
  #RECV_MSG=$(python consumeFromQueue.py)
  #RESULT=$(python compare.py "$RECV_MSG" "$EXPECTED_MSG")
  

if __name__ == '__main__':
  main()
