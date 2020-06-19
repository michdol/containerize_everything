import logging
import select
import socket

from typing import Dict

import settings
from custom_types.custom_types import Address

HEADER_LENGTH = 10


class Client(object):
  def __init__(self, socket, address):
    self.socket: socket.socket = socket
    self.address: Address = address
    self.raw_header: bytes = b''
    self.raw_username: bytes = b''
    self.header: str = ''
    self.username: str = ''

  def __str__(self) -> str:
    return "{}:{}".format(*self.address)

  def set_header(self, header):
    self.raw_header = header
    self.header = header.decode("utf-8")

  def set_username(self, username):
    self.raw_username = username
    self.username = username.decode("utf-8")

  def is_master(self) -> bool:
    logging.debug("is_master(): {}, {}".format(self.username, settings.CLIENT_CONTAINER_NAME))
    return self.username == settings.CLIENT_CONTAINER_NAME


class UndefinedClient(Client):
  def is_master(self):
    return False


class Server(object):
  def __init__(self, host: str, port: int):
    self.host = host
    self.port = port
    self.clients: Dict = {}
    self.master: Client = UndefinedClient("", -1)
    self.server_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.server_socket.bind((self.host, self.port))
    self.sockets = [self.server_socket]

  def serve_forever(self):
    logging.info("Listening on {}:{}".format(self.host, self.port))
    self.server_socket.listen()
    while True:
      read, _, exception = select.select(self.sockets, [], self.sockets)
      self.read_sockets = read
      self.exception_sockets = exception
      for notified_socket in self.read_sockets:
        # New connection
        if notified_socket == self.server_socket:
          client_socket, client_address = self.server_socket.accept()
          client = Client(client_socket, client_address)
          payload = self.receive_message(client)
          if not payload:
            logging.info("{}: Payload empty, connection closed".format(client))
            continue
          client.set_header(payload["header"])
          client.set_username(payload["data"])
          if client.is_master():
            logging.debug("Master connected")
            self.master = client
          self.sockets.append(client.socket)
          self.clients[client.socket] = client
          logging.info("{}: New connection accepted".format(client))
        else:
          client = self.clients[notified_socket]
          payload = self.receive_message(client)
          if not payload:
            logging.info("{}: Connection closed, removing client".format(client))
            self.sockets.remove(notified_socket)
            del self.clients[notified_socket]
            continue
          logging.info("{}: Notifying other clients by {}".format(client, client.username))
          for client_socket in self.clients:
            if client_socket != notified_socket:
              tmp = "{}{}{}{}".format(
                client.raw_header, client.raw_username,
                payload["header"], payload["data"]
              )
              client_socket.send(tmp.encode("utf-8"))

      for notified_socket in self.exception_sockets:
        logging.info("Removing sockets with exception\t{}:{}".format(*notified_socket.getpeername()))
        self.sockets.remove(notified_socket)
        del self.clients[notified_socket]

  def receive_message(self, client):
    try:
      logging.info("{}: Receiving a message".format(client))
      message_header = client.socket.recv(HEADER_LENGTH)
      if len(message_header) == 0:
        logging.info("{}: No data received, connection has been closed.".format(client))
        return
      message_header_str = self.decode_bytes(message_header)
      message_length = int(message_header_str.strip())
      logging.info("Message length %d", message_length)
      message = client.socket.recv(message_length)
      message_str = self.decode_bytes(message)
      logging.info("{}: Received message\n{}".format(client, message_str))
      return {"header": message_header, "data": message}
    except Exception as e:
      logging.error("{}: Error receiving a message: {}".format(client, e))

  def decode_bytes(self, payload):
    return payload.decode("utf-8")


if __name__ == "__main__":
  format_ = "%(asctime)s %(levelname)s: %(message)s"
  logging.basicConfig(format=format_, level=logging.DEBUG,
                      datefmt="%H:%M:%S")

  server = Server("0.0.0.0", 8000)
  server.serve_forever()
