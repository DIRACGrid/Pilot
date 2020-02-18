'''This is simple server, which is based on sockets and ssl '''

import json
import ssl
import socket
import sys
import re

class SimpleServer(object):
    """Class for receiving and answering data from TLS connection"""
    def __init__(self, addr, cert, key, CA, path_array, verbose=True):
        """Creating socket"""
        self.addr = addr
        self.cert = cert
        self.key = key
        self.ca = CA
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(addr)
        self.path = path_array
        self.verbose = verbose
    def listen(self):
        """Listening on socket"""
        if self.verbose:
            print 'Begin listening\n'
        self.sock.listen(5)
        while True:
            try:
                self.handle()
            except KeyboardInterrupt:
                self.close()
                if self.verbose:
                    print '\nConnection closed'
                sys.exit()

    def handle(self):
        """Simple handler for TLS connection"""
        connection_stream, fromaddr = self.sock.accept()
        try:
            self.ssl_socket = ssl.wrap_socket(connection_stream,
                                         certfile=self.cert,
                                         keyfile=self.key,
                                              ca_certs=self.ca,
                                         cert_reqs=ssl.CERT_REQUIRED,
                                         server_side=True)
            data = self.ssl_socket.read()
            if self.verbose:
                print '\n\nThis person sending message to us - {0}'.format(fromaddr)
                cert = self.ssl_socket.getpeercert()
                print 'Certificate of person:'
                print cert
                print 'Message:'
                print data
            for path in self.path:
                if re.search('^GET {0} HTTP/1.1'.format(path), data):
                    self.get(path)
                if re.search('^POST {0} HTTP/1.1'.format(path), data):
                    [head, self.message] = data.split('\n\n')
                    self.post(path)
            self.ssl_socket.close()
        except ssl.SSLError as e:
            pass
#            print 'Problem with connection from this addr:\n'
#            print fromaddr
#            print 'Problem:\n'
#            print e
    def close(self):
        """Close socket"""
        self.sock.close()
    def get(self, path):
        """GET path handler"""
        pass
    def post(self, path):
        """POST path handler"""
        pass

class TestServer(SimpleServer):
    """Server for tests"""
    def get(self, path):
        if path == '/':
            response = """HTTP/1.0 200 OK
Content-Type: text/html


<head>Test message ...</head>
<body>Hello there, general Kenobi</body>"""
            another_response = 'HTTP/1.0 200 OK\nContent-Type: text/html\r\n\r\n<head>Test message...</head><body>Hello there general Kenobi</body>'
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



if __name__ == '__main__':
    addr = ('127.0.0.1', 1027)
    server_cert = 'certs/server.crt'
    server_key = 'certs/server.key'
    ca = 'certs/CAcert.pem'
    server = TestServer(addr, server_cert, server_key, ca, ['/', '/second'])
    server.listen()

