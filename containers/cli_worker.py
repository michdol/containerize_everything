import socket
import logging
import sys
import errno

from time import sleep, time

from constants import (
  WORKER_HEADER_LENGTH,
  SERVER_HEADER_LENGTH,
  WORKER_HEADER_MESSAGE_LENGTH,
  HEADER_LENGTH,
  SERVER_ADDRESS,
  SERVER_ADDRESS_WORKERS,
  MessageType,
  WorkerStatus
)
from custom_types.custom_types import WorkerHeader, ServerHeader


class Worker_(object):
  def __init__(self):
    self.id: int = 0
    self.status: WorkerStatus = WorkerStatus.NOT_CONNECTED
    self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  def build_payload(self, message: str, message_type: MessageType) -> str:
    m_len = f"{len(message):04d}"
    message_length = f"{m_len:<{WORKER_HEADER_MESSAGE_LENGTH}}"
    time_sent = int(time())
    header = f"{message_type}|{self.status}|{time_sent}|{message_length}"
    return "{header}\n{message}".format(
      header=header,
      message=message
    )

  def run(self):
    logging.info("Connecting to {}".format(SERVER_ADDRESS_WORKERS))
    # self.socket.connect(SERVER_ADDRESS)
    self.socket.connect(('server', 8001))
    self.socket.setblocking(False)
    host_name = socket.gethostname()
    worker_address = socket.gethostbyname(host_name)
    logging.info("Worker {}:{} connecting".format(*worker_address))
    initial_message: str = self.build_payload(
      "Hello from {}".format(worker_address),
      MessageType.INITIAL_CONNECTION
    )
    logging.info("Sending {}".format(initial_message))
    self.socket.send(initial_message.encode("utf-8"))
    while True:
      payload = self.build_payload("Hello from worker", MessageType.INFO)
      self.socket.send(payload.encode('utf-8'))
      sleep(0.5)
      try:
        header = self.socket.recv(SERVER_HEADER_LENGTH)
        if len(header) == 0:
          logging.error("Connection closed by server")
          sys.exit()
        parsed_header: ServerHeader = self.parse_server_header(header)
        message: bytes = self.socket.recv(parsed_header.message_length)
        logging.info("Header: {}\nMessage: {}".format(parsed_header, message.decode("utf-8")))
      except IOError as e:
        # This is normal on non blocking connections - when there are no incoming data error is going to be raised
        # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
        # We are going to check for both - if one of them - that's expected, means no incoming data, continue as normal
        # If we got different error code - something happened
        if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
          logging.error("Reading error: {}".format(e))
          sys.exit()

        # We just did not receive anything
        continue
      except Exception as e:
        logging.error("Receving error: {}".format(e))
        sys.exit()

  def parse_server_header(self, header: bytes) -> ServerHeader:
    values = header.decode("utf-8").strip().split("|")
    return ServerHeader(*[int(v) for v in values])


def main():
  format_ = "%(asctime)s %(levelname)s: %(message)s"
  logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

  worker = Worker_()
  worker.run()


if __name__ == "__main__":
  main()
