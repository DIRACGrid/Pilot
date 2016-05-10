import time
import sys
import stomp

class MyListener(stomp.ConnectionListener):
    def on_error(self, headers, message):
        print('received an error "%s"' % message)
    def on_message(self, headers, message):
        print(message)

def main():
  consume()

def consume():
  host_port  = [('128.142.242.99', int(61614))]
  key_file = 'certificates/client/key.pem'
  cert_file = 'certificates/client/cert.pem'
  ca_certs = 'certificates/testca/cacert.pem'
  conn = stomp.Connection(host_and_ports=host_port, use_ssl = True)
  conn.set_ssl(for_hosts=host_port, key_file = key_file,cert_file = cert_file, ca_certs=ca_certs)
  conn.set_listener('', MyListener())
  conn.start()
  conn.connect(wait=True)
  conn.subscribe(destination='/queue/test', id=1, ack='auto')
  conn.disconnect()
  #while 1:
    #pass

if __name__ == '__main__':
  main()
