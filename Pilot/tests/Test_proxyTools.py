import os
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.getcwd() + "/Pilot")

from proxyTools import getVO, parseASN1


class TestProxyTools(unittest.TestCase):
    def test_getVO(self):
        vo = "unknown"
        cert = "x509_uFAKE"
        ret = self.__createFakeProxy(cert)
        self.assertEqual(ret, 0)
        with open(cert, "rb") as fp:
            vo = getVO(fp.read())
        os.remove(cert)
        self.assertEqual(vo, "fakevo")

    @patch("proxyTools.Popen")
    def test_getVOPopenFails(self, popenMock):
        """
        Check if an exception is raised when Popen return code is not 0.

        """
        popenMock.return_value.returncode = -1
        popenMock.return_value.communicate.return_value = ("output", "error")
        cert = "x509_uFAKE"
        ret = self.__createFakeProxy(cert)
        self.assertEqual(ret, 0)
        msg = "Error when invoking openssl X509"
        with open(cert, "rb") as fp:
            data = fp.read()
        os.remove(cert)
        with self.assertRaises(Exception) as exc:
            getVO(data)

        self.assertEqual(str(exc.exception), msg)

        popenMock.reset_mock()
        # if an underlying command fails, the exception is propagated:
        msg = "command not found: openssl"
        popenMock.side_effect = OSError(msg)
        with self.assertRaises(OSError) as exc:
            getVO(data)
        self.assertEqual(str(exc.exception), msg)

    @patch("proxyTools.Popen")
    def test_parseASN1Fails(self, popenMock):
        """Should raise an exception when Popen return code is !=0"""

        popenMock.return_value.returncode = -1
        popenMock.return_value.communicate.return_value = ("output", "error")
        msg = "Error when invoking openssl asn1parse"

        with self.assertRaises(Exception) as exc:
            parseASN1("Anything")

        self.assertEqual(str(exc.exception), msg)

        popenMock.reset_mock()

        # if an underlying command fails, the exception is propagated:
        msg = "command not found: openssl"
        popenMock.side_effect = OSError(msg)
        with self.assertRaises(OSError) as exc:
            parseASN1("Anything")
        self.assertEqual(str(exc.exception), msg)

    def test_createFakeProxy(self):
        """Just test if a proxy is created"""

        ret = self.__createFakeProxy("x509_uFAKE")
        self.assertEqual(ret, 0)
        os.remove("x509_uFAKE")

    def __createFakeProxy(self, proxyFile):
        """
        Create a fake proxy locally.
        """
        basedir = os.path.dirname(__file__)
        shutil.copy(basedir + "/certs/voms/proxy.pem", proxyFile)
        return 0

