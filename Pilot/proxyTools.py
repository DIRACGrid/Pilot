"""few functions for dealing with proxies and authentication"""

from __future__ import absolute_import, division, print_function

import json
import os
import re
import ssl
import sys
from base64 import b16decode
from subprocess import PIPE, Popen

try:
    IsADirectoryError  # pylint: disable=used-before-assignment
except NameError:
    IsADirectoryError = OSError

try:
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except ImportError:
    from urllib import urlencode

    from urllib2 import urlopen


VOMS_FQANS_OID = b"1.3.6.1.4.1.8005.100.100.4"
VOMS_EXTENSION_OID = b"1.3.6.1.4.1.8005.100.100.5"

RE_OPENSSL_ANS1_FORMAT = re.compile(br"^\s*\d+:d=(\d+)\s+hl=")


def parseASN1(data):
    cmd = ["openssl", "asn1parse", "-inform", "der"]
    proc = Popen(cmd, stdin=PIPE, stdout=PIPE)
    out, _ = proc.communicate(data)
    if proc.returncode != 0:
        raise Exception("Error when invoking openssl asn1parse")
    return out.split(b"\n")


def findExtension(oid, lines):
    for i, line in enumerate(lines):
        if oid in line:
            return i


def getVO(proxy_data):
    """Fetches the VO in a chain certificate

    :param proxy_data: Bytes for the proxy chain
    :type proxy_data: bytes
    :return: A VO
    :rtype: str
    """

    chain = re.findall(br"-----BEGIN CERTIFICATE-----\n.+?\n-----END CERTIFICATE-----", proxy_data, flags=re.DOTALL)
    for cert in chain:
        proc = Popen(["openssl", "x509", "-outform", "der"], stdin=PIPE, stdout=PIPE)
        out, _ = proc.communicate(cert)
        if proc.returncode != 0:
            raise Exception("Error when invoking openssl X509")
        cert_info = parseASN1(out)
        # Look for the VOMS extension
        idx_voms_line = findExtension(VOMS_EXTENSION_OID, cert_info)
        if idx_voms_line is None:
            continue
        voms_extension = parseASN1(b16decode(cert_info[idx_voms_line + 1].split(b":")[-1]))
        # Look for the attribute names
        idx_fqans = findExtension(VOMS_FQANS_OID, voms_extension)
        (initial_depth,) = map(int, RE_OPENSSL_ANS1_FORMAT.match(voms_extension[idx_fqans - 1]).groups())
        for line in voms_extension[idx_fqans:]:
            (depth,) = map(int, RE_OPENSSL_ANS1_FORMAT.match(line).groups())
            if depth <= initial_depth:
                break
            # Look for a role, if it exists the VO is the first element
            match = re.search(br"OCTET STRING\s+:/([a-zA-Z0-9]+)/Role=", line)
            if match:
                return match.groups()[0].decode()
    raise NotImplementedError("Something went very wrong")


class BaseRequest(object):
    """This class helps supporting multiple kinds of requests that requires connections"""

    def __init__(self, url, caPath, name="unknown"):
        self.name = name
        self.url = url
        self.caPath = caPath
        self.headers = {
            "User-Agent": "Dirac Pilot [Unknown ID]"
        }
        # We assume we have only one context, so this variable could be shared to avoid opening n times a cert.
        # On the contrary, to avoid race conditions, we do avoid using "self.data" and "self.headers"
        self._context = None

        self._prepareRequest()

    def generateUserAgent(self, pilotUUID):
        """To analyse the traffic, we can send a taylor-made User-Agent

        :param pilotUUID: Unique ID of the Pilot
        :type pilotUUID: str
        """
        self.headers["User-Agent"] = "Dirac Pilot [%s]" % pilotUUID

    def _prepareRequest(self):
        """As previously, loads the SSL certificates of the server (to avoid "unknown issuer")"""
        # Load the SSL context
        self._context = ssl.create_default_context()
        self._context.load_verify_locations(capath=self.caPath)
        
    def addHeader(self, key, value):
        """Add a header (key, value) into the request header"""
        self.headers[key] = value

    def executeRequest(self, raw_data, insecure=False):
        """Execute a HTTP request with the data, headers, and the pre-defined data (SSL + auth)

        :param raw_data: Data to send
        :type raw_data: dict
        :param insecure: Deactivate proxy verification /!\ Debug ONLY
        :type insecure: bool
        :return: Parsed JSON response
        :rtype: dict
        """    
        if sys.version_info[0] == 3:
            data = urlencode(raw_data).encode("utf-8")  # encode to bytes ! for python3
        else:
            # Python2
            data = urlencode(raw_data)

        request = Request(self.url, data=data, headers=self.headers)

        ctx = self._context  # Save in case of an insecure request

        if insecure:
            # DEBUG ONLY
            # Overrides context
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        with urlopen(request, context=ctx) as res:
            response_data = res.read().decode("utf-8")  # Decode response bytes
            try:
                return json.loads(response_data)  # Parse JSON response
            except json.JSONDecodeError:
                raise Exception("Invalid JSON response: %s" % response_data)


class TokenBasedRequest(BaseRequest):
    """Connected Request with JWT support"""

    def __init__(self, url, caPath, jwtData):
        super(TokenBasedRequest, self).__init__(url, caPath, "TokenBasedConnection")

        self.jwtData = jwtData
    
    def addJwtToHeader(self):
        # Adds the JWT in the HTTP request (in the Bearer field)
        self.headers["Authorization"] = "Bearer: %s" % self.jwtData


class X509BasedRequest(BaseRequest):
    """Connected Request with X509 support"""

    def __init__(self, url, caPath, certEnv):
        super(X509BasedRequest, self).__init__(url, caPath, "X509BasedConnection")

        self.certEnv = certEnv
        self._hasExtraCredentials = False

        # Load X509 once
        try:
            self._context.load_cert_chain(self.certEnv)
        except IsADirectoryError:  # assuming it'a dir containing cert and key
            self._context.load_cert_chain(
                os.path.join(self.certEnv, "hostcert.pem"), os.path.join(self.certEnv, "hostkey.pem")
            )
            self._hasExtraCredentials = True

    def executeRequest(self, raw_data):
        # Adds a flag if the passed cert is a Directory
        if self._hasExtraCredentials:
            raw_data["extraCredentials"] = '"hosts"'
        return super(X509BasedRequest, self).executeRequest(raw_data)
