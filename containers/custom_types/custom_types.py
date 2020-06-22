from collections import namedtuple
from typing import Tuple


Address = Tuple[str, int]
WorkerHeader = namedtuple("WorkerHeader", ["message_type", "status", "time_sent", "message_length"])
ServerHeader = namedtuple("ServerHeader", ["message_type", "status", "time_sent", "message_length"])
