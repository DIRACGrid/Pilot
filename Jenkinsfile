#!/usr/bin/env groovy

/*
This is customized pipeline for running on jenkins-dirac.web.cern.ch
*/


properties([parameters([string(name: 'projectVersion', defaultValue: '8.1.0a4', description: 'The DIRAC version to install. Use py2 or py3 syntax'),
                        string(name: 'Pilot_repo', defaultValue: 'DIRACGrid', description: 'The Pilot repo'),
                        string(name: 'Pilot_branch', defaultValue: 'devel', description: 'The Pilot branch'),
                        string(name: 'DIRAC_test_repo', defaultValue: 'DIRACGrid', description: 'The DIRAC repo to use for getting the test code'),
                        string(name: 'DIRAC_test_branch', defaultValue: 'integration', description: 'The DIRAC branch to use for getting the test code'),
                        string(name: 'JENKINS_CE', defaultValue: 'jenkins.cern.ch', description: 'The CE definition to use (of DIRAC.Jenkins.ch, see CS for others)'),
                        string(name: 'modules', defaultValue: '', description: 'to override what is installed, e.g. with https://github.com/$DIRAC_test_repo/DIRAC.git:::DIRAC:::$DIRAC_test_branch'),
                        string(name: 'pip_install_options', defaultValue: '', description: 'options to pip install (e.g. --index-url=https://lhcb-repository.web.cern.ch/repository/pypi/simple)'),
                        string(name: 'pilot_options', defaultValue: '', description: 'any pilot option, e.g. --pythonVersion=2'),
                        string(name: 'CSURL', defaultValue: 'https://lbcertifdirac70.cern.ch:9135/Configuration/Server', description: 'URL for CS'),
                        string(name: 'DIRACSETUP', defaultValue: 'DIRAC-Certification', description: 'DIRAC setup'),
                        string(name: 'pilotJSON', defaultValue: 'pilot_oldSchema.json', description: 'other option: pilot_newSchema.json'),
                        string(name: 'wnVO', defaultValue: 'dteam', description: 'other option: gridpp')
                       ])])


node('lhcbci-cernvm4-02') {
    // Clean workspace before doing anything
    deleteDir()

    withEnv([
        "PILOTCFG=pilot.cfg",
        "DIRACSE=CERN-SWTEST",
        "JENKINS_QUEUE=jenkins-queue_not_important",
        "JENKINS_SITE=DIRAC.Jenkins.ch",
        "DIRACUSERDN=/DC=ch/DC=cern/OU=Organic Units/OU=Users/CN=alboyer/CN=819281/CN=Alexandre Franck Boyer",
        "DIRACUSERROLE=dirac_user"]){

        stage('GET') {

            echo "Here getting the code"

            dir("$WORKSPACE/TestCode"){
                sh """
                    git clone https://github.com/${params.Pilot_repo}/Pilot.git
                    cd Pilot
                    git checkout ${params.Pilot_branch}
                    cd ..
                """
                sh """
                    git clone https://github.com/${params.DIRAC_test_repo}/DIRAC.git
                    cd DIRAC
                    git checkout ${params.DIRAC_test_branch}
                    cd ..
                """
                echo "Got the test code"
            }
            stash includes: 'TestCode/**', name: 'testcode'
        }
        stage('SourceAndInstall') {

            echo "Sourcing and installing"
            sh """
                source $WORKSPACE/TestCode/Pilot/tests/CI/pilot_ci.sh
                fullPilot
            """
            echo "**** Pilot INSTALLATION DONE ****"

            stash includes: 'PilotInstallDIR/**', name: 'installation'

        }
        stage('Test') {
            echo "Starting the tests"

            parallel(

                "Integration" : {
                    node('lhcbci-cernvm4-03') {

                        cleanWs()

                        unstash "installation"
                        unstash "testcode"

                        try {
                            dir(env.WORKSPACE+"/PilotInstallDIR"){
                                sh '''
                                    bash -c "DEBUG=True;\
                                    source bashrc;\
                                    source diracos/diracosrc;\
                                    source \$WORKSPACE/TestCode/Pilot/tests/CI/pilot_ci.sh;\
                                    downloadProxy;\
                                    python \$WORKSPACE/TestCode/DIRAC/tests/Workflow/Integration/Test_UserJobs.py pilot.cfg -o /DIRAC/Security/UseServerCertificate=no -ddd"
                                '''
                            }
                        } catch (e) {
                            // if any exception occurs, mark the build as failed
                            currentBuild.result = 'FAILURE'
                            throw e
                        } finally {
                            // perform workspace cleanup only if the build have passed
                            // if the build has failed, the workspace will be kept
                            cleanWs cleanWhenFailure: false
                        }
                    }
                },

                "Regression" : {
                    node('lhcbci-cernvm4-03') {

                        cleanWs()

                        unstash "installation"
                        unstash "testcode"

                        try {
                            dir(env.WORKSPACE+"/PilotInstallDIR"){
                                sh '''
                                    bash -c "DEBUG=True;\
                                    source bashrc;\
                                    source diracos/diracosrc;\
                                    source \$WORKSPACE/TestCode/Pilot/tests/CI/pilot_ci.sh;\
                                    downloadProxy;\
                                    python \$WORKSPACE/TestCode/DIRAC/tests/Workflow/Regression/Test_RegressionUserJobs.py pilot.cfg -o /DIRAC/Security/UseServerCertificate=no -ddd"
                                '''
                            }
                        } catch (e) {
                            // if any exception occurs, mark the build as failed
                            currentBuild.result = 'FAILURE'
                            throw e
                        } finally {
                            // perform workspace cleanup only if the build have passed
                            // if the build has failed, the workspace will be kept
                            cleanWs cleanWhenFailure: false
                        }
                    }
                },

            )
        }
    }
}

