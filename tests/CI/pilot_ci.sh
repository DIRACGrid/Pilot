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

if [[ -n "${DEBUG:-}" ]]; then
  echo '==> Running in DEBUG mode'
  DEBUG='-ddd'
else
  echo '==> Running in non-DEBUG mode'
fi

if [[ -n "${WORKSPACE:-}" ]]; then
  echo '==> We are in Jenkins I guess'
else
  WORKSPACE=${PWD}
fi

pwd
echo -e "${WORKSPACE}"
# Creating default structure
mkdir -p "${WORKSPACE}/TestCode" # Where the test code resides
TESTCODE=$_
mkdir -p "${WORKSPACE}/ClientInstallDIR" # Where client are installed
# shellcheck disable=SC2034
CLIENTINSTALLDIR=$_
mkdir -p "${WORKSPACE}/PilotInstallDIR" # Where pilots are normally installed
PILOTINSTALLDIR=$_

# Sourcing utility file
# shellcheck source=tests/CI/utilities.sh
source "${TESTCODE}/Pilot/tests/CI/utilities.sh"


# Here the pilot is run in the current directory. This assumes that the pilot files are found locally.
# This installation will use a certificate for authN/authZ. Such certificate should have the GenericPilot role
PilotInstall(){
  echo '==> [PilotInstall]'

  default

  # get the configuration file (from an VO extension, if it exists)
  pilot="Pilot"
  cp "${TESTCODE}/${VO}${pilot}/tests/CI/pilot.json" .
  # and adapt it
  sed -i "s/VAR_JENKINS_SITE/${JENKINS_SITE}/g" pilot.json
  sed -i "s/VAR_JENKINS_CE/${JENKINS_CE}/g" pilot.json
  sed -i "s/VAR_JENKINS_QUEUE/${JENKINS_QUEUE}/g" pilot.json
  # shellcheck disable=SC2154
  sed -i "s/VAR_DIRAC_VERSION/${projectVersion}/g" pilot.json
  sed -i "s#VAR_CS#${CSURL}#g" pilot.json
  sed -i "s#VAR_USERDN#${DIRACUSERDN}#g" pilot.json

  #installStompRequestsIfNecessary
  #preparePythonEnvironment
  #python PilotLoggerTools.py PilotUUID
  #python PilotLogger.py "Hello I am THE best pilot"

  # launch the pilot script
  # shellcheck disable=SC2154
  pilotOptions="${pilot_options}"
  pilotOptions+=" -M 1 -S ${DIRACSETUP} -N ${JENKINS_CE} -Q ${JENKINS_QUEUE} -n ${JENKINS_SITE} --cert --certLocation=/home/dirac/certs"
  if [ "${VO}" ]
  then
    pilotOptions+=" -l ${VO} -E ${VO}"
    pilotOptions+="Pilot"
  fi
  # shellcheck disable=SC2154
  if [ "${wnVO}" ] # Bind the Worker Node to the VirtualOrganization
  then
    pilotOptions+=" --wnVO ${wnVO}"
  fi
  # shellcheck disable=SC2154
  if [[ "${modules}" ]]; then
    pilotOptions+=" --modules=""${modules}"
  fi
  pilotOptions+=" --debug"

  echo -e "Running dirac-pilot.py ${pilotOptions}"
  # shellcheck disable=SC2086
  if ! python dirac-pilot.py ${pilotOptions}; then
    echo 'ERROR: pilot script failed' >&2
    exit 1
  fi

  echo '==> [Done PilotInstall]'
}

