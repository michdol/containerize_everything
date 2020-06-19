import logging
import selectors
import socket
import types

from binascii import hexlify


def get_logger():
  logger = logging.getLogger(__name__)
  handler = logging.StreamHandler()
  formatter = logging.Formatter(
      '%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  logger.setLevel(logging.DEBUG)
  return logger


logger = get_logger()
sel = selectors.DefaultSelector()
messages = [b'I am a', b'Dick']


def start_connections(host, port, num_conns):
  server_addr = (host, port)
  for i in range(0, num_conns):
    connid = i + 1
    logger.info("Starting connection {} with {}".format(connid, server_addr))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(server_addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    data = types.SimpleNamespace(
      connid=connid,
      msg_total=sum(len(m) for m in messages),
      recv_total=0,
      messages=list(messages),
      outb=b''
    )
    sel.register(sock, events, data=data)


def handle_connection(key, mask):
  sock = key.fileobj
  data = key.data
  if mask & selectors.EVENT_READ:
    recv_data = None
    try:
      recv_data = sock.recv(1024)
    except Exception as e:
      logger.info("Caught error {}".format(e))
      sel.unregister(sock)
      sock.close()
    if recv_data:
      logger.info("Received: {}, from {}".format(repr(recv_data), data.connid))
      data.recv_total += len(recv_data)
    if not recv_data or data.recv_total == data.msg_total:
      logger.info("Closing connection with {}".format(data.connid if data else "NO DATA"))
      sel.unregister(sock)
      sock.close()
  if mask & selectors.EVENT_WRITE:
    if not data.outb and data.messages:
      data.outb = data.messages.pop(0)
    if data.outb:
      logger.info("Sending {}, to {}".format(repr(data.outb), data.connid))
      sent = 0
      try:
        sent = sock.send(data.outb)
      except Exception as e:
        logger.error("Error while sending to {}\n{}".format(data.connid, e))
      data.outb = data.outb[sent:]


def main():
  HOST = "python_container_worker_1"
  PORT = 8000
  start_connections(HOST, PORT, 1)

  try:
    while True:
      events = sel.select(timeout=1)
      if events:
        for key, mask in events:
          handle_connection(key, mask)
      if not sel.get_map():
        break
  except KeyboardInterrupt:
    logger.info("Caught keyboard interrupt, exiting")
  finally:
    sel.close()


class Server(object):
  def __init__(self):
    self.__host_name = socket.gethostname()

  @property
  def host_name(self):
    return self.__host_name

  @property
  def ip_addr(self):
    return socket.gethostbyname(self.__host_name)

  def get_remote_machine_info(self, remote_host):
    try:
      logger.info("IP addr: %s" % socket.gethostbyname(remote_host))
    except socket.error as err_msg:
      logger.error("Error - %s: %s" % (remote_host, err_msg))

  def convert_ip_addr(self, ip_addr: str):
    packed_ip_addr = socket.inet_aton(ip_addr)
    unpacked_ip_addr = socket.inet_ntoa(packed_ip_addr)
    logger.info("IP: {} => Packed: {}, Unpacked: {}".format(
      ip_addr, repr(hexlify(packed_ip_addr)), unpacked_ip_addr))

  def find_service_name(self):
    protocol_name = 'tcp'
    for port in [80, 25]:
      service_name = socket.getservbyport(port, protocol_name)
      logger.info("Port: %s => service name: %s" % (port, service_name))
    service_name = socket.getservbyport(53, 'udp')
    logger.info("Port: %s => service name: %s" % (port, service_name))

  def convert_integer(self):
    data = 1234
    # 32-bit
    logger.info("\nconvert_integer 32 bit")
    logger.info("Original: %s" % data)
    logger.info("Long host byte order: %s" % socket.ntohl(data))
    logger.info("Network byte order: %s" % socket.htonl(data))
    # 16-bit
    logger.info("\nconvert_integer 16 bit")
    logger.info("Original: %s" % data)
    logger.info("Short host byte order: %s" % socket.ntohs(data))
    logger.info("Network byte order: %s" % socket.htons(data))


if __name__ == "__main__":
  # main()
  s = Server()
  print("My name is {}, I work at {}".format(s.host_name, s.ip_addr))
  s.get_remote_machine_info('www.python.org')
  s.get_remote_machine_info('python_container_worker_1')
  s.convert_ip_addr("127.0.0.1")
  s.convert_ip_addr("168.192.0.1")
  s.find_service_name()
  s.convert_integer()

# https://realpython.com/python-sockets/#handling-multiple-connections
# page 15 (28)