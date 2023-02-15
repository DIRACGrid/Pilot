#!/usr/bin/env bash

# utilities.sh
#
# utilities for running the pilot integration tests

# Sourcing DIRAC/tests utility file

# shellcheck source=/dev/null
source "$TESTCODE/DIRAC/tests/Jenkins/utilities.sh"



# function that override the default one in $TESTCODE/DIRAC/tests/Jenkins/utilities.sh
# 
prepareForPilot(){
  echo '==> [prepareForPilot]'

  #get the pilot files from the Pilot
  for file in dirac-pilot.py pilotCommands.py pilotTools.py proxyTools.py
  do
    cp "$TESTCODE/Pilot/Pilot/${file}" .
  done

  #get possible extensions
  if [[ "$VO" ]]; then
    pilotFile="PilotCommands.py"
    pilot="Pilot"
    for file in $VO$pilotFile
    do
      cp "$TESTCODE/$VO$pilot/$VO$pilot/${file}" .
    done
  fi

  echo "==> [Done prepareForPilot]"
}

cleanPilot(){
  for file in dirac-pilot.py pilotCommands.py pilotTools.py pilot.cfg pilot.json
  do
    rm -f "${file}"
  done

  #get possible extensions
  if [[ "$VO" ]]; then
    pilotFile="PilotCommands.py"
    pilot="Pilot"
    for file in $VO$pilotFile
    do
      rm -f "${file}"
    done
  fi

}
