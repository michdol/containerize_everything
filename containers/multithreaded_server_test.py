import uuid
import threading

from unittest import main, TestCase, mock

import settings

from constants import DestinationType, MessageType, HEADER_LENGTH, SERVER_TEST_ADDRESS, DUMMY_UUID
from errors import MasterAlreadyConnectedError, AuthenticationError
from protocol import Request, create_payload, parse_header, Client, Worker, Master
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

	@mock.patch("multithreaded_server.uuid.uuid4")
	def test_authenticate_client(self, mock_uuid):
		mock_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_uuid.return_value = mock_id
		mock_request = mock.MagicMock(message="I'm a client")
		mock_socket = mock.MagicMock()
		address = ("100.0.100.1", 1234)

		client = self.server.authenticate(mock_socket, address, mock_request)
		self.assertIsInstance(client, Client)
		self.assertEqual(client.id, mock_id)
		self.assertIs(client, self.server.clients[client.socket])
		self.assertIs(mock_socket, self.server.clients_index[mock_id])
		self.assertEqual(client.address, address)
		self.assertIn(client.socket, self.server.sockets)

	@mock.patch("multithreaded_server.uuid.uuid4")
	def test_authenticate_worker(self, mock_uuid):
		mock_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_uuid.return_value = mock_id
		mock_request = mock.MagicMock(message="I'm a worker")
		mock_socket = mock.MagicMock()
		address = ("100.0.100.1", 1234)

		worker = self.server.authenticate(mock_socket, address, mock_request)
		self.assertIsInstance(worker, Worker)
		self.assertEqual(worker.id, mock_id)
		self.assertIs(worker, self.server.workers[worker.socket])
		self.assertEqual(worker.address, address)
		self.assertIn(worker.socket, self.server.sockets)

	@mock.patch("multithreaded_server.uuid.uuid4")
	def test_authenticate_master(self, mock_uuid):
		mock_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_uuid.return_value = mock_id
		mock_request = mock.MagicMock(message="I'm a master")
		mock_socket = mock.MagicMock()
		address = ("100.0.100.1", 1234)

		master = self.server.authenticate(mock_socket, address, mock_request)
		self.assertIsInstance(master, Master)
		self.assertEqual(master.id, mock_id)
		self.assertIs(master, self.server.clients[master.socket])
		self.assertIs(mock_socket, self.server.clients_index[mock_id])
		self.assertIs(master, self.server.master)
		self.assertEqual(master.address, address)
		self.assertIn(master.socket, self.server.sockets)

	@mock.patch("multithreaded_server.uuid.uuid4")
	def test_authenticate_master_already_authenticated(self, mock_uuid):
		"""
		Only one master should be authenticated at the time.
		"""
		mock_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_uuid.return_value = mock_id
		mock_request = mock.MagicMock(message="I'm a master")
		mock_socket = mock.MagicMock()
		address = ("100.0.100.1", 1234)

		self.server.authenticate(mock_socket, address, mock_request)

		with self.assertRaises(MasterAlreadyConnectedError):
			self.server.authenticate(mock_socket, address, mock_request)

	@mock.patch("multithreaded_server.uuid.uuid4")
	def test_authenticate_failure(self, mock_uuid):
		mock_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_uuid.return_value = mock_id
		mock_request = mock.MagicMock(message="I'm a bot")
		mock_socket = mock.MagicMock()
		address = ("100.0.100.1", 1234)

		with self.assertRaises(AuthenticationError):
			self.server.authenticate(mock_socket, address, mock_request)

	@mock.patch("protocol.time.time")
	@mock.patch("multithreaded_server.uuid.uuid4")
	def test_handle_new_connection(self, mock_uuid, mock_time):
		source = DUMMY_UUID
		destination = DUMMY_UUID
		destination_type = DestinationType.SERVER
		time_sent = 1234567890
		message_type = MessageType.INITIAL_CONNECTION
		message = "I'm a master"
		message_length = len(message)
		header = f"{source}|{destination_type}|{destination}|{time_sent}|{message_type:02d}|{message_length:010d} "
		address = ("100.0.100.1", 1234)

		mock_time.return_value = 1234567890
		mock_client_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_uuid.return_value = mock_client_id
		mock_socket = mock.MagicMock()
		mock_socket.recv.side_effect = [
			header.encode('utf-8'),
			message.encode('utf-8'),
		]

		self.server.handle_new_connection(mock_socket, address)

		expected_message = "connected, ok"
		expected_response = "{source}|{destination_type}|{destination}|{time_sent}|{message_type:02d}|{message_length:010d} {message}".format(
			source=self.server.id,
			destination_type=DestinationType.CLIENT,
			destination=mock_client_id,
			time_sent=1234567890,
			message_type=MessageType.INITIAL_CONNECTION,
			message_length=len(expected_message),
			message=expected_message,
		).encode("utf-8")
		response: bytes = mock_socket.send.mock_calls[0][1][0] 
		self.assertEqual(response, expected_response)

	@mock.patch("multithreaded_server.Server.handle_exception")
	def test_handle_new_connection_exception(self, mock_handler):
		mock_socket = mock.MagicMock()
		exception = ValueError("Spanish Inquisition")
		mock_socket.recv.side_effect = exception
		address = ("100.0.100.1", 1234)

		self.server.handle_new_connection(mock_socket, address)

		mock_handler.assert_called_with(mock_socket, exception)
