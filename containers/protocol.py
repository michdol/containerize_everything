import socket
import time
import uuid

from typing import Dict

from constants import HEADER_LENGTH, DestinationType, MessageType
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
	def __init__(self, raw_header: bytes, raw_message: bytes, source: uuid.UUID, destination: uuid.UUID,
			destination_type: DestinationType, time_sent: int, message_type: MessageType, message_length: int,
			message: str
		):
		self.raw_header: bytes = raw_header
		self.raw_message: bytes = raw_message
		self.source: uuid.UUID = source
		self.destination: uuid.UUID = destination
		self.destination_type: DestinationType = destination_type
		self.time_sent: int = time_sent
		self.message_type: MessageType = message_type
		self.message_length: int = message_length
		self.message: str = message

	def __str__(self) -> str:
		return f"Request({self.source}/{self.destination_type}{self.destination}:{self.message_type})"

	def payload(self) -> bytes:
		return self.raw_header + self.raw_message


def create_payload(source: uuid.UUID, destination: str, destination_type: DestinationType, message: str,
		message_type: MessageType) -> bytes:
	message_length = len(message)
	now = int(time.time())
	payload = "{source}|{destination_type}|{destination}|{time_sent}|{message_type:02d}|{message_length:010d} {message}".format(
		source=source,
		destination_type=destination_type,
		destination=destination,
		time_sent=now,
		message_type=message_type,
		message_length=message_length,
		message=message
	)
	return payload.encode("utf-8")


def parse_header(header: bytes) -> Dict:
	values = header.decode("utf-8").split("|")
	return {
		"source": uuid.UUID(values[0]),
		"destination": uuid.UUID(values[2]),
		"destination_type": DestinationType(values[1]),
		"time_sent": int(values[3]),
		"message_type": MessageType(int(values[4])),
		"message_length": int(values[5]),
	}
