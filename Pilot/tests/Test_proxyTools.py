from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import subprocess
import shlex
import sys
import os
import shutil
import unittest

############################
# python 2 -> 3 "hacks"
try:
    from Pilot.proxyTools import getVO, parseASN1
except ImportError:
    from proxyTools import getVO, parseASN1

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch


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

    @patch("Pilot.proxyTools.Popen")
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
        """Should raise an exception when Popen return code is !=0"""

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
        shutil.copy(basedir + "/certs/user/userkey.pem", basedir + "/certs/user/userkey400.pem")
        os.chmod(basedir + "/certs/user/userkey400.pem", 0o400)
        ret = self.createFakeProxy(
            basedir + "/certs/user/usercert.pem",
            basedir + "/certs/user/userkey400.pem",
            "fakeserver.cern.ch:15000",
            "fakevo",
            basedir + "/certs//host/hostcert.pem",
            basedir + "/certs/host/hostkey.pem",
            basedir + "/certs/ca",
            proxyFile,
        )
        os.remove(basedir + "/certs/user/userkey400.pem")
        return ret

    def createFakeProxy(self, usercert, userkey, serverURI, vo, hostcert, hostkey, CACertDir, proxyfile):
        """
        voms-proxy-fake --cert usercert.pem
                        --key userkey.pem
                        -rfc
                        -fqan "/fakevo/Role=user/Capability=NULL"
                        -uri fakeserver.cern.ch:15000
                        -voms fakevo
                        -hostcert hostcert.pem
                        -hostkey hostkey.pem
                        -certdir ca
        """
        opt = (
            '--cert %s --key %s -rfc -fqan "/fakevo/Role=user/Capability=NULL" -uri %s -voms %s -hostcert %s'
            "  -hostkey %s  -certdir %s -out %s"
            % (usercert, userkey, serverURI, vo, hostcert, hostkey, CACertDir, proxyfile)
        )
        proc = subprocess.Popen(
            shlex.split("voms-proxy-fake " + opt),
            bufsize=1,
            stdout=sys.stdout,
            stderr=sys.stderr,
            universal_newlines=True,
        )
        proc.communicate()
        return proc.returncode
