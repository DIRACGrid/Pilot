"""
   Wasser module is created for providing https requests for Python 2.6,
   where you don't have pyOpenSSL, cryptography.
   Here  SSL wrapper for socket is used.
"""

import json
import socket
import ssl
import re
from urlparse import urlparse


class Response(object):
    """Class for representation of server response, and manipulating data in it"""
    def __init__(self, data):
        """
        Creating and parsing response on
        headers,
        body,
        code of response,
        date of response,
        content_length,
        content_type,
        encoding,
        server
        """
        ind_of_body = data.find('\r\n\r\n')
        self.head = data[:ind_of_body]
        self.body = data[ind_of_body+4:]
        self.code = re.search('(.*)\nDate', self.head).group(1)
        self.date = re.search('\nDate: (.*)\n', self.head).group(1)
        self.content_type = re.search('\nContent-Type:(.*);', self.head).group(1)
        self.content_length = re.search('\nContent-Length:(.*)\n', self.head).group(1)
        self.encoding = re.search('charset=(.*)\n', self.head).group(1)
        self.server = re.search('Server:(.*)', self.head).group(1)
    def __str__(self):
        return "Headers:\n{0}\nBody:\n{1}".format(self.head, self.body)
class Wasser(object):
    """Class to create https requests for Python 2.6"""
    def __init__(self, user_cert, user_key, ca_cert):
        """
        For creating https request you need to provide path for your
        certificate and key and ca_cert for checking certificate of server
        """
        for filename in [user_cert, user_key, ca_cert]:
            try:
                with open(filename) as test_file:
                    print '{0} exists'.format(filename)
            except IOError:
                raise IOError('This %s cannot be accessed' %  filename)
        self.user_cert = user_cert
        self.user_key = user_key
        self.ca_cert = ca_cert
    def create(self):
        """
        Creating socket for connecting and wrapping him with ssl
        """
        unwrap_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if isinstance(self.ca_cert, str):
            ssl_socket = ssl.wrap_socket(unwrap_socket,
                                         certfile=self.user_cert,
                                         keyfile=self.user_key,
                                         ca_certs=self.ca_cert,
                                         cert_reqs=ssl.CERT_REQUIRED)
        else:
            raise Exception("ca_cert isn't provided")
        return ssl_socket

    def get(self, url):
        """
           GET request, provide fully qualified url
           as example - https://localhost:1027/
           not localhost:1027/
        """
        parsed_url = urlparse(url)
        location = parsed_url.netloc
        path = parsed_url.path
        index_of_colon = location.find(':')
        host = location[:index_of_colon]
        port = int(location[index_of_colon+1:])

        ssl_socket = self.create()

        try:
            ssl_socket.connect((host, port))

            request_body = 'GET {0} HTTP/1.1\nAccept: */*\n\n'.format(path)

            ssl_socket.write(request_body)

            data = ssl_socket.read()

            ssl_socket.close()

            return data #Response(data)
        except ssl.SSLError as error:
            print 'Problem with connecting to this url:'
            print url
            print 'Problem:'
            print error
    def post(self, url, message):
        """
           POST request, provide url and message to post
           if type of message is dict -> request will post json
           else request will post text/plain
        """

        ssl_socket = self.create()

        parsed_url = urlparse(url)
        location = parsed_url.netloc
        path = parsed_url.path
        index_of_colon = location.find(':')
        host = location[:index_of_colon]
        port = int(location[index_of_colon+1:])

        try:
            ssl_socket.connect((host, port))

            if message is None:
                raise Exception("You didn't provide any data to post, please write message, or json")
            elif isinstance(message, dict):
                json_string = json.dumps(message)
                message_len = len(json_string)
                request_body = "POST {0} HTTP/1.1\nContent-Type: application/json\nContent-Length: {1}\n\n{2}".format(path, message_len, json_string)
            else:
                message = str(message)
                message_len = len(message)
                request_body = "POST {0} HTTP/1.1\nContent-Type: text/plain\nContent-Length: {1}\n\n{2}".format(path, message_len, message)

            ssl_socket.write(request_body)

            data = ssl_socket.read()

            ssl_socket.close()
            return data #Response(data)
        except ssl.SSLError as error:
            print 'Problem with connecting to this url:'
            print url
            print 'Problem:'
            print error


if __name__ == '__main__':
    test_json = {'wasser':'stein'}
    new_request = Wasser('certs/user.crt', 'certs/user.key', 'certs/CAcert.pem')
    fake_request = Wasser('certs/fake_user.crt', 'certs/fake_user.key',
                          'certs/CA_fake_cert.pem')
    #print '\nPOST request\n'
    #print new_request.post('https://localhost:1027/', test_json)
    #print '\nPOST request\n'
    #print new_request.post('https://localhost:1027/', 'Hello server')
    print '\nGET request, normal certificate\n'
    print new_request.get('https://localhost:1027/')
    print '\nGET request, fake certificate\n'
    print fake_request.get('https://localhost:1027/')
