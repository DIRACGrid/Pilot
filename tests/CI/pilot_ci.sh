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


# basically it just calls the pilot wrapper
# don't launch the JobAgent here
function PilotInstall(){

  default

  cwd=$PWD
  cd $PILOTINSTALLDIR
  if [ $? -ne 0 ]
  then
    echo 'ERROR: cannot change to ' $PILOTINSTALLDIR
    return
  fi

  #get the configuration file, and adapt it
  cp $TESTCODE/Pilot/tests/CI/pilot.json .
  sed -i s/VAR_JENKINS_SITE/$JENKINS_SITE/g pilot.json
  sed -i s/VAR_JENKINS_CE/$JENKINS_CE/g pilot.json
  sed -i s/VAR_JENKINS_QUEUE/$JENKINS_QUEUE/g pilot.json
  sed -i s/VAR_DIRAC_VERSION/$projectVersion/g pilot.json
  sed -i s/VAR_CS/$CSURL/g pilot.json
  sed -i s/VAR_USERDN/$DIRACUSERDN/g pilot.json

  #get the pilot files
  for file in PilotLogger.py PilotLoggerTools.py PilotTools.py dirac-install.py dirac-pilot.py pilotCommands.py pilotTools.py
  do
    cp $TESTCODE/Pilot/Pilot/${file} .
  done

  # launch the pilot script
  python dirac-pilot.py  -M 1 -S $DIRACSETUP -N $JENKINS_CE -Q $JENKINS_QUEUE -n $JENKINS_SITE --cert --certLocation=/home/dirac/certs -ddd
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
