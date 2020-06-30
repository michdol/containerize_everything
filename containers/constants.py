from enum import Enum, IntEnum

from custom_types import Address


HEADER_LENGTH = 100

HOST_NAME = "server"
SERVER_PORT = 8000
SERVER_ADDRESS: Address = (HOST_NAME, SERVER_PORT)


DUMMY_UUID = "00000000-0000-0000-0000-000000000000"

class MessageType(IntEnum):
	INITIAL_CONNECTION = 0
	INFO = 1
	MESSAGE = 2
	ERROR = 9


class DestinationType(str, Enum):
	SERVER = "s"
	CLIENT = "c"
	GROUP = "g"


"""
Client/Worker/Master connects to server
Worker sends some message (work result)
Worker sends info data about itself
Master sends command to start/stop/pause work
Worker sends error

Server broadcasts all info to Client/Master
"""

class ClientGroup(Enum):
	CLIENTS = "00000000-0000-0000-0000-00000000"
	WORKERS = "00000000-0000-0000-0000-00000001"

class ResponseStatus(IntEnum):
	# Success
	CONNECTION_ACCEPTED = 0
	# Exception
	CONNECTION_REFUSED = 10
	# Other
	UNKNOWN = 20


class WorkerStatus(IntEnum):
	NOT_CONNECTED = 0
	CONNECTED = 1
	WORKING = 2
	ERROR = 9
