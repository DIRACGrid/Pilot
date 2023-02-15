#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import os
import sys
import tempfile
import string
import random
import subprocess

try:
    from Pilot.pilotTools import CommandBase, PilotParams
except ImportError:
    from pilotTools import CommandBase, PilotParams

import unittest

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch


class TestPilotParams(unittest.TestCase):
    @patch("sys.argv")
    def test_pilotParamsInit(self, argvmock):
        argvmock.__getitem__.return_value = [
            "-z",
            "-d",
            "-g",
            "dummyURL",
            "-F",
            "tests/pilot.json",
        ]

        pp = PilotParams()

        argvmock.__getitem__.assert_called()
        self.assertEqual(argvmock.__getitem__.call_count, 2)  # 2 getopt calls
        self.assertTrue(pp.pilotLogging)
        self.assertEqual(pp.loggerURL, "dummyURL")
        self.assertTrue(pp.debugFlag)

    @patch.object(PilotParams, "_PilotParams__getSearchPaths")
    @patch("sys.argv")
    def test_pilotOptions(self, argvmock, mockPaths):
        # no -z, no -g when  the new JSON format in use.
        argvmock.__getitem__.return_value = [
            "-F",
            "tests/pilot.json",
        ]

        pp = PilotParams()
        vo = "gridpp"
        setup = "GridPP"
        paths = [
            "/Defaults/Pilot",
            "/%s/Pilot" % setup,
            "/%s/Defaults/Pilot" % vo,
            "/%s/%s/Pilot" % (vo, setup),
        ]
        mockPaths.return_value = paths

        mockPilotJSON = {
            "Defaults": {"Pilot": {"RemoteLogging": "False"}},
            "GridPP": {
                "Pilot": {
                    "Version": "8.0.5",
                    "Extensions": "None",
                    "CheckVersion": "False",
                    "pilotFileServer": "diractest.grid.hep.ph.ic.ac.uk:8443",
                    "pilotRepoBranch": "devel",
                }
            },
            "gridpp": {
                "GridPP": {
                    "Pilot": {
                        "GenericPilotGroup": "gridpp_pilot",
                        "GenericPilotDN": "/C=UK/O=eScience/OU=Imperial/L=Physics/CN=dirac-pilot-test.grid.hep.ph.ic.ac.uk",
                        "RemoteLogging": "True",
                        "RemoteLoggerURL": "https://diractest.grid.hep.ph.ic.ac.uk:8444/WorkloadManagement/TornadoPilotLogging",
                        "UploadSE": "UKI-LT2-IC-HEP-disk",
                        "UploadPath": "/gridpp/pilotlogs/",
                        "LoggingShifterName": "GridPPLogManager",
                    },
                }
            },
        }
        pp.pilotCFGFile = "tests/CI/pilot.json"  # any file really, just testing remote logging options.

        with patch.dict(pp.pilotJSON, mockPilotJSON, clear=True):
            res = pp.getPilotOptionsDict()
            self.assertEqual(
                res.get("RemoteLoggerURL"),
                "https://diractest.grid.hep.ph.ic.ac.uk:8444/WorkloadManagement/TornadoPilotLogging",
            )
            self.assertEqual(res.get("RemoteLogging"), "True")
            self.assertEqual(res.get("UploadPath"), "/gridpp/pilotlogs/")

        # delete a key from a higher priority dictionary and we are left with one with a lower priority:
        del mockPilotJSON["gridpp"]["GridPP"]["Pilot"]["RemoteLogging"]
        with patch.dict(pp.pilotJSON, mockPilotJSON, clear=True):
            res = pp.getPilotOptionsDict()
            self.assertEqual(res.get("RemoteLogging"), "False")


class TestCommandBase(unittest.TestCase):
    def setUp(self):
        # These temporary files, opened in a binary mode, will act as standard stream pipes for `Popen`
        self.stdout_mock = tempfile.NamedTemporaryFile(mode="rb+", delete=False)
        self.stderr_mock = tempfile.NamedTemporaryFile(mode="rb+", delete=False)

    def tearDown(self):
        # At the end of the test, we'll close and remove the created files
        self.stdout_mock.close()
        os.remove(self.stdout_mock.name)
        os.remove(self.stderr_mock.name)

    @patch(("sys.argv"))
    @patch("subprocess.Popen")
    def test_executeAndGetOutput(self, popenMock, argvmock):
        argvmock.__getitem__.return_value = [
            "-d",
            "-g",
            "dummyURL",
            "-F",
            "tests/pilot.json",
        ]

        for size in [1000, 1024, 1025, 2005]:
            random_str = "".join(random.choice(string.ascii_letters + "\n") for i in range(size))
            if sys.version_info.major == 3:
                random_bytes = random_str.encode("UTF-8")
                self.stdout_mock.write(random_bytes)
            else:
                self.stdout_mock.write(random_str)
            self.stdout_mock.seek(0)
            if sys.version_info.major == 3:
                self.stderr_mock.write("Errare humanum est!".encode("UTF-8"))
            else:
                self.stderr_mock.write("Errare humanum est!")
            self.stderr_mock.seek(0)
            pp = PilotParams()
            cBase = CommandBase(pp)
            popenMock.return_value.stdout = self.stdout_mock
            popenMock.return_value.stderr = self.stderr_mock
            outData = cBase.executeAndGetOutput("dummy")
            popenMock.assert_called()
            self.assertEqual(outData[1], random_str)
            self.stdout_mock.seek(0)
            self.stderr_mock.seek(0)
            self.stdout_mock.truncate()
            self.stderr_mock.truncate()


class TestSimplePilotLogger(unittest.TestCase):
    def test_SimplePilotLogger(self):
        uuid = "37356d94-15c6-11e6-a600-606c663dde16"


if __name__ == "__main__":
    unittest.main()
