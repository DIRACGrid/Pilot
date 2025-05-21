"""few functions for dealing with proxies and authentication"""

from __future__ import absolute_import, division, print_function

import json
import os
import time
import re
import ssl
import sys
from base64 import b16decode
from subprocess import PIPE, Popen

try:
    IsADirectoryError  # pylint: disable=used-before-assignment
except NameError:
    IsADirectoryError = IOError

try:
    from urllib.parse import urlencode
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
except ImportError:
    from urllib import urlencode

    from urllib2 import Request, urlopen, HTTPError

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
    """This class helps supporting multiple kinds of requests that require connections"""

    def __init__(self, url, caPath, pilotUUID, name="unknown"):
        self.name = name
        self.url = url
        self.caPath = caPath
        self.headers = {
            "User-Agent": "Dirac Pilot [Unknown ID]"
        }
        self.pilotUUID = pilotUUID
        # We assume we have only one context, so this variable could be shared to avoid opening n times a cert.
        # On the contrary, to avoid race conditions, we do avoid using "self.data" and "self.headers"
        self._context = None

        self._prepareRequest()

    def generateUserAgent(self):
        """To analyse the traffic, we can send a taylor-made User-Agent"""
        self.addHeader("User-Agent", "Dirac Pilot [%s]" % self.pilotUUID)

    def _prepareRequest(self):
        """As previously, loads the SSL certificates of the server (to avoid "unknown issuer")"""
        # Load the SSL context
        self._context = ssl.create_default_context()
        self._context.load_verify_locations(capath=self.caPath)
        
    def addHeader(self, key, value):
        """Add a header (key, value) into the request header"""
        self.headers[key] = value

    def executeRequest(self, raw_data, insecure=False, content_type="json"):
        """Execute a HTTP request with the data, headers, and the pre-defined data (SSL + auth)

        :param raw_data: Data to send
        :type raw_data: dict
        :param insecure: Deactivate proxy verification WARNING Debug ONLY
        :type insecure: bool
        :param content_type: Data format to send, either "json" or "x-www-form-urlencoded"
        :type content_type: str
        :return: Parsed JSON response
        :rtype: dict
        """
        if content_type == "json":
            data = json.dumps(raw_data).encode("utf-8")
            self.addHeader("Content-Type", "application/json")
            self.addHeader("Content-Length", str(len(data)))
        else:

            data = urlencode(raw_data)

            if content_type == "x-www-form-urlencoded":
                if sys.version_info.major == 3:
                    data = urlencode(raw_data).encode("utf-8")  # encode to bytes ! for python3
            
                self.addHeader("Content-Type", "application/x-www-form-urlencoded")
                self.addHeader("Content-Length", str(len(data)))
            elif content_type == "query":
                self.url = self.url + "?" + data 
                data = None  # No body
            else:
                raise ValueError("Invalid content_type. Use 'json' or 'x-www-form-urlencoded'.")


        request = Request(self.url, data=data, headers=self.headers, method="POST")

        ctx = self._context  # Save in case of an insecure request

        if insecure:
            # DEBUG ONLY
            # Overrides context
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE


        try:
            if sys.version_info.major == 3:
                # Python 3 code
                with urlopen(request, context=ctx) as res:
                    response_data = res.read().decode("utf-8")  # Decode response bytes
            else:
                # Python 2 code
                res = urlopen(request, context=ctx)
                try:
                    response_data = res.read()
                finally:
                    res.close()
        except HTTPError as e:
            raise RuntimeError("HTTPError : %s" % e.read().decode())

        try:
            return json.loads(response_data)  # Parse JSON response
        except ValueError:  # In Python 2, json.JSONDecodeError is a subclass of ValueError
            raise ValueError("Invalid JSON response: %s" % response_data)


