import uuid
import socket
import threading
import time

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

	def _artificial_lock(self, lock, test_name, timeout=1):
		"""
		Used to acquire lock for test.
		Should be run in separate thread.
		"""
		try:
			lock.acquire()
			time.sleep(timeout)
		except Exception as e:
			print("Failed to acquire lock during test: {}".format(test_name))
		finally:
			lock.release()

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

	def test_get_recipients_destination_type_client(self):
		mock_client_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_socket = mock.MagicMock()
		self.server.clients_index[mock_client_id] = mock_socket

		recipients = self.server.get_recipients(mock_client_id, DestinationType.CLIENT)
		self.assertEqual(recipients, [mock_socket])

		random_id = uuid.UUID("90000000-0000-0000-0000-000000000009")
		recipients = self.server.get_recipients(random_id, DestinationType.CLIENT)
		self.assertEqual(recipients, [])

	def test_dispatch_single_client(self):
		mock_client_1_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_client_1_socket = mock.MagicMock()
		self.server.clients_index[mock_client_1_id] = mock_client_1_socket

		source = uuid.UUID("00000000-0000-0000-0000-000000000000")
		destination = mock_client_1_id
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

		self.server.dispatch(request)

		mock_client_1_socket.send.assert_called_with(request.payload())

	@mock.patch("multithreaded_server.Server.remove_client")
	def test_dispatch_single_client_exception_while_sending(self, mock_remove_client):
		mock_client_1_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_client_1_socket = mock.MagicMock()
		exception = socket.error("Can't send message")
		mock_client_1_socket.send.side_effect = exception
		mock_connection = mock.MagicMock()
		self.server.clients[mock_client_1_socket] = mock_connection
		self.server.clients_index[mock_client_1_id] = mock_client_1_socket

		source = uuid.UUID("00000000-0000-0000-0000-000000000000")
		destination = mock_client_1_id
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

		self.server.dispatch(request)
		mock_remove_client.assert_called_with(mock_connection)

	def test_remove_client(self):
		mock_client_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_client_socket = mock.MagicMock()
		mock_address = ("100.1.100.1", 1234)
		client = Client(mock_client_id, mock_client_socket, mock_address)
		self.server.clients[mock_client_socket] = client
		self.server.clients_index[mock_client_id] = mock_client_socket
		self.server.sockets.append(mock_client_socket)

		self.server.remove_client(client)

		self.assertFalse(self.server.lock.locked())
		self.assertNotIn(mock_client_socket, self.server.clients)
		self.assertNotIn(mock_client_socket, self.server.sockets)
		self.assertNotIn(mock_client_id, self.server.clients)

	def test_remove_client_master(self):
		mock_client_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_client_socket = mock.MagicMock()
		mock_address = ("100.1.100.1", 1234)
		client = Master(mock_client_id, mock_client_socket, mock_address)
		self.server.master = client
		self.server.clients[mock_client_socket] = client
		self.server.clients_index[mock_client_id] = mock_client_socket
		self.server.sockets.append(mock_client_socket)

		self.server.remove_client(client)

		self.assertFalse(self.server.lock.locked())
		self.assertNotIn(mock_client_socket, self.server.clients)
		self.assertNotIn(mock_client_socket, self.server.sockets)
		self.assertNotIn(mock_client_id, self.server.clients)
		self.assertIsNone(self.server.master)

	def test_remove_client_locked(self):
		mock_client_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
		mock_client_socket = mock.MagicMock()
		mock_address = ("100.1.100.1", 1234)
		client = Client(mock_client_id, mock_client_socket, mock_address)
		self.server.clients[mock_client_socket] = client
		self.server.clients_index[mock_client_id] = mock_client_socket
		self.server.sockets.append(mock_client_socket)

		thread_args = (self.server.lock, self.test_remove_client_locked.__name__)
		artificial_lock_thread = threading.Thread(target=self._artificial_lock, args=thread_args)
		artificial_lock_thread.start()
		self.server.remove_client(client)
		artificial_lock_thread.join()

		self.assertFalse(self.server.lock.locked())
		self.assertNotIn(mock_client_socket, self.server.clients)
		self.assertNotIn(mock_client_socket, self.server.sockets)
		self.assertNotIn(mock_client_id, self.server.clients)
