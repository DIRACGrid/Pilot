# utilities.sh
#
# utilities for running the pilot integration tests

# Sourcing DIRAC/tests utility file
source $TESTCODE/DIRAC/tests/Jenkins/utilities.sh



# function that override the default one in $TESTCODE/DIRAC/tests/Jenkins/utilities.sh
# 
function prepareForPilot(){

  #get the pilot files from the Pilot
  for file in PilotLogger.py PilotLoggerTools.py dirac-pilot.py pilotCommands.py pilotTools.py
  do
    cp $TESTCODE/Pilot/Pilot/${file} .
  done

  #get possible extensions
  if [ $VO ]
  then
    pilotFile="PilotCommands.py"
    pilot="Pilot"
    for file in $VO$pilotFile
    do
      cp $TESTCODE/$VO$pilot/$VO$pilot/${file} .
    done
  fi

  # get dirac-install.py file
  curl -L -O https://raw.githubusercontent.com/DIRACGrid/DIRAC/integration/Core/scripts/dirac-install.py
}


# function preparePythonEnvironment()
# {
#   cd $PILOTINSTALLDIR
#   USER_SITE_PACKAGE_BASE=$(python -m site --user-base)
#   wget https://bootstrap.pypa.io/get-pip.py && python get-pip.py --user --upgrade
#   INSTALL_COMMAND="$USER_SITE_PACKAGE_BASE/bin/pip install --upgrade --user -r $TESTCODE/Pilot/requirements.txt"
#   eval $INSTALL_COMMAND
# }

#consume all messages from the queue, leaving it empty
# function RabbitServerCleanup()
# {
#   cd $PILOTINSTALLDIR
#   python consumeFromQueue.py
# }
