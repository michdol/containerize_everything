import uuid
import threading

from unittest import main, TestCase, mock

from constants import DestinationType, MessageType, HEADER_LENGTH, SERVER_TEST_ADDRESS
from protocol import Request, create_payload, parse_header
from multithreaded_server import Server


class ServerTest(TestCase):
	def setUp(self):
		super().setUp()
		self.server = Server("0.0.0.0", 9999)
		# For now no need for a running server
		"""
		self.server_thread = threading.Thread(target=self.server.serve_forever)
		self.server_thread.start()
		"""

	def tearDown(self):
		super().tearDown()
		self.server.socket.close()
		# For now no need for a running server
		"""
		self.server.shutdown()
		self.server_thread.join()
		assert not self.server_thread.is_alive(), "Server thread not shut down"
		"""

	def test_build_request(self):
		source = uuid.UUID("00000000-0000-0000-0000-000000000001")
		destination = uuid.UUID("00000000-0000-0000-0000-000000000002")
		destination_type = DestinationType.CLIENT
		time_sent = 1234567890
		message_type = MessageType.MESSAGE
		message = "Hello"
		message_length = len(message)
		header = f"{source}|{destination_type}|{destination}|{time_sent}|{message_type:02d}|{message_length:010d} "

		mock_socket = mock.MagicMock()
		mock_socket.recv.side_effect = [
			header.encode('utf-8'),
			message.encode('utf-8'),
		]

		request = self.server.build_request(mock_socket)
		self.assertEqual(request.source, source)
		self.assertEqual(request.destination, destination)
		self.assertEqual(request.destination_type, destination_type)
		self.assertEqual(request.time_sent, time_sent)
		self.assertEqual(request.message_type, message_type)
		self.assertEqual(request.message_length, message_length)
		self.assertEqual(request.message, message)
