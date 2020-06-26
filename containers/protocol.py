import socket

from constants import HEADER_LENGTH
from custom_types import Address


class Connection(object):
	def __init__(self):
		self.id = None
		self.socket: socket.socket = None
		self.address: Address = None

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
	def __init__(self):
		self.raw_header: bytes = b''
		self.raw_message: bytes = b''
		self.source = ""
		self.destination = ""
		self.time_sent = 0
		self.message_type = 0
		self.message_length = 0
		self.message = None

	def __str__(self) -> str:
		return f"Request({self.source}/{self.destination}:{self.message_type})"

	def build_payload(self) -> bytes:
		# TODO: check how to concatenate bytes
		return self.raw_header + self.raw_message


"""
"{source}|{destination}|{time_sent}|{message_type}|{message_length}\n{message}"

source: UUID/Empty UUID (32 characters)
UUID given by server or 00000000-0000-0000-0000-00000000

destination: iUUID/gUUID (33 characters)
i - id of specific entity (client, worker, master)
g - group (Clients, Workers, All)

time_sent: int (10 digits)
Unix timestamp converted to integer (10 digits long)

message_type: int (zero padded 2 digits)
type of the message (command, job result, info, error)

message_length: int (zero padded 10 digits)
length of json string

message: json


HEADER_LENGTH = 91
"""

def build_request(connection: Connection) -> Request:
	"""
	0				 1						 2					 3							4
	{source}|{destination}|{time_sent}|{message_type}|{message_length}\n{message}
	"""
	try:
		logging.debug("{} building request".format(connection))
		header: bytes = connection.socket.recv(HEADER_LENGTH)
		values = [int(value) for value in header.decode("utf-8").split("|")]
		message_length = values[5]
		message: bytes = connection.recv(message_length)
		return Request(
			raw_header=header,
			raw_message=message,
			source=values[0],
			destination=values[1],
			time_sent=values[2],
			message_type=values[3],
			message_length=values[4],
			message=message.decode("utf-8")
		)
	except Exception as e:
		logging.error("{} Error while building request: {}".format(connection, e))
		handle_exception(connection, e)


def handle_exception(connection: Connection, error: Exception):
	pass
