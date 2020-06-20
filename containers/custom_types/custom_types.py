from collections import namedtuple
from typing import Tuple


Address = Tuple[str, int]
WorkerHeader = namedtuple("WorkerHeader", ["message_length", "message_type", "worker_status"])
