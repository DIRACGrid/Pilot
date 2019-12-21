"""Tests for wasser module"""
from multiprocessing import Process
from time import sleep
import unittest
import json
import ssl
import wasser
from simple_ssl_server import SimpleServer


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


class TestWasserRequest(unittest.TestCase):
    """Test for wasser requests"""
    def setUp(self):
        pass
    def test_post_json_success(self):
        """Test for POST application/json success\nNormal certificate, normal
        CA for checking server certificate\n"""
        test_json = {'wasser':'stein'}
        json_string = json.dumps(test_json)
        message_len = len(json_string)
        expecting_response = "HTTP/1.0 200 OK\nContent-Type: text/plain\nContent-Length: {0}\n\n{1}".format(message_len, json_string)
        wasser_post_json_response = wasser.post('https://localhost:1207/',
                                                test_json,
                                                ('certs/user.crt', 'certs/user.key') )
        self.assertEqual(expecting_response, wasser_post_json_response)
    def test_post_text_success(self):
        """Test for POST text/plain success\nNormal certificate, normal CA for
        checking server certificate\n"""
        message = 'How are you'
        message_len = len(message)
        expecting_response = "HTTP/1.0 200 OK\nContent-Type: text/plain\nContent-Length: {0}\n\n{1}".format(message_len, message)
        wasser_post_text_response = wasser.post('https://localhost:1207/',
                                                message,
                                                ('certs/user.crt', 'certs/user.key'))
        self.assertEqual(expecting_response, wasser_post_text_response)
    def test_get_success(self):
        """Test for GET */* success\nNormal certificate, normal CA for checking
        server certificate\n"""
        expecting_response = """HTTP/1.0 200 OK
                       Content-Type: text/html


                       <head>Test message ...</head>
                       <body>Hello there, general Kenobi</body>
                       """
        wasser_get_response = wasser.get('https://localhost:1207/', ('certs/user.crt', 'certs/user.key'))
        self.assertEqual(expecting_response, wasser_get_response)
    def test_get_fail_fake_CA(self):
        """Test for GET fail, fake CA to verify server certificate\n"""
        self.assertRaises(wasser.RequestException, wasser.get,
                          'https://localhost:1207/',
                          ('certs/user.crt', 'certs/user.key'),
                          'certs/CA_fake_cert.pem')
    def test_get_fail_fake_cert(self):
        """Test for GET fail, fake certificate to be verified by server CA\n"""
        self.assertRaises(wasser.RequestException, wasser.get,
                          'https://localhost:1207/',
                          ('certs/fake_user.crt', 'certs/fake_user.key'))
    def test_post_fail_fake_CA(self):
        """Test for POST fail, fake CA to verify server certificate\n"""
        self.assertRaises(wasser.RequestException, wasser.post,
                          'https://localhost:1207/',
                          'Hello there',
                          ('certs/user.crt', 'certs/user.key'),
                          'certs/CA_fake_cert.pem')
    def test_post_fail_fake_cert(self):
        """Test for POST fail, fake certificate to be verified by server CA\n"""
        self.assertRaises(wasser.RequestException, wasser.post,
                          'https://localhost:1207/',
                          'Hello there',
                          ('certs/fake_user.crt', 'certs/fake_user.key'))
    def test_post_fail(self):
        """Test for POST fail, wrong url\n"""
        self.assertRaises(wasser.RequestException, wasser.post,
                          'https://localhostish:1207/',
                          'Hello there',
                          ('certs/user.crt', 'certs/user.key'),)
    def test_get_fail(self):
        """Test for GET fail, wrong url\n"""
        self.assertRaises(wasser.RequestException, wasser.get,
                          'https://localhostish:1207/',
                          ('certs/user.crt', 'certs/user.key'),
                          'certs/CA_fake_cert.pem')
    def tearDown(self):
        pass

class TestWasserIO(unittest.TestCase):
    """Testing other wasser functions: __init__, create()"""
    def setUp(self):
        pass
    def test_get_io_error(self):
        """Testing raising IOError for invoking get method with
        fake parameters """
        self.failUnlessRaises(IOError, wasser.get, 'https://localhost:1207/',
                              ('some_cert', 'some_key'), 'some_CA')
    def test_post_io_error(self):
        """Testing raising IOError for invoking post method with
        fake parameters """
        self.failUnlessRaises(IOError, wasser.post, 'https://localhost:1207/',
                              ('some_cert', 'some_key'), 'some_CA')
    def tearDown(self):
        pass


if __name__ == '__main__':
    addr = ('127.0.0.1', 1207)
    server_cert = 'certs/server.crt'
    server_key = 'certs/server.key'
    ca = 'certs/CAcert.pem'

    server = TestServer(addr, server_cert, server_key, ca, ['/', '/second'],
                        False)
    server_process = Process(target=server.listen)
    server_process.start()
    sleep(1)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestWasserRequest)
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(TestWasserIO))
    unittest.TextTestRunner(verbosity=3).run(suite)

    server_process.terminate()
