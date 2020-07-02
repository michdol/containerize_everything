import uuid

from enum import Enum, IntEnum

from custom_types import Address


HEADER_LENGTH = 101

HOST_NAME = "server"
SERVER_PORT = 8000
SERVER_ADDRESS: Address = (HOST_NAME, SERVER_PORT)

TEST_HOST_NAME = "test_server"
TEST_SERVER_PORT = 9999
SERVER_TEST_ADDRESS: Address = (TEST_HOST_NAME, TEST_SERVER_PORT)

DUMMY_UUID = "00000000-0000-0000-0000-000000000000"

class MessageType(IntEnum):
	INITIAL_CONNECTION = 0
	INFO = 1
	MESSAGE = 2
	COMMAND = 3
	JOB_RESULT = 4
	ERROR = 9


class DestinationType(str, Enum):
	SERVER = "s"
	CLIENT = "c"
	GROUP = "g"


CLIENTS = uuid.UUID("00000000-0000-0000-0000-000000000000")
WORKERS = uuid.UUID("00000000-0000-0000-0000-000000000001")


class ResponseStatus(IntEnum):
	# Success
	CONNECTION_ACCEPTED = 0
	# Exception
	CONNECTION_REFUSED = 10
	# Other
	UNKNOWN = 20


class WorkerStatus(IntEnum):
	NOT_CONNECTED = 0
	IDLE = 1
	WORKING = 2
	ERROR = 9
