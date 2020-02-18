""" Unit tests for MessageSender
"""

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

from multiprocessing import Process
from time import sleep
import unittest
import json
import sys
import os
from Pilot.simple_ssl_server import SimpleServer
from Pilot.MessageSender import RESTSender


class TestServer(SimpleServer):
  """Server for tests"""

  def get(self, path):
    if path == '/':
      response = """HTTP/1.0 200 OK
                       Content-Type: text/html


                       <head>Test message ...</head>
                       <body>Hello there, general Kenobi</body>
                       """
      self.ssl_socket.send(response)
    elif path == '/second':
      reponse = """HTTP/1.1 200 OK
            Content-Type: text/plain


            Hello there"""
      self.ssl_socket.send(response)

  def post(self, path):
    if path == '/':
      if isinstance(self.message, dict):
        json_string = json.dumps(self.message)
        message_len = len(json_string)
        response = "HTTP/1.0 200 OK\nContent-Type: application/json\nContent-Length: {0}\n\n{1}".format(
            message_len, json_string)
      else:
        message = str(self.message)
        message_len = len(message)
        response = "HTTP/1.0 200 OK\nContent-Type: text/plain\nContent-Length: {0}\n\n{1}".format(message_len, message)
    self.ssl_socket.send(response)


class TestRESTSender(unittest.TestCase):

  def setUp(self):
    self.testFile = 'myFile'
    self.testMessage = 'my test message'

  def test_success(self):
    params = {'HostKey': 'key', 'HostCertificate': 'cert', 'CACertificate':
              'CAcert.pem',
              'Url': 'https://localhost:1207/', 'LocalOutputFile': self.testFile}
    msgSender = RESTSender(params)
    res = msgSender.sendMessage(self.testMessage, 'info')
    self.assertTrue(res)

  def test_failure_badParams(self):
    self.assertRaises(ValueError, RESTSender, {'blabl': 'bleble'})


