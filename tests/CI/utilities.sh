# utilities.sh
#
# utilities for running the pilot integration tests

function default(){

  if [ -z $JENKINS_SITE ]
  then
    JENKINS_SITE='DIRAC.Jenkins.ch'
  fi

  if [ -z $JENKINS_CE ]
  then
    JENKINS_CE='jenkins.cern.ch'
  fi

  if [ -z $JENKINS_QUEUE ]
  then
    JENKINS_QUEUE='jenkins-queue_not_important'
  fi
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


function prepareForPilot(){

  #get the pilot files from the Pilot
  for file in PilotLogger.py PilotLoggerTools.py dirac-install.py dirac-pilot.py pilotCommands.py pilotTools.py
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

}
