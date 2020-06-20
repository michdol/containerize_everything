import socket
import logging

from custom_types import Address
from constants import MessageType, WorkerStatus, WORKER_HEADER_LENGTH


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

	def header(self):
		return """
		"{message_length}:{message_type}:{status}"
		message_length - total message length
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

	def build_payload(self, message: str, message_type: MessageType) -> bytes:
		padding_character = ""
		header = f"{message_length}:{message_type:02d}:{status:02d}{padding_character:<{WORKER_HEADER_LENGTH}}"
		payload = "{header}\n{message}".format(
			header=header,
			message=message
		)
		return payload.encode('utf-8')
