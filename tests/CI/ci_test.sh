#!/bin/bash

PILOTBRANCH=pilot_loggers
DEBUG=True

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

source TestCode/Pilot/tests/CI/pilot_ci.sh 
#<---- this file contains the tests logic

echo -e '***' $(date -u) "**** Pilot INSTALLATION START ****\n"

prepareForPilot
preparePythonEnvironment
cd $PILOTINSTALLDIR 
echo '==> [SimplePilotLogger ]'
RabbitServerCleanup #to assure that the queue is empty
python Test_simplePilotLogger.py
RabbitServerCleanup #to assure that the queue is empty
cd ../
