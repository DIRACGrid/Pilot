#!/bin/sh
#
# Runs as dirac. Sets up to run dirac-pilot.py
#

date --utc +"%Y-%m-%d %H:%M:%S %Z vm-pilot Start vm-pilot"

#checking if stomp is installed
if ! python -c 'import stomp' > /dev/null 2>&1; then
    #checking if pip is installed
    if ! type pip > /dev/null 2>&1; then
        type yum > /dev/null 2>&1 || { echo >&2 "yum installer is required. Aborting"; exit 1; }
        yum -y install python-pip
    fi
    pip install --user 'stomp.py=4.1.11'
fi
#stomp should be installed now
python -c 'import stomp' > /dev/null 2>&1 ||{ echo >&2 "stomp installation failure. Aborting"; exit 1; }

for i in "$@"
do
case $i in
    --dirac-site=*)
    DIRAC_SITE="${i#*=}"
    ;;
    --lhcb-setup=*)
    LHCBDIRAC_SETUP=`echo "${i#*=}" | sed 's/#.*$//'`
    ;;
    --ce-name=*)
    CE_NAME="${i#*=}"
    ;;
    --vm-uuid=*)
    VM_UUID="${i#*=}"
    ;;
    --vmtype=*)
    VMTYPE="${i#*=}"
    ;;
    *)
    # unknown option
    ;;
esac
done


# Default if not given explicitly
LHCBDIRAC_SETUP=${LHCBDIRAC_SETUP:-LHCb-Production}

# JOB_ID is used by when reporting LocalJobID by DIRAC watchdog
export JOB_ID="$CE_NAME:$VMTYPE:$VM_UUID"

# We might be running from cvmfs or from /var/spool/checkout
export CONTEXTDIR=`readlink -f \`dirname $0\``

export TMPDIR=/scratch/
export EDG_WL_SCRATCH=$TMPDIR

# NOT NEEDED WITH PILOT 2.0?
# Export host cert/key pair as proxy so will be found by dirac-agent
#export X509_CERT_DIR=/cvmfs/grid.cern.ch/etc/grid-security/certificates
#export X509_VOMS_DIR=/cvmfs/grid.cern.ch/etc/grid-security/vomsdir

# Still needed in 2.0 for glexecComputingElement
export X509_USER_PROXY=/scratch/dirac/etc/grid-security/hostkey.pem

# Needed to find software area
export VO_LHCB_SW_DIR=/cvmfs/lhcb.cern.ch

# So these NFS mounted directories can be found
export MACHINEFEATURES=/etc/machinefeatures
export JOBFEATURES=/etc/jobfeatures

# This is just for our glexec alternative that uses sudo
export GLITE_LOCATION=/opt/glite

# Clear it to avoid problems ( be careful if there is more than one agent ! )
rm -rf /tmp/area/*

# URLs where to get scripts
DIRAC_INSTALL='https://raw.githubusercontent.com/DIRACGrid/DIRAC/raw/integration/Core/scripts/dirac-install.py'
DIRAC_PILOT='https://raw.githubusercontent.com/DIRACGrid/DIRAC/integration/WorkloadManagementSystem/PilotAgent/dirac-pilot.py'
DIRAC_PILOT_TOOLS='https://raw.githubusercontent.com/DIRACGrid/DIRAC/integration/WorkloadManagementSystem/PilotAgent/pilotTools.py'
DIRAC_PILOT_COMMANDS='https://raw.githubusercontent.com/DIRACGrid/DIRAC/integration/WorkloadManagementSystem/PilotAgent/pilotCommands.py'
LHCbDIRAC_PILOT_COMMANDS='http://svn.cern.ch/guest/dirac/LHCbDIRAC/trunk/LHCbDIRAC/WorkloadManagementSystem/PilotAgent/LHCbPilotCommands.py'

#PILOT_LOGGER='Pilot/PilotLogger/PilotLogger.py' 
#PILOT_LOGGER_TOOLS='Pilot/PilotLogger/PilotLoggerTools.py' 

#wget --no-check-certificate -O PilotLoggerTools.py $PILOT_LOGGER_TOOLS
#wget --no-check-certificate -O PilotLogger.py $PILOT_LOGGER

python PilotLoggerTools.py PilotAgentUUID
python PilotLogger.py "Hello I am THE best pilot: $LHCBDIRAC_SETUP, $CE_NAME, $DIRAC_SITE" 
python PilotLogger.py "Getting DIRAC Pilot 2.0 code from lhcbproject for now..."

wget --no-check-certificate -O dirac-install.py $DIRAC_INSTALL
wget --no-check-certificate -O dirac-pilot.py $DIRAC_PILOT
wget --no-check-certificate -O pilotTools.py $DIRAC_PILOT_TOOLS
wget --no-check-certificate -O pilotCommands.py $DIRAC_PILOT_COMMANDS
wget --no-check-certificate -O LHCbPilotCommands.py $LHCbDIRAC_PILOT_COMMANDS


# Included on the dirac-agent command line by the fixed pilotCommands.VM.py
#echo '-o CEType=glexec'		   > CEType-glexec.agent.cfg
#echo '-o StopAfterFailedMatches=0' > StopAfterFailedMatches0.agent.cfg

#run the dirac-pilot script, only for installing, do not run the JobAgent here
python dirac-pilot.py \
 --debug \
 --setup $LHCBDIRAC_SETUP \
 --project LHCb \
 -o '/LocalSite/SubmitPool=Test' \
 --configurationServer dips://lhcb-conf-dirac.cern.ch:9135/Configuration/Server \
 --Name "$CE_NAME" \
 --MaxCycles 1 \
 -o '/Systems/WorkloadManagement/Certification/Agents/JobAgent/StopAfterFailedMatches=0' \
 -o '/Systems/WorkloadManagement/Certification/Agents/JobAgent/CEType=glexec' \
 -o '/Systems/WorkloadManagement/Production/Agents/JobAgent/StopAfterFailedMatches=0' \
 -o '/Systems/WorkloadManagement/Production/Agents/JobAgent/CEType=glexec' \
 --name "$DIRAC_SITE" \
 --cert \
 --certLocation=/home/krzemien/etc/grid-security \
 --commandExtensions LHCbPilot \
 --commands LHCbGetPilotVersion,CheckWorkerNode,LHCbInstallDIRAC,LHCbConfigureBasics,LHCbConfigureSite,LHCbConfigureArchitecture,LHCbConfigureCPURequirements,LaunchAgent
