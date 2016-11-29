#!/bin/bash
#-------------------------------------------------------------------------------
# pilot_ci
#
# Several functions used for Jenkins style jobs
# They may also work on other CI systems
#
# wojciech.krzemien@ncbj.gov.pl and fstagni@cern.ch
# 09/05/2016
#-------------------------------------------------------------------------------

# A CI job needs:
#
# === environment variables (minimum set):
# DEBUG
# WORKSPACE
#
# === a default directory structure is created:
# ~/TestCode
# ~/ServerInstallDIR
# ~/PilotInstallDIR

# you can try this out with:
#
# bash
# DEBUG=True
# WORKSPACE=$PWD
# PILOT_FILES='file:///home/toffo/pyDevs/Pilot/Pilot' #Change this!
# JENKINS_CE='jenkins.cern.ch'
# JENKINS_QUEUE='jenkins-queue_not_important'
# mkdir $PWD/TestCode
# cd $PWD/TestCode
# mkdir Pilot
# cd Pilot
# cp -r ~/pyDevs/Pilot/* .
# cd ../..
# source TestCode/Pilot/tests/CI/pilot_ci.sh
# fullPilot

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

echo `pwd`
echo $WORKSPACE
# Creating default structure
mkdir -p $WORKSPACE/TestCode # Where the test code resides
TESTCODE=$_
mkdir -p $WORKSPACE/ServerInstallDIR # Where servers are installed
SERVERINSTALLDIR=$_
mkdir -p $WORKSPACE/PilotInstallDIR # Where pilots are installed
PILOTINSTALLDIR=$_

# Sourcing utility file
source $TESTCODE/Pilot/tests/CI/utilities.sh


function PilotInstall(){
  # basically it just calls the pilot wrapper

  default

  #Don't launch the JobAgent here
  cwd=$PWD
  cd $PILOTINSTALLDIR
  if [ $? -ne 0 ]
  then
    echo 'ERROR: cannot change to ' $PILOTINSTALLDIR
    return
  fi

  wget https://raw.githubusercontent.com/fstagni/Pilot/integrationTest/Pilot/pilot_wrapper.sh
  # wget https://raw.githubusercontent.com/DIRACGrid/Pilot/master/Pilot/pilot_wrapper.sh
  chmod +x pilot_wrapper.sh
  ./pilot_wrapper.sh $PILOT_FILES $JENKINS_CE $JENKINS_QUEUE
  if [ $? -ne 0 ]
  then
    echo 'ERROR: pilot script failed'
    return
  fi

  cd $cwd
  if [ $? -ne 0 ]
  then
    echo 'ERROR: cannot change to ' $cwd
    return
  fi
}


function fullPilot(){

  #first simply install via the pilot
  PilotInstall

  #this should have been created, we source it so that we can continue
  source $PILOTINSTALLDIR/bashrc
  if [ $? -ne 0 ]
  then
    echo 'ERROR: cannot source bashrc'
    return
  fi

  #Adding the LocalSE and the CPUTimeLeft, for the subsequent tests
  dirac-configure -FDMH --UseServerCertificate -L $DIRACSE $DEBUG
  if [ $? -ne 0 ]
  then
    echo 'ERROR: cannot configure'
    return
  fi

  #Configure for CPUTimeLeft and more
  python $TESTCODE/DIRAC/tests/Jenkins/dirac-cfg-update.py -o /DIRAC/Security/UseServerCertificate=True $DEBUG
  if [ $? -ne 0 ]
  then
    echo 'ERROR: cannot update the CFG'
    return
  fi

  #Getting a user proxy, so that we can run jobs
  downloadProxy
  #Set not to use the server certificate for running the jobs
  dirac-configure -FDMH -o /DIRAC/Security/UseServerCertificate=False $DEBUG
  if [ $? -ne 0 ]
  then
    echo 'ERROR: cannot run dirac-configure'
    return
  fi
}
