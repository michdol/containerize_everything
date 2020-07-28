from enum import Enum, IntEnum


class WorkerStatus(IntEnum):
	Waiting = 1
	Busy = 2
	Unavailable = 3


class MessageType(IntEnum):
	Authentication = 1
	Info = 2
	Message = 3
	Command = 4
	JobResults = 5
	Error = 9


class Command(IntEnum):
	StartJob = 1
	StopJob = 2
	PauseJob = 3
	Disconnect = 4


class JobName(Enum):
	TestJob = "test_job"
