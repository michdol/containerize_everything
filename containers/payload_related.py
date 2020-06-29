import time
import uuid

from typing import Dict

from constants import MessageType, DestinationType


def create_payload(source: uuid.UUID, destination: str, destination_type: DestinationType, message: str, message_type: MessageType) -> bytes:
	message_length = len(message)
	now = int(time.time())
	header = "{source}|{destination_type}{destination}|{time_sent}|{message_type:02d}|{message_length:010d}".format(
		source=source,
		destination_type=destination_type,
		destination=destination,
		time_sent=now,
		message_type=message_type,
		message_length=message_length,
	)
	payload = "{} {}".format(header, message)
	return payload.encode("utf-8")


def parse_header(header: bytes) -> Dict:
	values = header.decode("utf-8").split("|")
	return {
		"source": values[0],
		"destination": values[1],
		"time_sent": int(values[2]),
		"message_type": int(values[3]),
		"message_length": int(values[4]),
	}
