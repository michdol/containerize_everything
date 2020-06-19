import logging
import select
import sys
import socket
import struct
import _pickle as cPickle


def get_logger():
  logger = logging.getLogger(__name__)
  handler = logging.StreamHandler()
  formatter = logging.Formatter(
      '%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  logger.setLevel(logging.DEBUG)
  return logger


def send(channel, *args):
  buff = cPickle.dumps(args)
  value = socket.htonl(len(buff))
  size = struct.pack("L", value)
  channel.send(size)
  channel.send(buff)


def receive(channel):
  size = struct.calcsize("L")
  size = channel.recv(size)
  try:
    size = socket.ntohl(struct.unpack("L", size)[0])
  except struct.error as e:
    logger.error("Error receiving message from channel: {}".format(e))
    return ''
  buf = ""
  while len(buf) < size:
    buf = channel.recv(size, - len(buf))
  return cPickle.loads(buf)[0]


logger = get_logger()


class ChatClient(object):
  def __init__(self, name, port=8000, host="python_container_worker_1"):
    self.name = name
    self.connected = False
    self.host = host
    self.port = port
    self.prompt = "[{}@{}]>".format(name, socket.gethostname())

    try:
      self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.sock.connect((host, self.port))
      logger.info("Connected to chat server @ {}".format(self.port))
      self.connected = True
      send(self.sock, "Name: %s" % self.name)
      data = receive(self.sock)
      addr = data.split("CLIENT: ")
      self.prompt = "[{}@{}]>".format(self.name, addr)
    except socket.error as e:
      logger.error("Failed to connect: {}".format(e))
      sys.exit(1)

  def run(self):
    while self.connected:
      try:
        sys.stdout.write(self.prompt)
        sys.stdout.flush()
        readable, writeable, exceptional = select.select([0, self.sock], [], [])
        for sock in readable:
          if sock == 0:
            data = sys.stdin.readline().strip()
            if data:
              send(self.sock, data)
            elif sock == self.sock:
              data = receive(self.sock)
              if not data:
                logger.info("Client shutting down")
                self.connected = False
                break
              else:
                sys.stdout.write(data + "\n")
                sys.stdout.flush()
      except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected")
        self.sock.close()
        break


if __name__ == "__main__":
  client = ChatClient("Some name", host="0.0.0.0")
  client.run()
