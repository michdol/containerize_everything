import uuid

from enum import Enum, IntEnum


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