# Here the pilot is installed in PILOTINSTALLDIR.
# This is usually done for preparing workflow tests
fullPilot(){
  echo '==> [fullPilot]'

  cwd=${PWD}

  if ! cd "${PILOTINSTALLDIR}"; then
    echo -e "ERROR: cannot change to ${PILOTINSTALLDIR}" >&2
    exit 1
  fi

  cleanPilot
  prepareForPilot

  #first simply install via the pilot
  if ! PilotInstall; then
    echo "ERROR: pilot installation failed" >&2
    exit 1
  fi

  if ! cd "${cwd}"; then
    echo -e "ERROR: cannot change to ${cwd}" >&2
    exit 1
  fi

  #this should have been created, we source it so that we can continue
  # shellcheck source=/dev/null
  if ! source "${PILOTINSTALLDIR}/bashrc"; then
    echo "WARN: cannot source bashrc, trying with diracosrc" >&2
    if ! source "${PILOTINSTALLDIR}/diracos/diracosrc"; then
      echo "ERROR: cannot source diracosrc" >&2
      exit 1
    fi
  fi

  echo -e "\n----PATH:${PATH}\n----" | tr ":" "\n"
  echo -e "\n----LD_LIBRARY_PATH:${LD_LIBRARY_PATH}\n----" | tr ":" "\n"
  echo -e "\n----DYLD_LIBRARY_PATH:${DYLD_LIBRARY_PATH}\n----" | tr ":" "\n"
  echo -e "\n----PYTHONPATH:$PYTHONPATH\n----" | tr ":" "\n"

  echo -e '\n----python'
  python -V
  command -v python


  #Adding the LocalSE and the CPUTimeLeft, for the subsequent tests
  if [ "${PILOTCFG}" ]
  then
    if ! dirac-configure -FDMH --UseServerCertificate -L "${DIRACSE}" -O "${PILOTINSTALLDIR}/${PILOTCFG}" "$PILOTINSTALLDIR/${PILOTCFG}" "${DEBUG}"; then
      echo 'ERROR: cannot configure' >&2
      exit 1
    fi
  else
    if ! dirac-configure -FDMH --UseServerCertificate -L "${DIRACSE}" "${DEBUG}"; then
      echo 'ERROR: cannot configure' >&2
      exit 1
    fi
  fi

  #Configure for CPUTimeLeft and more
  if ! [ "${PILOTCFG}" ]
  then
    if ! python "${TESTCODE}/DIRAC/tests/Jenkins/dirac-cfg-update.py" -o /DIRAC/Security/UseServerCertificate=True "${DEBUG}"; then
      echo "ERROR: cannot update the CFG" >&2
      exit 1
    fi
  fi

  #Getting a user proxy, so that we can run jobs
  downloadProxy
  echo "==> Set not to use the server certificate for running the jobs"
  if [ "${PILOTCFG}" ]
  then
    if ! dirac-configure -FDMH -o /DIRAC/Security/UseServerCertificate=False -O "$PILOTINSTALLDIR/${PILOTCFG}" "$PILOTINSTALLDIR/${PILOTCFG}" "${DEBUG}"; then
      echo "ERROR: cannot run dirac-configure" >&2
      exit 1
    fi
  else
    if ! dirac-configure -FDMH -o /DIRAC/Security/UseServerCertificate=False "${DEBUG}"; then
      echo "ERROR: cannot run dirac-configure" >&2
      exit 1
    fi
  fi

  echo '==> [Done fullPilot]'
}


installStompRequestsIfNecessary()
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
      if [ "${PYTHON_VERSION}" = '2.6' ]; then
        curl https://bootstrap.pypa.io/pip/2.6/get-pip.py -o get-pip.py
      else 
        curl https://bootstrap.pypa.io/pip/2.7/get-pip.py -o get-pip.py
      fi
      python get-pip.py --user --upgrade
      echo "${PIP_LOC} install --user 'stomp.py==4.1.11'"
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
# then we run a few pilots, with different Inner CE types, that should hopefully match those jobs

submitAndMatch(){
  echo '==> [submitAndMatch]'

  # Here we submit the jobs (to DIRAC.Jenkins.ch)
  # This installs the DIRAC client
  if ! installDIRAC; then
    echo 'ERROR: failure installing the DIRAC client' >&2
    exit 1
  fi

  # This submits the jobs
  if ! submitJob; then
    echo 'ERROR: failure submitting the jobs' >&2
    exit 1
  fi

  # FIXME: these tests should be run in parallel Jenkins jobs, through a pipeline.

  # list of CEs that will be tried out (see pilot.json, and CS, for more info)
  ces=(jenkins-full.cern.ch jenkins-mp-full.cern.ch jenkins-singularity-full.cern.ch jenkins-mp-pool-full.cern.ch jenkins-mp-pool-sudo-full.cern.ch jenkins-mp-pool-singularity-full.cern.ch)
  for ce in "${ces[@]}"; do
    # Then we run the full pilot, including the JobAgent, which should match the jobs we just submitted
    if ! mkdir "${PILOTINSTALLDIR}_${ce}"; then
      echo -e "ERROR: cannot create dir ${PILOTINSTALLDIR}_${ce}" >&2
      exit 1
    fi
    if ! cd "${PILOTINSTALLDIR}_${ce}"; then
      echo -e "ERROR: cannot change to ${PILOTINSTALLDIR}_${ce}" >&2
      exit 1
    fi
    cleanPilot
    prepareForPilot
    default

    JENKINS_CE="${ce}"

    if ! PilotInstall; then
      echo 'ERROR: dirac-pilot failure' >&2
      exit 1
    fi
  done

  echo '==> [Done submitAndMatch]'
}
