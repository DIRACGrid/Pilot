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
            "tests/CI/pilot.json",
        ]

        pp = PilotParams()

        argvmock.__getitem__.assert_called()
        self.assertEqual(argvmock.__getitem__.call_count, 3)
        self.assertTrue(pp.pilotLogging)
        self.assertEqual(pp.loggerURL, "dummyURL")
        self.assertTrue(pp.debugFlag)


class TestCommandBase(unittest.TestCase):
    def setUp(self):
        # These temporary files, opened in text mode, will act as standard stream pipes for `Popen`
        if sys.version_info.major == 3:
            self.stdout_mock = tempfile.NamedTemporaryFile(mode="rb+", delete=False)
            self.stderr_mock = tempfile.NamedTemporaryFile(mode="rb+", delete=False)
        else:
            self.stdout_mock = tempfile.NamedTemporaryFile(mode="r+", delete=False)
            self.stderr_mock = tempfile.NamedTemporaryFile(mode="r+", delete=False)

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
            "tests/CI/pilot.json",
        ]

        for size in [1000, 1024, 1025, 2005]:
            random_str = "".join(
                random.choice(string.ascii_letters + "\n") for i in range(size)
            )
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
