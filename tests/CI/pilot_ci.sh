#!/usr/bin/env bash
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
# WORKSPACE
#
# === a default directory structure is created:
# ~/TestCode
# ~/ClientInstallDIR
# ~/PilotInstallDIR

# you can try this out with:
#
# bash
# DEBUG=True
# WORKSPACE=$PWD
# mkdir $PWD/TestCode
# cd $PWD/TestCode
# mkdir Pilot
# cd Pilot
# cp -r ~/pyDevs/Pilot/* .  # change this...
# cd ../..
# source TestCode/Pilot/tests/CI/pilot_ci.sh
# fullPilot

# Def of environment variables:

if [ ! -z "${DEBUG:-}" ]
then
  echo '==> Running in DEBUG mode'
  DEBUG='-ddd'
else
  echo '==> Running in non-DEBUG mode'
fi

if [ ! -z "${WORKSPACE:-}" ]
then
  echo '==> We are in Jenkins I guess'
else
  WORKSPACE=$PWD
fi

pwd
echo -e "$WORKSPACE"
# Creating default structure
mkdir -p "$WORKSPACE/TestCode" # Where the test code resides
TESTCODE=$_
mkdir -p "$WORKSPACE/ClientInstallDIR" # Where client are installed
# shellcheck disable=SC2034
CLIENTINSTALLDIR=$_
mkdir -p "$WORKSPACE/PilotInstallDIR" # Where pilots are installed
PILOTINSTALLDIR=$_

# Sourcing utility file
# shellcheck source=tests/CI/utilities.sh
source "$TESTCODE/Pilot/tests/CI/utilities.sh"


# basically it just calls the pilot wrapper
# don't launch the JobAgent here
function PilotInstall(){
  echo '==> [PilotInstall]'

  default

  cwd=$PWD
  if ! cd "$PILOTINSTALLDIR"; then
    echo -e "ERROR: cannot change to $PILOTINSTALLDIR"
    exit 1
  fi

  #get the configuration file (from an VO extension, if it exists)
  pilot="Pilot"
  cp "$TESTCODE/$VO$pilot/tests/CI/pilot.json" .
  # and adapt it
  sed -i "s/VAR_JENKINS_SITE/$JENKINS_SITE/g" pilot.json
  sed -i "s/VAR_JENKINS_CE/$JENKINS_CE/g" pilot.json
  sed -i "s/VAR_JENKINS_QUEUE/$JENKINS_QUEUE/g" pilot.json
  # shellcheck disable=SC2154
  sed -i "s/VAR_DIRAC_VERSION/$projectVersion/g" pilot.json
  sed -i "s#VAR_CS#$CSURL#g" pilot.json
  sed -i "s#VAR_USERDN#$DIRACUSERDN#g" pilot.json


  prepareForPilot
  #installStompRequestsIfNecessary
  #preparePythonEnvironment
  python PilotLoggerTools.py PilotUUID
  python PilotLogger.py "Hello I am THE best pilot"

  # launch the pilot script
  pilotOptions=$pilot_options
  pilotOptions+=" -M 1 -S $DIRACSETUP -N $JENKINS_CE -Q $JENKINS_QUEUE -n $JENKINS_SITE --cert --certLocation=/home/dirac/certs"
  if [ "$VO" ]
  then
    pilotOptions+=" -l $VO -E $VO"
    pilotOptions+="Pilot"
  fi
  # shellcheck disable=SC2154
  if [ "$lcgVersion" ]
  then
    pilotOptions+=" -g $lcgVersion"
  fi
  # shellcheck disable=SC2154
  if [ "$modules" ]
  then
    pilotOptions+=" --modules=$modules"
  fi
  pilotOptions+=" --debug"

  echo -e "Running dirac-pilot.py $pilotOptions"
  if ! python dirac-pilot.py "$pilotOptions"; then
    echo 'ERROR: pilot script failed'
    exit 1
  fi

  if ! cd "$cwd"; then
    echo -e "ERROR: cannot change to $cwd"
    exit 1
  fi

  echo '==> [Done PilotInstall]'
}


