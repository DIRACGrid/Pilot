"""few functions for dealing with proxies and authentication"""

from __future__ import absolute_import, division, print_function

import json
import os
import time
import re
import ssl
import sys
from base64 import b16decode, b64decode
from subprocess import PIPE, Popen
from random import randint

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
    from urllib2 import HTTPError, Request, urlopen

VOMS_FQANS_OID = b"1.3.6.1.4.1.8005.100.100.4"
VOMS_EXTENSION_OID = b"1.3.6.1.4.1.8005.100.100.5"

RE_OPENSSL_ANS1_FORMAT = re.compile(br"^\s*\d+:d=(\d+)\s+hl=")

MAX_REQUEST_RETRIES = 10 # If a request failed (503 error), we retry
MAX_TIME_BETWEEN_TRIES = 20 # 20 seconds max between each request

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

def extract_diracx_payload(proxy_data):
    """Extracts and decodes the DIRACX section from proxy data

    :param proxy_data: The full proxy content (str or bytes)
    :return: Parsed DIRACX payload as dict
    :rtype: dict
    """
    if isinstance(proxy_data, bytes):
        proxy_data = proxy_data.decode('utf-8')

    # 1. Extract the DIRACX block
    match = re.search(r"-----BEGIN DIRACX-----(.*?)-----END DIRACX-----", proxy_data, re.DOTALL)
    if not match:
        raise ValueError("DIRACX section not found")

    # 2. Remove whitespaces/newlines and base64-decode the inner content
    b64_data = ''.join(match.group(1).strip().splitlines())

    # 3. Base64 decode
    try:
        decoded = b64decode(b64_data)
    except Exception as e:
        raise ValueError("Base64 decoding failed: %s" % str(e))

    # 4. JSON decode
    try:
        payload = json.loads(decoded)
    except Exception as e:
        raise ValueError("JSON decoding failed: %s" % str(e))

    return payload

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

    def executeRequest(self, raw_data, insecure=False, content_type="json", json_output=True):

        tries_left = MAX_REQUEST_RETRIES

        while (tries_left > 0):
            try: 
                return self.__execute_raw_request(
                    raw_data=raw_data,
                    insecure=insecure,
                    content_type=content_type,
                    json_output=json_output
                )
            except HTTPError as e:
                if e.code >= 500 and e.code < 600: 
                    # If we have an 5XX error (server overloaded), we retry
                    # To avoid DOS-ing the server, we retry few seconds later
                    time.sleep(randint(1, MAX_TIME_BETWEEN_TRIES))
                else:
                    raise e 
            
            tries_left -= 1

        raise RuntimeError("Too much tries. Server down.")

    def __execute_raw_request(self, raw_data, insecure=False, content_type="json", json_output=True):
        """Execute a HTTP request with the data, headers, and the pre-defined data (SSL + auth)

        :param raw_data: Data to send
        :type raw_data: dict
        :param insecure: Deactivate proxy verification WARNING Debug ONLY
        :type insecure: bool
        :param content_type: Data format to send, either "json" or "x-www-form-urlencoded" or "query"
        :type content_type: str
        :param json_output: If we have an output
        :type json_output: bool
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

        if json_output:
            try:
                return json.loads(response_data)  # Parse JSON response
            except ValueError:  # In Python 2, json.JSONDecodeError is a subclass of ValueError
                raise ValueError("Invalid JSON response: %s" % response_data)


class TokenBasedRequest(BaseRequest):
    """Connected Request with JWT support"""

    def __init__(self, diracx_URL, endpoint_path, caPath, jwtData, pilotUUID):

        url = diracx_URL + endpoint_path

        super(TokenBasedRequest, self).__init__(url, caPath, pilotUUID, "TokenBasedConnection")
        self.jwtData = jwtData
        self.diracx_URL = diracx_URL
        self.endpoint_path = endpoint_path
        self.addJwtToHeader()
    
    def addJwtToHeader(self):
        # Adds the JWT in the HTTP request (in the Bearer field)
        self.headers["Authorization"] = "Bearer %s" % self.jwtData["access_token"]

    def executeRequest(self, raw_data, insecure=False, content_type="json", json_output=True, tries_left=1, refresh_callback=None):
       
        while (tries_left >= 0):

            try:
                return super(TokenBasedRequest, self).executeRequest(
                    raw_data,
                    insecure=insecure,
                    content_type=content_type,
                    json_output=json_output
                )
            except HTTPError as e:
                if e.code != 401:
                    raise e
            
                # If we have an unauthorized error, then refresh and retry
                if refresh_callback:
                    refresh_callback()
                
                self.addJwtToHeader()

            tries_left -= 1

        raise RuntimeError("Too much tries. Can't refresh my token.")

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

    def executeRequest(self, raw_data, insecure=False, content_type="json", json_output=True):
        # Adds a flag if the passed cert is a Directory
        if self._hasExtraCredentials:
            raw_data["extraCredentials"] = '"hosts"'
        return super(X509BasedRequest, self).executeRequest(
            raw_data,
            insecure=insecure,
            content_type=content_type,
            json_output=json_output
        )

def refreshUserToken(url, pilotUUID, jwt, clientID):
    """
    Refresh the JWT token (as a user).

    :param str url: Server URL
    :param str pilotUUID: Pilot unique ID
    :param dict jwt: Shared dict with current JWT; updated in-place
    :return: None
    """

    # PRECONDITION: jwt must contain "refresh_token"
    if not jwt or "refresh_token" not in jwt:
        raise ValueError("To refresh a token, a pilot needs a JWT with refresh_token")

    # Get CA path from environment
    caPath = os.getenv("X509_CERT_DIR")

    # Create request object with required configuration
    config = BaseRequest(
        url=url + "api/auth/token",
        caPath=caPath,
        pilotUUID=pilotUUID,
    )

    # Perform the request to refresh the token
    response = config.executeRequest(
        raw_data={
            "refresh_token": jwt["refresh_token"],
            "grant_type": "refresh_token",
            "client_id": clientID
        },
        content_type="x-www-form-urlencoded",
    )

    # Do NOT assign directly, because jwt is a reference, not a copy
    jwt["access_token"] = response["access_token"]
    jwt["refresh_token"] = response["refresh_token"]

def refreshPilotToken(url, pilotUUID, jwt, _=None):
    """
    Refresh the JWT token (as a pilot).

    :param str url: Server URL
    :param str pilotUUID: Pilot unique ID
    :param dict jwt: Shared dict with current JWT; updated in-place
    :return: None
    """

    # PRECONDITION: jwt must contain "refresh_token"
    if not jwt or "refresh_token" not in jwt:
        raise ValueError("To refresh a token, a pilot needs a JWT with refresh_token")

    # Get CA path from environment
    caPath = os.getenv("X509_CERT_DIR")

    # Create request object with required configuration
    config = BaseRequest(
        url=url + "api/auth/pilot-token",
        caPath=caPath,
        pilotUUID=pilotUUID,
    )

    # Perform the request to refresh the token
    response = config.executeRequest(
        raw_data={
            "refresh_token": jwt["refresh_token"],
            "pilot_stamp": pilotUUID
        },
        insecure=True,
    )

    # Do NOT assign directly, because jwt is a reference, not a copy
    jwt["access_token"] = response["access_token"]
    jwt["refresh_token"] = response["refresh_token"]

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

    if not url.endswith("/"):
        url = url + "/"

    # Create request object with required configuration
    config = BaseRequest(
        url="%sapi/auth/revoke" % url,
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
        content_type="query",
        json_output=False
    )
