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


class RequestException(Exception):
    """Exception for requests"""
    def __init__(self, url, message):
        super(RequestException, self).__init__(url, message)
        self.url = url
        self.message = message
    def __str__(self):
        return '\nProblem with connecting to this url:\n{0}\nProblem:\n{1}'.format(self.url, self.message)

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
        values_and_regex = {'code':'(.*)\nDate',
                            'date':'\nDate:(.*)\n',
                            'content_type':'\nContent-Type:(.*)\n',
                            'content_length':'\nContent-Length:(.*)',
                            'encoding':'charset=(.*)\n',
                            'server':'Server:(.*)'
                           }
        self.headers = {}
        for key, regex in values_and_regex.items():
            res = re.search(regex, self.head)
            if res is None:
                self.headers[key] = None
            else:
                self.headers[key] = res.group(0)

        #self.code = re.search('(.*)\nDate', self.head).group(1)
        #self.date = re.search('\nDate: (.*)\n', self.head).group(1)
        #self.content_type = re.search('\nContent-Type:(.*);', self.head).group(1)
        #self.content_length = re.search('\nContent-Length:(.*)\n', self.head).group(1)
        #self.encoding = re.search('charset=(.*)\n', self.head).group(1)
        #self.server = re.search('Server:(.*)', self.head).group(1)
    def code(self):
        '''Return message code'''
        return self.headers['code']
    def date(self):
        '''Return response date'''
        return self.headers['date']
    def content_type(self):
        '''Return response content_type'''
        return self.headers['content_type']
    def content_length(self):
        '''Return response content length'''
        return self.headers['content_length']
    def encoding(self):
        '''Return response encoding'''
        return self.headers['encoding']
    def server(self):
        '''Resturn response server'''
        return self.headers['server']
    def __str__(self):
        return "Headers:\n{0}\nBody:\n{1}".format(self.head, self.body)




def post(url, data, cert, verify='certs/CAcert.pem'):
    """
    POST method for https request, please provide:
    url - url which you want to connect,
    data - message to POST,
    cert - tuple of your certificate and key, in this order
    verify - do you want to verify server certificate,
    verify - verify certificate which you want to use in verifying (only if isinstance(verify, str) = True)
    """
    parsed_url = urlparse(url)
    location = parsed_url.netloc
    path = parsed_url.path
    index_of_colon = location.find(':')
    if index_of_colon != -1:
        host = location[:index_of_colon]
        port = int(location[index_of_colon+1:])
    else:
        port = 443
        host = location
    user_cert = cert[0]
    user_key = cert[1]
    unwrap_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if isinstance(verify, str):
        for filename in [user_cert, user_key, verify]:
            try:
                open(filename)
            except IOError:
                raise IOError('This %s cannot be accessed' %  filename)
        ssl_socket = ssl.wrap_socket(unwrap_socket,
                                     certfile=user_cert,
                                     keyfile=user_key,
                                     ca_certs=verify,
                                     cert_reqs=ssl.CERT_REQUIRED)
    else:
        ssl_socket = ssl.wrap_socket(unwrap_socket,
                                     certfile=user_cert,
                                     keyfile=user_key,
                                     cert_reqs=ssl.CERT_NONE)
    try:
        ssl_socket.connect((host, port))
    except ssl.SSLError as error:
        error_list = error.strerror.split(':')
        raise RequestException(url, error_list[-1])
    except socket.error as error:
        raise RequestException(url, error.strerror)
    if isinstance(data, dict):
        message = json.dumps(data)
        message_len = len(message)
        content_type = 'application/json'
    else:
        message = str(data)
        message_len = len(message)
        content_type = 'text/plain'
    request_body = "POST {0} HTTP/1.1\nContent-Type: {1}\nContent-Length: {2}\n\n{3}".format(path, content_type, message_len, message)
    ssl_socket.send(request_body)
    response = ssl_socket.recv()
    ssl_socket.close()
    return response

def get(url, cert, verify='certs/CAcert.pem'):
    """
    GET method for https request, please provide:
    url - url which you want to connect,
    cert - tuple of your certificate and key, in this order
    verify - do you want to verify server certificate,
    verify - verify certificate which you want to use in verifying (only if isinstance(verify, str) = True)
    """
    parsed_url = urlparse(url)
    location = parsed_url.netloc
    path = parsed_url.path
    index_of_colon = location.find(':')
    host = location[:index_of_colon]
    port = int(location[index_of_colon+1:])
    user_cert = cert[0]
    user_key = cert[1]
    unwrap_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if isinstance(verify, str):
        for filename in [user_cert, user_key, verify]:
            try:
                open(filename)
            except IOError:
                raise IOError('This %s cannot be accessed' %  filename)
        ssl_socket = ssl.wrap_socket(unwrap_socket,
                                     certfile=user_cert,
                                     keyfile=user_key,
                                     ca_certs=verify,
                                     cert_reqs=ssl.CERT_REQUIRED)
    else:
        ssl_socket = ssl.wrap_socket(unwrap_socket,
                                     certfile=user_cert,
                                     keyfile=user_key,
                                     cert_reqs=ssl.CERT_NONE)
    try:
        ssl_socket.connect((host, port))
    except ssl.SSLError as error:
        error_list = error.strerror.split(':')
        raise RequestException(url, error_list[-1])
    except socket.error as error:
        raise RequestException(url, error.strerror)
    request_body = 'GET {0} HTTP/1.1\nAccept: */*\n\n'.format(path)
    ssl_socket.send(request_body)
    response = ssl_socket.recv()
    ssl_socket.close()
    return response




if __name__ == '__main__':
    test_json = {'wasser':'stein'}
    print '\nGET request, normal certificate\n'
    print get('https://localhost:1027/',
              ('certs/user.crt', 'certs/user.key'))
