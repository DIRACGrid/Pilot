from __future__ import absolute_import, division, print_function

import os
import sys
import string
import random
import subprocess

try:
    from Pilot.proxyTools import getVO, parseASN1
except ImportError:
    from proxyTools import getVO, parseASN1

import unittest

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch


class TestProxyTools(unittest.TestCase):
    def test_getVO(self):
        vo = "unknown"
        cert = "x509up_u53911"
        with open(cert, "rb") as fp:
            vo = getVO(fp.read())
        self.assertEqual(vo, "gridpp")

    @patch("Pilot.proxyTools.Popen")
    def test_getVOPopenFails(self, popenMock):
        """
        Check if an exception is raised when Popen return code is not 0.

        """
        popenMock.return_value.returncode = -1
        popenMock.return_value.communicate.return_value = ("output", "error")
        cert = "x509up_u53911"
        msg = "Error when invoking openssl X509"
        with open(cert, "rb") as fp:
            data = fp.read()

        with self.assertRaises(Exception) as exc:
            vo = getVO(data)

        self.assertEqual(str(exc.exception), msg)

        popenMock.reset_mock()
        # if an underlying command fails, the exception is propagated:
        msg = "command not found: openssl"
        popenMock.side_effect = OSError(msg)
        with self.assertRaises(OSError) as exc:
            res = getVO(data)
        self.assertEqual(str(exc.exception), msg)

    @patch("Pilot.proxyTools.Popen")
    def test_parseASN1Fails(self, popenMock):
        """ Should raise an exception when Popen return code is !=0 """

        popenMock.return_value.returncode = -1
        popenMock.return_value.communicate.return_value = ("output", "error")
        msg = "Error when invoking openssl asn1parse"

        with self.assertRaises(Exception) as exc:
            res = parseASN1("Anything")

        self.assertEqual(str(exc.exception), msg)

        popenMock.reset_mock()

        # if an underlying command fails, the exception is propagated:
        msg = "command not found: openssl"
        popenMock.side_effect = OSError(msg)
        with self.assertRaises(OSError) as exc:
            res = parseASN1("Anything")
        self.assertEqual(str(exc.exception), msg)



