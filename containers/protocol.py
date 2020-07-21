import errno
import logging
import socket
import time
import uuid

from typing import Dict, Tuple

from constants import DestinationType, MessageType
from settings import HEADER_LENGTH


Address = Tuple[str, int]


class Connection(object):
	def __init__(self, id_: uuid.UUID, sock: socket.socket, address: Address):
		self.id: uuid.UUID = id_
		self.socket: socket.socket = sock
		self.address: Address = address

	def __str__(self) -> str:
		return "Connection({})".format(self.id)


class Client(Connection):
	def __str__(self) -> str:
		return "Client({})".format(self.id)


class Master(Connection):
	def __str__(self) -> str:
		return "Master({})".format(self.id)


class Worker(Connection):
	def __str__(self) -> str:
		return "Worker({})".format(self.id)


message = {
	"type": "int [authentication, info, message]",
	"payload": "Union[bytes, str]",
	"destination": "Union[ID, Group]",
	"status": "ClientStatus[Waiting, Busy]",
}