if __name__ == '__main__':
  addr = ('127.0.0.1', 1207)
  server_cert = 'server.crt'
  server_key = 'server.key'
  ca = 'CAcert.pem'
  CA_file = open(ca, 'w+')
  CA_file.write('''-----BEGIN CERTIFICATE-----
MIIDuTCCAqGgAwIBAgIJAOFEPV8gUfTvMA0GCSqGSIb3DQEBCwUAMHMxCzAJBgNV
BAYTAlBMMRMwEQYDVQQIDApTb21lLVN0YXRlMQswCQYDVQQHDAJLUjEUMBIGA1UE
CgwLRmFrZUNvbXBhbnkxDzANBgNVBAMMBkZha2VDQTEbMBkGCSqGSIb3DQEJARYM
ZmFrZUBmYWtlLnBsMB4XDTE5MDExMTE5NDc1OFoXDTIxMTAzMTE5NDc1OFowczEL
MAkGA1UEBhMCUEwxEzARBgNVBAgMClNvbWUtU3RhdGUxCzAJBgNVBAcMAktSMRQw
EgYDVQQKDAtGYWtlQ29tcGFueTEPMA0GA1UEAwwGRmFrZUNBMRswGQYJKoZIhvcN
AQkBFgxmYWtlQGZha2UucGwwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIB
AQDTRt7YychhpsxxWsFUpl8sbSCBWvJgc7NkZ3xMx9JeNSg6/EviNO00LrFP18r7
tt6iZx1lZ0xm6YASCG98VTnCNz0zLG1awSCrFQGJM23sNbtDPcJZ9KU0CoY91GHH
hwXBBWLILU965bmpmuK3wbEEVZCUfCQtEqe1gE8OntO49t4zC16YFBXPpsuyXV1R
o7VKqEwDPh1Ot8nwLrb9cL6gLAwM/k8tZKcn54XjvZvlWRZUM1iQyXiz2pJfGavw
PdHxXCYYs4+wvQF6mrZyxhPuvoXUs78epf+P6hz6Atw0Eibm0P54dOV0TXCedQVh
Z8gde/STtb32p5+Q/OeRSddTAgMBAAGjUDBOMB0GA1UdDgQWBBRQQTJ0OyYWNw1U
mwhuKpkFQW0TkjAfBgNVHSMEGDAWgBRQQTJ0OyYWNw1UmwhuKpkFQW0TkjAMBgNV
HRMEBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQAQbIV5gcHnFGQatD5HhDq+vdBP
jmpehE2heEo708uTjXpD1Bl1D+BZTK+tyvhQtN9gGTqX/HvM0NvXSKmufofEqt17
2MTA4TjiH/0kLn3oe6itb/MSL79vaHPqZcK56qU2nQ36ji3VMEITOjxsscgGMHY0
WrORn4D5IQB9pdkMSrxb0uOHzXem6tptItpXRBGnuOqK9VnrNMHRXioDSonBWHCg
5FOzR9M2wCCeNhWZ7GlkPfEMsRS2YED4CHYF4/noFscTIBn0nzi7HmfCWZ9IZt4U
JU+cMU9UeD0bcayGYn6+FdUOAMRL1nuiuZSGsfDfP9uf8MUt/b9svEQdy7AN
-----END CERTIFICATE-----''')
  CA_file.close()
  server_cert_file = open(server_cert, 'w+')
  server_cert_file.write('''-----BEGIN CERTIFICATE-----
MIIDajCCAlICCQDFJV8E0N4atzANBgkqhkiG9w0BAQsFADBzMQswCQYDVQQGEwJQ
TDETMBEGA1UECAwKU29tZS1TdGF0ZTELMAkGA1UEBwwCS1IxFDASBgNVBAoMC0Zh
a2VDb21wYW55MQ8wDQYDVQQDDAZGYWtlQ0ExGzAZBgkqhkiG9w0BCQEWDGZha2VA
ZmFrZS5wbDAeFw0xOTAxMTEyMDMyMjlaFw0yMDA1MjUyMDMyMjlaMHsxCzAJBgNV
BAYTAlBMMRMwEQYDVQQIDApTb21lLVN0YXRlMQswCQYDVQQHDAJLUjEUMBIGA1UE
CgwLRmFrZUNvbXBhbnkxEjAQBgNVBAMMCWxvY2FsaG9zdDEgMB4GCSqGSIb3DQEJ
ARYRbG9jYWxob3N0QGZha2UucGswggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQCnqmuJomixREZ0BEpeawjAfmbN6691t444VzWIeRto0WvmamNtaDAlPlBA
MnbK/NOIe2zjgOaVDX8Hs5T3AlgIVtSUcgQjhaPLRyTWxqFYQQ+0ag2ajVYkhwiA
SiJblo7KMCIGjGj9o3Zp/ArfsrMgymxSHZXd2NMKDne8U6V7ftcb6Lg0F0BByZnZ
mvVzHmE5/BzjDxaTttx/oFy88o7kKUT+FVMuFOusJtSQavGUp8kHQSmxVFKsL06W
D6g4Jk3d/z+vt5WETgEEZa36NQaMpFCVmaqtNY4gbHLZFTrvDbDAs6Dwx1mO6pj1
+Rar+Bjkfp43T3xALD37x5E9xNSfAgMBAAEwDQYJKoZIhvcNAQELBQADggEBALLV
EaUy+sJLat7/OdyG6dKcxgSdRXLJnm/Pk5chtrJ3oLd5iC84GRESie/IbXT8NNHA
IHufgeko/+ScBRbOvfcEkUjTZU8CFl2Y2OkHSdlzaVGrVW3jVT8lTYjsWgIpw9F7
Of41xwWrv231dGFoNd/d6xXR3MgKwZZ8pMrbmSVmbKMYHqQn5NFklVPmqem2hegT
SzMcBln1mU84JnYWuqV7qzPhbSQVJreQMD2mWuhYXQ6ebqsvXAcL9yJzSgK/j5dV
iCQrmT6rDtXNC+U+aos9AyuBZmfakywpMJnTYijTqaatqhVyjcckeuAh071OAEl+
YDz8oBCf0xLyILyd1+8=
-----END CERTIFICATE-----''')
  server_cert_file.close()
  server_key_file = open(server_key, 'w+')
  server_key_file.write('''-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAp6priaJosURGdARKXmsIwH5mzeuvdbeOOFc1iHkbaNFr5mpj
bWgwJT5QQDJ2yvzTiHts44DmlQ1/B7OU9wJYCFbUlHIEI4Wjy0ck1sahWEEPtGoN
mo1WJIcIgEoiW5aOyjAiBoxo/aN2afwK37KzIMpsUh2V3djTCg53vFOle37XG+i4
NBdAQcmZ2Zr1cx5hOfwc4w8Wk7bcf6BcvPKO5ClE/hVTLhTrrCbUkGrxlKfJB0Ep
sVRSrC9Olg+oOCZN3f8/r7eVhE4BBGWt+jUGjKRQlZmqrTWOIGxy2RU67w2wwLOg
8MdZjuqY9fkWq/gY5H6eN098QCw9+8eRPcTUnwIDAQABAoIBACkxGExvJzNt57U3
HKJHv5WzOESdA7VzDDDRVCicQFynHtA0EQtfDn0H6yVqgH7sUHf2gtD96ShzcWMN
/qoU3FXoJz/1JwknGw+lAer2T8tj6JzVdVQkJybAOhlynTBNM/V+j812D5FI6J2v
O2ir+ZAzyxr9g8VGMMsGtOoCzuQg5qCIP+Yt8D4zQNEW9UULiCj4wwogZ6c5O6o2
Fyj1HBHG9+eI2RI+AwKWLp4IZQSBzLjCJbdMOuKPAnP+Hodfjba0V97RSg/Rz+1R
+ZIccJSudYMKtQ8kUsldn3xr+TMmylwWJNmopHD9QktFix/yb0TgbV/aQqOOw36l
aQpyxEkCgYEA0Rn3wq9K9NiXFo+/EFTWlVEgMHz7Rb4GebtIaM26Ka98E2J1vrN/
evvXKyvMXBAXnh1MJZFRl0de/CEbHn1FqoHR+bkmrc2tWcEzJXDV6XCt+q2jYPYp
PPssCLVhmCeTnLmJcTfQTxGBKdOiAKQldqEPNEra3L7M9vo8CtTig5UCgYEAzUVT
aytRRbuIm+1wHx6+pJ0VKXSB2D/2xndszqo6PUB1IwEJADacixancLksbIOk1WGC
LnFao19w/Npq5wl/94tl2dfUWnGDi5AvWutQKDSK3etklQSh2qqYZ9FBOmVoeB4+
OJDbuUvbgm2IObu78Q6bBcBjOJcFZVoXcmDfqmMCgYAhwNJYr9kmquvArZWG+lrl
IYJTsWkSOflrnwqyODtLzVL3AhbFoM38OTjjdB954PMfB9Wp3spP5Cp2ApYRFuGv
A2O0rumKdr/71A8AhTVSiGjdJThRR4sil9zkzvqhCApw6xY/m2XZzZaO/OWSuux9
OMRuiYLIzVfiqkQU74Zc/QKBgA8SZAmeaJ1CI8mvKWhfjYfwsLkWgOIr8CaqZibW
gOg2b2NelBab6+qagzjXn9dn4xZ3zmMyl4EfZOBr+SV1oRu/9H6GRmVNqGb68z8t
v/jzwq6AtiXq7SdtFzuoNa3f/Ee1kMP+fuOgGkH9YN88VZRhiihl8+MX06GZd9dC
HaoZAoGBAMuvL7nHiJYYWpvodkLj6EjJooWsJkMtzWfC/ox6CBdIYlNM3s5UEkQI
JDdPmz8seNh+bq5QvL9fnh0fgmeUzV6xhsd9IxQGSQj5yfgEMZXPYDGrAL2hVGNJ
/8j1N6ULtBuUwQxvSXF4TixNwM6HpL8Pt9+4wkw4jul/cXe/qH8F
-----END RSA PRIVATE KEY-----''')
  server_key_file.close()

  user_cert_file = open('cert', 'w+')
  user_cert_file.write('''-----BEGIN CERTIFICATE-----
MIIDXDCCAkQCCQDFJV8E0N4atTANBgkqhkiG9w0BAQsFADBzMQswCQYDVQQGEwJQ
TDETMBEGA1UECAwKU29tZS1TdGF0ZTELMAkGA1UEBwwCS1IxFDASBgNVBAoMC0Zh
a2VDb21wYW55MQ8wDQYDVQQDDAZGYWtlQ0ExGzAZBgkqhkiG9w0BCQEWDGZha2VA
ZmFrZS5wbDAeFw0xOTAxMTExOTQ4NTVaFw0yMDA1MjUxOTQ4NTVaMG0xCzAJBgNV
BAYTAlBMMQ0wCwYDVQQIDARVc2VyMQswCQYDVQQHDAJLUjESMBAGA1UECgwJTG9j
YWxGQWtlMREwDwYDVQQDDAh1c2VyQ2VydDEbMBkGCSqGSIb3DQEJARYMdXNlckBm
YWtlLnBsMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1kVc7zgjaEzc
MUMUI+Mqe+50kF3qxCshtsd7YXWqQZ7p8ogbL/s2Uy4wjb4OqxSS9VWkkLJokgdx
RZJUc55NrAM0ilFl6A+aY5saSy25iGhe2X6B2MYgV4gDuTlmrdyNACrFjIU+Xk4d
u0+9i7iQmA0yMVn3fuxb2YJffTsnJnDrmGUHdzCKdXBhDjFe0hIa7ZVfF6lK8xbF
WVr23OmB70vmReFYXzve3QXBEX2bn1LtbfZZT/WcTitIDa/+jUWaf5U9PKOC9C1K
vnXvUIbSR3VBCVuQkg6tzNAKID7DaBYGbs/z1AUdGU4hHRCNbtT+coZC3oKv31z9
ZuHFwhGKUQIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQCOwKp1AgYsHB6IkPRYsJOy
2HhSwBnEsSJ/QFeDVF3vCSJsILuOD2uLvp7P/5KrEWjzG1H6/IJTa6AETAAoVYbt
5Aa4DFCBMuJcFCwX8BvpB6e8cz1rKSFqJRwR+gU5ghfaAZjM6qq+62XxuCjlQM04
RlTLbDo92R5gyypNKFbdH/xldMElF9vljSyrdrot5yJuOiF0Foa5PL8T5XD00R7l
jGOOo3PWGBLC0JLcojBB1FCp6+HpD27yixu4cZWiLzeBD7CzIZKcXTkkWg/hvizb
GVyZygrgouxS+IVQ8yM1mvwnHEKg4/N0KbPQuR/gU63G+qRG09LgmP+NgLcLfDFl
-----END CERTIFICATE-----''')
  user_cert_file.close()

  user_key_file = open('key', 'w+')
  user_key_file.write('''-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA1kVc7zgjaEzcMUMUI+Mqe+50kF3qxCshtsd7YXWqQZ7p8ogb
L/s2Uy4wjb4OqxSS9VWkkLJokgdxRZJUc55NrAM0ilFl6A+aY5saSy25iGhe2X6B
2MYgV4gDuTlmrdyNACrFjIU+Xk4du0+9i7iQmA0yMVn3fuxb2YJffTsnJnDrmGUH
dzCKdXBhDjFe0hIa7ZVfF6lK8xbFWVr23OmB70vmReFYXzve3QXBEX2bn1LtbfZZ
T/WcTitIDa/+jUWaf5U9PKOC9C1KvnXvUIbSR3VBCVuQkg6tzNAKID7DaBYGbs/z
1AUdGU4hHRCNbtT+coZC3oKv31z9ZuHFwhGKUQIDAQABAoIBAQCsrvAL9tFKUI8w
wF+t4HkvseiNJLN8b0pXdQLxc5PIGNtwU9KdY7bPaK1GvoIxzH33bJMY7j+qWIco
S5r2JwFv/JFOW/VmBZUmayzQo8QftAWlAPiCjIIqKPrfPuyKd/HGzbGx4vx1oj0B
5Wzb+t3FPPVToq78wl3vuMteMNsHdYXg2yCZG6fXkbNkFWqWHaqp+8Y3ZlcU1rhO
Z7LtHDi6WYfaMJWMW9xKDf70oCXKr/cwgY1h7i41eQidqDeION+4vcGuzmjq5atU
MlSMpx9OSUPyeXfxzyb/3qWOgfa2GR+R9anwJ2fCncEP5SX8t2oBJ9WdnIYEVJ1z
pWKi0vl1AoGBAPYeN8fEpuxsj2Hgzg4ROXm5fydd+Krqzdo/ULEskYt25oPir8nM
t6JdLdbIKUuIUh9uMfa8ZCWet1OteFuSD2ayj0xYAGhois9tmHa3QIX0TisHgPTz
mpN5jFPqhYkhu5GLid+3MqgXeuSWtEfiSg/2nVSF4i860eWRF6XEooL7AoGBAN7f
zB59cDNGdhafd1H/ExvhfPxtX1cB+t4dv3zHqBaLYpE5g0SENhdQbyxQJgIWz3kp
PRknI8lnl12kkcie0VQUEmt1m7Gvg31Hj4iloEvI6ma+ZHZKnGfraASbrRNJLg43
CYMLhs/ASs/FcS/NLybNchSp8DPJKKX10GBJy0YjAoGAcoo1o37dwIH1aLPasalK
el/d0VBmfgSwsLVutEXtpl47gX1qGhxwCdwbjS2yKjjTH1WFYzLh2LA42XSN4u/i
wwSus/Twm6ark0WKAxXdrXm5N0VSuqz0b1XN/O/UHbHZPS8Xh0oXBSuIQgHw/NNP
bIZ1SfTVAu346UHRI5CToSkCgYAOLXxloCMoD95pOAG2JJzJlEGIKUj8VvLneEr7
HBRUQs+lX1w7WpG6T/KShhK05VCTa40ocXX0VPOrEFH5yiiUyaYWUefymLCrooa9
8ZNN3t0SZiAr6jki3zXBvUl4RZp5awTe4jfUNW5M40l8+fd652zPZbQTB0PfstBr
n6YfswKBgHCduQC30UMmSB0y46NrTJ32pHOoxJj9PiJFidQV/9ifVjcrVHJXGRzA
WA9z7+WQHJOoGo1JaX8sp+8DRuJEJhWDXGqhNLWpmmFAgbY5jq6OaUEhiOnv4Fwa
x4tCpgBFteVpNiJ1gZ3SKdDFZ/mKkIGau20fi6oBdldtrULijjVF
-----END RSA PRIVATE KEY-----''')
  user_key_file.close()

  server = TestServer(addr, server_cert, server_key, ca, ['/', '/second'])
  server_process = Process(target=server.listen)
  server_process.start()
  print 'Server is listening'
  sleep(1)

  suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestRESTSender)
  testResult = unittest.TextTestRunner(verbosity=2).run(suite)
  server_process.terminate()
  for f in ['cert', 'key', server_cert, server_key, ca]:
    os.remove(f)
  sys.exit(not testResult.wasSuccessful())
