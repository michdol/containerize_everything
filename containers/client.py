import socket
import logging

import settings

from custom_types import Address


class Client(object):
  def __init__(self, socket, address):
    self.socket: socket.socket = socket
    self.address: Address = address
    self.raw_header: bytes = b''
    self.raw_username: bytes = b''
    self.header: str = ''
    self.username: str = ''

  def __str__(self) -> str:
    return "Client({}:{})".format(*self.address)

  def set_header(self, header):
    self.raw_header = header
    self.header = header.decode("utf-8")

  def set_username(self, username):
    self.raw_username = username
    self.username = username.decode("utf-8")

  def is_master(self) -> bool:
    logging.debug("is_master(): {}, {}".format(self.username, settings.CLIENT_CONTAINER_NAME))
    return self.username == settings.CLIENT_CONTAINER_NAME
