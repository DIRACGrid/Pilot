#!/usr/bin/env python
import sys
import json
  
def main():
  (res1, res2) = (sys.argv[1], sys.argv[2])  or "Something wrong nothing to compare!"
  print "******blabal**"
  print res1
  print res2 
  #return compareResults(res1, res2)  

def compareResults(msg1, msg2):
  print msg1
  print msg2
  #msg1 = json.loads(msg1)   
  #msg2 = json.loads(msg2)   
  #msg1 = msg1.pop("timestamp", None)
  #msg2 = msg2.pop("timestamp", None)
  return msg1 == msg2 

if __name__ == '__main__':
  main()
