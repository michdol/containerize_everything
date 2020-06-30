import socket
import uuid

from constants import HEADER_LENGTH, DestinationType
from custom_types import Address


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


class Request(object):
	# TODO: type hints for message_type and message might be incorrent
	# message_type: MessageType
	# message: json, if exists
	def __init__(self, raw_header: bytes, raw_message: bytes, source: uuid.UUID, destination: uuid.UUID,
			destination_type: DestinationType, time_sent: int, message_type: int, message_length: int,
			message: str
		):
		self.raw_header: bytes = raw_header
		self.raw_message: bytes = raw_message
		self.source: uuid.UUID = source
		self.destination: uuid.UUID = destination
		self.destination_type: DestinationType = destination_type
		self.time_sent: int = time_sent
		self.message_type: int = message_type
		self.message_length: int = message_length
		self.message: str = message

	def __str__(self) -> str:
		return f"Request({self.source}/{self.destination_type}{self.destination}:{self.message_type})"

	def payload(self) -> bytes:
		return self.raw_header + self.raw_message
