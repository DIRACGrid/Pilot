""" few functions for dealing with proxies
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import re
from base64 import b16decode
from subprocess import Popen, PIPE

VOMS_FQANS_OID = b"1.3.6.1.4.1.8005.100.100.4"
VOMS_EXTENSION_OID = b"1.3.6.1.4.1.8005.100.100.5"

RE_OPENSSL_ANS1_FORMAT = re.compile(r"^\s*\d+:d=(\d+)\s+hl=")

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

    chain = re.findall(r"-----BEGIN CERTIFICATE-----\n.+?\n-----END CERTIFICATE-----", proxy_data, flags=re.DOTALL)
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
            match = re.search(r"OCTET STRING\s+:/([a-zA-Z0-9]+)/Role=", line)
            if match:
                return match.groups()[0].decode()
    raise NotImplementedError("Something went very wrong")
