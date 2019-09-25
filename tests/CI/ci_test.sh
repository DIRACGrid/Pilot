#!/usr/bin/env bash

PILOTBRANCH=pilot_loggers

echo -e "**** Starting Pilot tests with PilotLogger ****\n"

echo -e "***' $(date -u) **** Getting the tests ****\n"

mkdir -p "$PWD/TestCode"
if ! cd "$PWD/TestCode"; then
  exit 1
fi

git clone https://github.com/wkrzemien/Pilot.git
if ! cd Pilot; then
  exit 1
fi
git checkout "$PILOTBRANCH"
pwd
if ! cd "../.."; then
  exit 1
fi
pwd

echo -e "*** $(date -u) **** Got the tests ****\n"

# shellcheck source=tests/CI/pilot_ci.sh
source "$TESTCODE/Pilot/tests/CI/pilot_ci.sh"
#<---- this file contains the tests logic

echo -e "*** $(date -u) **** Pilot INSTALLATION START ****\n"

prepareForPilot
preparePythonEnvironment
if ! cd "$PILOTINSTALLDIR"; then
  exit 1
fi
echo '==> [SimplePilotLogger ]'
RabbitServerCleanup #to assure that the queue is empty
python Test_simplePilotLogger.py
RabbitServerCleanup #to assure that the queue is empty
if ! cd "../"; then
  exit 1
fi
