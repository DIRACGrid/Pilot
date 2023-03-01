""" Test class for Pilot
"""

from __future__ import absolute_import, division, print_function

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

# imports
import unittest
import json
import stat
import sys
import os
import shutil

from Pilot.pilotTools import PilotParams
from Pilot.pilotCommands import CheckWorkerNode, ConfigureSite, NagiosProbes


class PilotTestCase(unittest.TestCase):
    """Base class for the Agents test cases"""

    def setUp(self):
        # Define a local file for test, and all the necessary parameters
        with open("pilot.json", "w") as fp:
            json.dump(
                {
                    "Setups": {
                        "TestSetup": {
                            "Commands": {"cetype1": "x,y, z", "cetype2": ["d", "f"]},
                            "CommandExtensions": "TestExtension1,TestExtension2",
                            "NagiosProbes": "Nagios1,Nagios2",
                            "NagiosPutURL": "https://127.0.0.2/",
                            "Version": "v1r1, v2r2",
                        }
                    },
                    "CEs": {"grid1.example.com": {"GridCEType": "cetype1", "Site": "site.example.com"}},
                    "DefaultSetup": "TestSetup",
                },
                fp,
            )

    def tearDown(self):
        for fileProd in [
            "pilot.json",
            "Nagios1",
            "Nagios2",
            "PilotAgentUUID",
            "dev.tgz",
            "pilot.out",
            "123.txt",
            "testing.tgz",
        ]:
            try:
                os.remove(fileProd)
            except OSError:
                pass
            try:
                shutil.rmtree("ReplacementCode")
            except OSError:
                pass


class CommandsTestCase(PilotTestCase):
    """Test case for each pilot command"""

    def test_InitJSON(self):
        """Test the pilot.json and command line parsing"""
        sys.argv[1:] = ["--Name", "grid1.example.com", "--commandOptions", "a=1,b=2", "-Z", "c=3"]
        pp = PilotParams()

        self.assertEqual(pp.commands, ["x", "y", "z"])
        self.assertEqual(pp.commandExtensions, ["TestExtension1", "TestExtension2"])

        self.assertEqual(pp.commandOptions["a"], "1")
        self.assertEqual(pp.commandOptions["b"], "2")
        self.assertEqual(pp.commandOptions["c"], "3")

        sys.argv[1:] = [
            "--Name",
            "grid1.example.com",
            "--commandOptions",
            "a = 1,  b=2",
            "-Z",
            " c=3",
        ]  # just some spaces
        pp = PilotParams()

        self.assertEqual(pp.commandOptions["a"], "1")
        self.assertEqual(pp.commandOptions["b"], "2")
        self.assertEqual(pp.commandOptions["c"], "3")

        sys.argv[1:] = ["--Name", "grid1.example.com", "--commandOptions=a = 1,  b=2", "-Z", " c=3"]  # spaces and '=''
        pp = PilotParams()

        self.assertEqual(pp.commandOptions["a"], "1")
        self.assertEqual(pp.commandOptions["b"], "2")
        self.assertEqual(pp.commandOptions["c"], "3")

    def test_CheckWorkerNode(self):
        """Test CheckWorkerNode command"""
        pp = PilotParams()
        cwn = CheckWorkerNode(pp)
        self.assertEqual(cwn.execute(), None)

    def test_ConfigureSite(self):
        """Test ConfigureSite command"""
        pp = PilotParams()
        pp.configureScript = "echo"
        cs = ConfigureSite(pp)
        self.assertEqual(cs.execute(), None)

    def test_NagiosProbes(self):
        """Test NagiosProbes command"""
        pp = PilotParams()
        nagios = NagiosProbes(pp)

        with open("Nagios1", "w") as fp:
            fp.write("#!/bin/sh\necho 123\n")

        os.chmod("Nagios1", stat.S_IRWXU)

        with open("Nagios2", "w") as fp:
            fp.write("#!/bin/sh\necho 567\n")

        os.chmod("Nagios2", stat.S_IRWXU)

        nagios.execute()

        self.assertEqual(nagios.nagiosProbes, ["Nagios1", "Nagios2"])
        self.assertEqual(nagios.nagiosPutURL, "https://127.0.0.2/")


#############################################################################
# Test Suite run
#############################################################################


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PilotTestCase)
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(CommandsTestCase))
    testResult = unittest.TextTestRunner(verbosity=2).run(suite)

# EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#EOF#
