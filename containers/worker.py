import socket
import logging

from custom_types import Address
from constants import MessageType, WorkerStatus, WORKER_HEADER_LENGTH, WORKER_HEADER_MESSAGE_LENGTH


class Worker(object):
	def __init__(self, socket, address):
		self.socket: socket.socket = socket
		self.address: Address = address
		self.id: int = 0
		self.status: WorkerStatus = WorkerStatus.NOT_CONNECTED

	def __str__(self) -> str:
		return "Worker'{}({}:{})".format(self.id, *self.address)

	def has_connected(self) -> bool:
		return self.id > 0

	def header_(self, message: str, message_type: MessageType) -> str:
		m_len = f"{len(message):04d}"
		message_length = f"{m_len:<{WORKER_HEADER_MESSAGE_LENGTH}}"
		return f"{message_type}|{status}|{time_sent}|{message_length}"

	def header(self):
		return """
		{message_type}|{status}|{time_sent}|{message_length}
		01|01|1234567890|0123'    '
		2 + 1 + 2 + 1 + 10 + 1 + len(str(len(message)))
		17 + message_length (4)
		message_length padded with 15 spaces making worker header 32 in total


		message_type: int - type of message,
												available types:
													- 0 initial connection - worker connects to the server first time
													- 1 info/statistic - worker's current state, disk usage data, idk.
													- 2 work result - defined work's result, number of works occurrences, etc.
													- 3 work finished - work done, this message follows last work result, should not contain result
													- 9 - errors
		status: int - current status:
									available statuses:
										- 0 - not connected
										- 1 - connected, awaiting command
										- 2 - working
										- 9 - error
		time_sent - unix time
		message_length - total message length
		padding_character - 4 spaces
		"""

	def message(self):
		"""
		Depends on message_type
		"""
		return """
		switch message_type:
		case 0: empty string
		case 1: worker's statistical data
		case 2: work result, depends on work's definition
		case 3: some statistical data, time elapsed, data sent, etc.
		case 9: error type, error message, error dependent
		"""

	def server_response_header(self):
		return """
		2 + 1 + 2 + 10 = 15
		message_length = 4 + 13 padding spaces
		total 32 characters

		{message_type}|{status}|{time_sent}|{message_length}
		message_type: int - type of message,
												available types:
													- 0 initial connection - worker connects to the server first time
													- 1 info/statistic - worker's current state, disk usage data, idk.
													- 2 work result - defined work's result, number of works occurrences, etc.
													- 3 work finished - work done, this message follows last work result, should not contain result
													- 9 - errors
		status: int - current status:
									available statuses:
										- 0 - not connected
										- 1 - connected, awaiting command
										- 2 - working
										- 9 - error
		time_sent - unix time
		message_length - total message length
		"""
