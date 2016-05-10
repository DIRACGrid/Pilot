#!/bin/bash

PILOTBRANCH=pilot_loggers
DEBUG=True

PILOTUSERDN=/DC=ch/DC=cern/OU=Organic Units/OU=Users/CN=wkrzemie/CN=643820/CN=Wojciech Jan Krzemien

echo -e "**** Starting Pilot tests with PilotLogger ****\n"

echo -e '***' $(date -u) "**** Getting the tests ****\n"

mkdir -p $PWD/TestCode
cd $PWD/TestCode

git clone https://github.com/wkrzemien/Pilot.git
cd Pilot
git checkout $PILOTBRANCH
echo `pwd`
cd ../..
echo `pwd`

echo -e '***' $(date -u) "**** Got the tests ****\n"

#source TestCode/Pilot/tests/CI/pilot_ci.sh 
source pilot_ci.sh 
#<---- this file contains the tests logic

echo -e '***' $(date -u) "**** Pilot INSTALLATION START ****\n"

runAllPilotTests
