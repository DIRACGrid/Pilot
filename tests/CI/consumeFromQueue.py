import time
import sys
import stomp

class MyListener(stomp.ConnectionListener):
    def on_error(self, headers, message):
        print('received an error "%s"' % message)
    def on_message(self, headers, message):
        #sys.stdout.write(message)
        print(message)

def consume():
  host_port  = [('127.0.0.1', int(61614))]
  key_file = 'certificates/client/key.pem'
  cert_file = 'certificates/client/cert.pem'
  ca_certs = 'certificates/testca/cacert.pem'
  conn = stomp.Connection(host_and_ports=host_port, use_ssl = True)
  conn.set_ssl(for_hosts=host_port, key_file = key_file,cert_file = cert_file, ca_certs=ca_certs)
  conn.set_listener('', MyListener())
  conn.start()
  conn.connect()
  conn.subscribe(destination='/queue/test', id=1, ack='auto')
  conn.disconnect()

