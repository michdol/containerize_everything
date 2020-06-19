import logging
import os
import socket


SERVER_HOST = "python_container_worker_1"
SERVER_PORT = 8000
BUF_SIZE = 1024


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


class ForkedClient():
  def __init__(self, host, port):
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.connect((host, port))

  def run(self):
    current_pid = os.getpid()
    logger.info("<{}> sending message to server".format(current_pid))
    sent_data_length = self.sock.send("Hello server".encode("utf-8"))
    logger.info("<{}> sent {} characters".format(current_pid, sent_data_length))

    response = self.sock.recv(BUF_SIZE)
    logger.info("<{}> received {}".format(current_pid, response))

  def shutdown(self):
    self.sock.close()


if __name__ == "__main__":
  client1 = ForkedClient(SERVER_HOST, SERVER_PORT)
  client1.run()
  client2 = ForkedClient(SERVER_HOST, SERVER_PORT)
  client2.run()

  client1.shutdown()
  client2.shutdown()
