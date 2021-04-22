"""
   backportRequests is created to provide https requests for Python 2.6,
   where you don't have pyOpenSSL, cryptography.
   Here  SSL wrapper for socket is used.
"""

import json
import socket
import ssl

try:
  from urlparse import urlparse
except ImportError:
  from urllib.parse import urlparse


class exceptions(object):
  class RequestException(Exception):
    """Exception for requests"""

    def __init__(self, url, message):
      super(exceptions.RequestException, self).__init__(message)
      self.url = url
      self.message = message

    def __str__(self):
      return '\nProblem with connecting to this url:\n{0}\nProblem:\n{1}'.format(self.url, self.message)


def post(url, data, cert, verify='certs/CAcert.pem'):
  """
  POST method for https request.
  Args:
    url(str): url which you want to connect,
    data: message to POST,
    cert(tuple): tuple of your certificate and key, in this order.
    verify(bool): do you want to verify server certificate.
    verify(bool): verify certificate which you want to use in verifying (only if isinstance(verify, str) = True).
  Return:
    obj: Response.
  """
  parsed_url = urlparse(url)
  location = parsed_url.netloc
  path = parsed_url.path
  index_of_colon = location.find(':')
  if index_of_colon != -1:
    host = location[:index_of_colon]
    port = int(location[index_of_colon + 1:])
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
        raise IOError('This %s cannot be accessed' % filename)
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
    raise exceptions.RequestException(url, error_list[-1])
  except socket.error as error:
    raise exceptions.RequestException(url, error.strerror)
  if isinstance(data, dict):
    message = json.dumps(data)
    message_len = len(message)
    content_type = 'application/json'
  else:
    message = str(data)
    message_len = len(message)
    content_type = 'text/plain'
  request_body = "POST {0} HTTP/1.1\nContent-Type: {1}\nContent-Length: {2}\n\n{3}".format(
    path, content_type, message_len, message)
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
  port = int(location[index_of_colon + 1:])
  user_cert = cert[0]
  user_key = cert[1]
  unwrap_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  if isinstance(verify, str):
    for filename in [user_cert, user_key, verify]:
      try:
        open(filename)
      except IOError:
        raise IOError('This %s cannot be accessed' % filename)
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
    raise exceptions.RequestException(url, error_list[-1])
  except socket.error as error:
    raise exceptions.RequestException(url, error.strerror)
  request_body = 'GET {0} HTTP/1.1\nAccept: */*\n\n'.format(path)
  ssl_socket.send(request_body)
  response = ssl_socket.recv()
  ssl_socket.close()
  return response