class TokenBasedRequest(BaseRequest):
    """Connected Request with JWT support"""

    def __init__(self, url, caPath, jwtData, pilotUUID):
        super(TokenBasedRequest, self).__init__(url, caPath, pilotUUID, "TokenBasedConnection")
        self.jwtData = jwtData
        self.addJwtToHeader()
    
    def addJwtToHeader(self):
        # Adds the JWT in the HTTP request (in the Bearer field)
        self.headers["Authorization"] = "Bearer %s" % self.jwtData["access_token"]

    def executeRequest(self, raw_data, insecure=False, content_type="json"):
    
        return super(TokenBasedRequest, self).executeRequest(
            raw_data,
            insecure=insecure,
            content_type=content_type
        )

class X509BasedRequest(BaseRequest):
    """Connected Request with X509 support"""

    def __init__(self, url, caPath, certEnv, pilotUUID):
        super(X509BasedRequest, self).__init__(url, caPath, pilotUUID, "X509BasedConnection")

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

    def executeRequest(self, raw_data, insecure=False, content_type="json"):
        # Adds a flag if the passed cert is a Directory
        if self._hasExtraCredentials:
            raw_data["extraCredentials"] = '"hosts"'
        return super(X509BasedRequest, self).executeRequest(
            raw_data,
            insecure=insecure,
            content_type=content_type
        )


def refreshPilotToken(url, pilotUUID, jwt, jwt_lock):
    """
    Refresh the JWT token in a separate thread.

    :param str url: Server URL
    :param str pilotUUID: Pilot unique ID
    :param dict jwt: Shared dict with current JWT; updated in-place
    :param threading.Lock jwt_lock: Lock to safely update the jwt dict
    :return: None
    """

    # PRECONDITION: jwt must contain "refresh_token"
    if not jwt or "refresh_token" not in jwt:
        raise ValueError("To refresh a token, a pilot needs a JWT with refresh_token")

    # Get CA path from environment
    caPath = os.getenv("X509_CERT_DIR")

    # Create request object with required configuration
    config = TokenBasedRequest(
        url="%s/api/pilots/refresh-token" % url,
        caPath=caPath,
        pilotUUID=pilotUUID,
        jwtData=jwt
    )

    # Perform the request to refresh the token
    response = config.executeRequest(
        raw_data={
            "refresh_token": jwt["refresh_token"]
        },
        insecure=True,
    )

    # Ensure thread-safe update of the shared jwt dictionary
    jwt_lock.acquire()
    try:
        jwt.update(response)
    finally:
        jwt_lock.release()


def revokePilotToken(url, pilotUUID, jwt, clientID):
    """
    Refresh the JWT token in a separate thread.

    :param str url: Server URL
    :param str pilotUUID: Pilot unique ID
    :param str clientID: ClientID used to revoke tokens 
    :param dict jwt: Shared dict with current JWT; 
    :return: None
    """

    # PRECONDITION: jwt must contain "refresh_token"
    if not jwt or "refresh_token" not in jwt:
        raise ValueError("To refresh a token, a pilot needs a JWT with refresh_token")

    # Get CA path from environment
    caPath = os.getenv("X509_CERT_DIR")

    # Create request object with required configuration
    config = BaseRequest(
        url="%s/api/auth/revoke" % url,
        caPath=caPath,
        pilotUUID=pilotUUID
    )

    # Prepare refresh token payload
    payload = {
        "refresh_token": jwt["refresh_token"],
        "client_id": clientID 
    }

    # Perform the request to revoke the token
    _response = config.executeRequest(
        raw_data=payload,
        insecure=True,
        content_type="query"
    )

# === Token refresher thread function ===
def refreshTokenLoop(url, pilotUUID, jwt, jwt_lock, logger, interval=600):
    """
    Periodically refresh the pilot JWT token.

    :param str url: DiracX server URL
    :param str pilotUUID: Pilot UUID
    :param dict jwt: Shared JWT dictionary
    :param threading.Lock jwt_lock: Lock to safely update JWT
    :param Logger logger: Logger to debug 
    :param int interval: Sleep time between refreshes in seconds
    :return: None
    """
    while True:
        time.sleep(interval)

        try:
            refreshPilotToken(url, pilotUUID, jwt, jwt_lock)

            logger.info("Token refreshed.")
        except Exception as e:
            logger.error("Token refresh failed: %s\n" % str(e))
            continue