function fullPilot(){
  echo '==> [fullPilot]'

  #first simply install via the pilot
  if ! PilotInstall; then
    echo "ERROR: pilot installation failed"
    exit 1
  fi

  #this should have been created, we source it so that we can continue
  # shellcheck source=/dev/null
  if ! source "$PILOTINSTALLDIR/bashrc"; then
    echo "ERROR: cannot source bashrc"
    exit 1
  fi

  echo -e "\n----PATH:$PATH\n----" | tr ":" "\n"
  echo -e "\n----LD_LIBRARY_PATH:$LD_LIBRARY_PATH\n----" | tr ":" "\n"
  echo -e "\n----DYLD_LIBRARY_PATH:$DYLD_LIBRARY_PATH\n----" | tr ":" "\n"
  echo -e "\n----PYTHONPATH:$PYTHONPATH\n----" | tr ":" "\n"

  echo -e '\n----python'
  python -V
  which python


  #Adding the LocalSE and the CPUTimeLeft, for the subsequent tests
  if [ "$PILOTCFG" ]
  then
    if ! dirac-configure -FDMH --UseServerCertificate -L "$DIRACSE" -O "$PILOTINSTALLDIR/$PILOTCFG" "$PILOTINSTALLDIR/$PILOTCFG" "$DEBUG"; then
      echo 'ERROR: cannot configure'
      exit 1
    fi
  else
    if ! dirac-configure -FDMH --UseServerCertificate -L "$DIRACSE" "$DEBUG"; then
      echo 'ERROR: cannot configure'
      exit 1
    fi
  fi

  #Configure for CPUTimeLeft and more
  if ! [ "$PILOTCFG" ]
  then
    if ! python "$TESTCODE/DIRAC/tests/Jenkins/dirac-cfg-update.py" -o /DIRAC/Security/UseServerCertificate=True "$DEBUG"; then
      echo "ERROR: cannot update the CFG"
      exit 1
    fi
  fi

  #Getting a user proxy, so that we can run jobs
  downloadProxy
  echo "==> Set not to use the server certificate for running the jobs"
  if [ "$PILOTCFG" ]
  then
    if ! dirac-configure -FDMH -o /DIRAC/Security/UseServerCertificate=False -O "$PILOTINSTALLDIR/$PILOTCFG" "$PILOTINSTALLDIR/$PILOTCFG" "$DEBUG"; then
      echo "ERROR: cannot run dirac-configure"
      exit 1
    fi
  else
    if ! dirac-configure -FDMH -o /DIRAC/Security/UseServerCertificate=False "$DEBUG"; then
      echo "ERROR: cannot run dirac-configure"
      exit 1
    fi
  fi

<<<<<<< HEAD
  echo '==> [Done fullPilot]'
}

=======
>>>>>>> Resolvig error
function installStompRequestsIfNecessary()
{
  echo '==> [installStompRequestsIfNecessary]'

  # shellcheck disable=SC2155
  local PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
  #checking if stomp is installed
  if ! python -c 'import stomp' > /dev/null 2>&1; then
      #checking if pip is installed
      #if ! type python -m pip > /dev/null 2>&1; then
          #type yum > /dev/null 2>&1 || { echo >&2 "yum installer is required. Aborting"; exit 1; }
          #yum -y install python-pip
      #fi
      mkdir myLocal
      export PYTHONUSERBASE=${PWD}/myLocal
      python -c 'import site' # crazy hack to setup sys.path with the local directories 
      # shellcheck disable=SC2155
      local USER_SITE_PACKAGE_BASE=$(python -m site --user-base)
      local PIP_LOC=$USER_SITE_PACKAGE_BASE/bin/pip
      echo "PIP_LOC: $PIP_LOC"
      if [ "$PYTHON_VERSION" = '2.6' ]; then
        curl https://bootstrap.pypa.io/2.6/get-pip.py -o get-pip.py
      else 
        curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
      fi
      python get-pip.py --user --upgrade
      echo "$PIP_LOC install --user 'stomp.py==4.1.11'"
      ${PIP_LOC} install --user 'stomp.py==4.1.11'
      ${PIP_LOC} install --user 'requests'
  fi
  #stomp should be installed now
  python -c 'import stomp' > /dev/null 2>&1 ||{ echo >&2 "stomp installation failure. Aborting"; exit 1; }
  #requests should be installed now
  python -c 'import requests' > /dev/null 2>&1 ||{ echo >&2 "requests installation failure. Aborting"; exit 1; }

  echo '==> [Done installStompRequestsIfNecessary]'
}

####################################################################################
# submitAndMatch
#
# This installs a DIRAC client, then use it to submit jobs to DIRAC.Jenkins.ch,
# then we run a pilot that should hopefully match those jobs

function submitAndMatch(){
  echo '==> [submitAndMatch]'

  # Here we submit the jobs (to DIRAC.Jenkins.ch)
  # This installs the DIRAC client
  if ! installDIRAC; then
    echo 'ERROR: failure installing the DIRAC client'
    exit 1
  fi

  # This submits the jobs
  if ! submitJob; then
    echo 'ERROR: failure submitting the jobs'
    exit 1
  fi

  # Then we run the full pilot, including the JobAgent, which should match the jobs we just submitted
  if ! cd "$PILOTINSTALLDIR"; then
    echo -e "ERROR: cannot change to $PILOTINSTALLDIR"
    exit 1
  fi
  prepareForPilot
  default

  if [ "$DIRACOSVER" ]
  then
    pilot_options=" --dirac-os --dirac-os-version=$DIRACOSVER"
    pilot_options+=' '
  fi

  if ! PilotInstall; then
    echo 'ERROR: dirac-pilot failure'
    exit 1
  fi

  echo '==> [Done submitAndMatch]'
}
