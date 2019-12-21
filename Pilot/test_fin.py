""" Unit tests for MessageSender
"""

# pylint: disable=protected-access, missing-docstring, invalid-name, line-too-long

from multiprocessing import Process
from time import sleep
import unittest
import json
import ssl
import wasser
from simple_ssl_server import SimpleServer
import sys
import os
from MessageSender import LocalFileSender, StompSender, RESTSender, eraseFileContent, loadAndCreateObject

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
                response = "HTTP/1.0 200 OK\nContent-Type: application/json\nContent-Length: {0}\n\n{1}".format(message_len, json_string)
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

    server = TestServer(addr, server_cert, server_key, ca, ['/', '/second'])
    server_process = Process(target=server.listen)
    server_process.start()
    print 'Server is listening'
    sleep(1)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestRESTSender)
    testResult = unittest.TextTestRunner(verbosity=2).run(suite)
    server_process.terminate()
    sys.exit(not testResult.wasSuccessful())
