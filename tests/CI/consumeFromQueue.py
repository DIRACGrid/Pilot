import stomp
import Queue

class MyListener(stomp.ConnectionListener):
  def __init__( self ):
    self.messages = Queue.Queue()
  def on_error(self, headers, message):
    print('received an error "%s"' % message)
  def on_message(self, headers, message):
    self.messages.put(message)
    print message

def main():
  consume()

def consume():
  '''
  Returns:
    Queue:
  '''
  host_port  = [('128.142.242.99', int(61614))]
  key_file = 'certificates/client/key.pem'
  cert_file = 'certificates/client/cert.pem'
  ca_certs = 'certificates/testca/cacert.pem'
  conn = stomp.Connection(host_and_ports=host_port, use_ssl = True)
  conn.set_ssl(for_hosts=host_port, key_file = key_file,cert_file = cert_file, ca_certs=ca_certs)
  listener = MyListener()
  conn.set_listener('', listener)
  conn.start()
  conn.connect(wait=True)
  conn.subscribe(destination='/queue/test', id=1, ack='auto')
  conn.disconnect()
  return listener.messages

if __name__ == '__main__':
  main()
