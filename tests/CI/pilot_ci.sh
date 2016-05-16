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

function prepareForPilot(){
	echo '==> [prepareForPilot]'

        PILOT_SCRIPTS_PATH=$TESTCODE/Pilot/Pilot 
        PILOT_LOGGER_PATH=$TESTCODE/Pilot/PilotLogger 
        PILOT_CI_PATH=$TESTCODE/Pilot/tests/CI
	#get the necessary scripts
	cp $PILOT_SCRIPTS_PATH/dirac-pilot.py $PILOTINSTALLDIR/
	cp $PILOT_SCRIPTS_PATH/pilotTools.py $PILOTINSTALLDIR/
	cp $PILOT_SCRIPTS_PATH/pilotCommands.py $PILOTINSTALLDIR/
        cp $PILOT_LOGGER_PATH/PilotLogger.py $PILOTINSTALLDIR/
        cp $PILOT_LOGGER_PATH/PilotLoggerTools.py $PILOTINSTALLDIR/
        cp $PILOT_CI_PATH/PilotLoggerTest.cfg $PILOTINSTALLDIR/PilotLogger.cfg
        cp $PILOT_CI_PATH/consumeFromQueue.py $PILOTINSTALLDIR
        cp $PILOT_CI_PATH/Test_simplePilotLogger.py $PILOTINSTALLDIR
        cp -r certificates $PILOTINSTALLDIR
        cp $TESTCODE/Pilot/requirements.txt $PILOTINSTALLDIR
}

function PreparePythonEnvironment()
{
  cd $PILOTINSTALLDIR 
  if [ "$HOSTNAME" = lbvobox49.cern.ch ]; then
    virtualenv $PILOTINSTALLDIR/testEnv
    source $PILOTINSTALLDIR/testEnv/bin/activate
    pip install -r $TESTCODE/Pilot/requirements.txt;
  else
    echo -e '***' $(date -u) "sourcing virtualenvwrapper.sh ****"
    . /opt/rh/python27/enable
    source /opt/rh/python27/root/usr/bin/virtualenvwrapper.sh
    mkvirtualenv testEnv
    workon testEnv
    pip install --upgrade setuptools;
    pip install -r $TestCode/Pilot/requirements.txt;
  fi
}
#consume all messages from the queue, leaving it empty
function RabbitServerCleanup()
{
  cd $PILOTINSTALLDIR 
  python consumeFromQueue.py 
}
