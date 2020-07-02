from collections import namedtuple
from typing import Tuple


Address = Tuple[str, int]
Message = namedtuple("Message", [
	"source",
	"destination",
	"destination_type",
	"time_sent",
	"message_type",
	"message_length",
	"message"
])
