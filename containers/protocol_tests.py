import uuid

from unittest import main, TestCase, mock

from constants import DestinationType, MessageType
from protocol import Request, create_payload, parse_header
from settings import HEADER_LENGTH


class RequestTest(TestCase):
	def test_string_representation(self):
		source = uuid.UUID("00000000-0000-0000-0000-000000000001")
		destination = uuid.UUID("00000000-0000-0000-0000-000000000002")
		destination_type = DestinationType.CLIENT
		time_sent = 1234567890
		message_type = MessageType.MESSAGE
		message = "Hello"
		message_length = len(message)
		header = f"{source}|{destination_type}|{destination}|{time_sent}|{message_type:02d}|{message_length:010d} "
		request = Request(
			raw_header=header.encode("utf-8"),
			raw_message=message.encode("utf-8"),
			source=source,
			destination=destination,
			destination_type=destination_type,
			time_sent=time_sent,
			message_type=message_type,
			message_length=message_length,
			message=message
		)

		expected = f"Request({source}/{destination_type}{destination}:{message_type})"
		self.assertEqual(str(request), expected)

	def test_payload(self):
		source = uuid.UUID("00000000-0000-0000-0000-000000000001")
		destination = uuid.UUID("00000000-0000-0000-0000-000000000002")
		destination_type = DestinationType.CLIENT
		time_sent = 1234567890
		message_type = MessageType.MESSAGE
		message = "Hello"
		message_length = len(message)
		header = f"{source}|{destination_type}|{destination}|{time_sent}|{message_type:02d}|{message_length:010d} "
		request = Request(
			raw_header=header.encode("utf-8"),
			raw_message=message.encode("utf-8"),
			source=source,
			destination=destination,
			destination_type=destination_type,
			time_sent=time_sent,
			message_type=message_type,
			message_length=message_length,
			message=message
		)

		expected = f"00000000-0000-0000-0000-000000000001|{destination_type}|00000000-0000-0000-0000-000000000002|1234567890|{message_type:02d}|0000000005 Hello"
		payload = request.payload()
		self.assertEqual(payload, expected.encode('utf-8'))


class ProtocolTest(TestCase):

	@mock.patch("protocol.time.time")
	def test_create_payload(self, mock_time):
		mock_time.return_value = 1234567890.0
		source = uuid.UUID("00000000-0000-0000-0000-000000000001")
		destination = uuid.UUID("00000000-0000-0000-0000-000000000002")
		destination_type = DestinationType.CLIENT
		message_type = MessageType.MESSAGE
		message = "Hello"

		payload: bytes = create_payload(source, destination, destination_type, message, message_type)
		expected = f"00000000-0000-0000-0000-000000000001|{destination_type}|00000000-0000-0000-0000-000000000002|1234567890|{message_type:02d}|0000000005 Hello"
		self.assertEqual(payload, expected.encode('utf-8'))

	@mock.patch("protocol.time.time")
	def test_parse_header(self, mock_time):
		mock_time.return_value = 1234567890.0
		source = uuid.UUID("00000000-0000-0000-0000-000000000001")
		destination = uuid.UUID("00000000-0000-0000-0000-000000000002")
		destination_type = DestinationType.CLIENT
		message_type = MessageType.MESSAGE
		message = "Hello"
		payload: bytes = create_payload(source, destination, destination_type, message, message_type)
		test_header = payload[:HEADER_LENGTH]

		header = parse_header(test_header)
		expected = {
			"source": source,
			"destination": destination,
			"destination_type": destination_type,
			"time_sent": 1234567890,
			"message_type": message_type,
			"message_length": 5
		}
		self.assertEqual(header, expected)
