#!/bin/bash
#-------------------------------------------------------------------------------
# pilot_ci
#
# Several functions used for Jenkins style jobs
# They may also work on other CI systems
#
#
# wojciech.krzemien@ncbj.gov.pl 
# based on F.Stagni dirac_ci script
# 09/05/2016
#-------------------------------------------------------------------------------

# A CI job needs:
#
# === environment variables (minimum set):
# DEBUG
# WORKSPACE
# PILOTBRANCH
#
# === a default directory structure is created:
# ~/TestCode
# ~/ServerInstallDIR
# ~/PilotInstallDIR




# Def of environment variables:

if [ ! -z "$DEBUG" ]
then
	echo '==> Running in DEBUG mode'
	DEBUG='-ddd'
else
	echo '==> Running in non-DEBUG mode'
fi

if [ ! -z "$WORKSPACE" ]
then
	echo '==> We are in Jenkins I guess'
else
  WORKSPACE=$PWD
fi

if [ ! -z "$PILOTBRANCH" ]
then
	echo '==> Working on Pilot branch ' $PILOTBRANCH
else
  PILOTBRANCH='master'
fi

echo `pwd`
echo $WORKSPACE
# Creating default structure
mkdir -p $WORKSPACE/TestCode # Where the test code resides
TESTCODE=$_
mkdir -p $WORKSPACE/ServerInstallDIR # Where servers are installed
SERVERINSTALLDIR=$_
mkdir -p $WORKSPACE/ClientInstallDIR # Where clients are installed
CLIENTINSTALLDIR=$_
mkdir -p $WORKSPACE/PilotInstallDIR # Where pilots are installed
PILOTINSTALLDIR=$_

function runAllPilotTests(){
  prepareForPilot
  simpleTestPilotLogger
  #FullPilotTestsWithWrapper
}

function prepareForPilot(){
	echo '==> [prepareForPilot]'

        PILOT_SCRIPTS_PATH=$TESTCODE/Pilot/Pilot 
        PILOT_LOGGER_PATH=$TESTCODE/Pilot/PilotLogger 
        PILOT_CI_PATH=$TESTCODE/Pilot/tests/CI
	#get the necessary scripts
	cp $PILOT_SCRIPTS_PATH/dirac-pilot.py $PILOTINSTALLDIR/
	cp $PILOT_SCRIPTS_PATH/pilotTools.py $PILOTINSTALLDIR/
	cp $PILOT_SCRIPTS_PATH/pilotCommands.py $PILOTINSTALLDIR/
        cp $PILOT_SCRIPTS_PATH/vm-pilot.sh $PILOTINSTALLDIR
        cp $PILOT_LOGGER_PATH/PilotLogger.py $PILOTINSTALLDIR/
        cp $PILOT_LOGGER_PATH/PilotLoggerTools.py $PILOTINSTALLDIR/
        cp $PILOT_CI_PATH/PilotLoggerTest.cfg $PILOTINSTALLDIR/PilotLogger.cfg
        cp $PILOT_CI_PATH/consumeFromQueue.py $PILOTINSTALLDIR
        cp $PILOT_CI_PATH/simpleTestPilotLogger.py $PILOTINSTALLDIR
        cp -r certificates $PILOTINSTALLDIR
}


#PilotLogger sends one message.
#Next it is taken from the RabbitMQ queue and 
#the content of the message is compared
function simpleTestPilotLogger(){

  echo '==> [simpleTestPilotLogger]'

  cd $PILOTINSTALLDIR 

  RabbitServerCleanup #to assure that the queue is empty

  RESULT=$(python simpleTestPilotLogger.py)

  RabbitServerCleanup #to assure that the queue is empty

  cd ../

  echo $RESULT
}

function FullPilotTestsWithWrapper(){
  echo '==> [FullPilotTestsWithWrapper]'
  cd $PILOTINSTALLDIR 
  ./vm-pilot.sh 
}

#consume all messages from the queue, leaving it empty
function RabbitServerCleanup()
{
  python consumeFromQueue.py 
}

