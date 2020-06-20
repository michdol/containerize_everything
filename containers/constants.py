from enum import IntEnum

from custom_types import Address


HEADER_LENGTH = 10
WORKER_HEADER_LENGTH = 20

SERVER_HOST_NAME = "server"
SERVER_PORT = 8000
SERVER_ADDRESS: Address = (SERVER_HOST_NAME, SERVER_PORT)


class MessageType(IntEnum):
	INITIAL_CONNECTION = 0
	INFO = 1
	WORK_RESULT = 2
	WORK_DONE = 3
	ERROR = 9


class WorkerStatus(IntEnum):
	NOT_CONNECTED = 0
	CONNECTED = 1
	WORKING = 2
	ERROR = 9
