#!/usr/bin/env bash

# utilities.sh
#
# utilities for running the pilot integration tests

# Sourcing DIRAC/tests utility file

# shellcheck source=../DIRAC/tests/Jenkins/utilities.sh
source "$TESTCODE/DIRAC/tests/Jenkins/utilities.sh"



# function that override the default one in $TESTCODE/DIRAC/tests/Jenkins/utilities.sh
# 
function prepareForPilot(){
  echo '==> [prepareForPilot]'

  #get the pilot files from the Pilot
  for file in PilotLogger.py PilotLoggerTools.py dirac-install.py dirac-pilot.py pilotCommands.py pilotTools.py MessageSender.py
  do
    cp "$TESTCODE/Pilot/Pilot/${file}" .
  done

  #get possible extensions
  if [ "$VO" ]
  then
    pilotFile="PilotCommands.py"
    pilot="Pilot"
    for file in $VO$pilotFile
    do
      cp "$TESTCODE/$VO$pilot/$VO$pilot/${file}" .
    done
  fi

  echo "==> [Done prepareForPilot]"
}


function preparePythonEnvironment()
{
  if ! cd "$PILOTINSTALLDIR"; then
   exit 1
  fi
  USER_SITE_PACKAGE_BASE=$(python -m site --user-base)
  wget https://bootstrap.pypa.io/get-pip.py && python get-pip.py --user --upgrade
  INSTALL_COMMAND="$USER_SITE_PACKAGE_BASE/bin/pip install --upgrade --user -r $TESTCODE/Pilot/requirements.txt"
  eval "$INSTALL_COMMAND"
}

#consume all messages from the queue, leaving it empty
# function RabbitServerCleanup()
# {
#   cd $PILOTINSTALLDIR
#   python consumeFromQueue.py
# }
