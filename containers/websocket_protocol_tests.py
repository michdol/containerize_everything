import errno
import random
import socket
import struct

from base64 import encodebytes as base64encode
from unittest import main, TestCase, mock

from websocket_protocol import (
	WebSocket,
	WebSocketState,
	Frame,
	FrameMaskError,
	WebSocketException,
	ConnectionClosedError,
	SocketConnectionBroken,
	SERVER_HANDSHAKE_RESPONSE,
	SERVER_HANDSHAKE_FAILED_RESPONSE,
	TEXT,
	CLOSE,
)


MOCK_HANDSHAKE_REQUEST = b''.join((
	b"GET / HTTP/1.1\r\n",
	b"Host: localhost:8002\r\n",
	b"Connection: Upgrade\r\n",
	b"Pragma: no-cache\r\n",
	b"Cache-Control: no-cache\r\n",
	b"Upgrade: websocket\r\n",
	b"Origin: http://localhost:3000\r\n",
	b"Sec-WebSocket-Version: 13\r\n",
	b"Sec-WebSocket-Key: I2oRAuMYu81nPkQcA3pBKA==\r\n\r\n",
))

MOCK_INVALID_HANDSHAKE_REQUEST = b''.join((
	b"GET / HTTP/1.1\r\n",
	b"Host: localhost:8002\r\n",
	b"Connection: Upgrade\r\n",
	b"Pragma: no-cache\r\n",
	b"Cache-Control: no-cache\r\n",
	b"Upgrade: websocket\r\n",
	b"Origin: http://localhost:3000\r\n",
	b"Sec-WebSocket-Version: 13\r\n\r\n",
))


class FrameTest(TestCase):
	def test_str(self):
		frame = Frame(b'', 1, (0, 0, 0,), TEXT, 5, 1, b'mock_mask', '')
		self.assertEqual(str(frame), "Frame(1:text:1)")

	def test_is_masked(self):
		frame = Frame(b'', 1, (0, 0, 0,), TEXT, 5, 1, b'mock_mask', '')
		self.assertTrue(frame.is_masked)

		frame = Frame(b'', 1, (0, 0, 0,), TEXT, 5, 1, None, '')
		self.assertFalse(frame.is_masked)
		frame = Frame(b'', 1, (0, 0, 0,), TEXT, 5, 1, b'', '')
		self.assertFalse(frame.is_masked)

	def test_parse_frame_from_client(self):
		"""
		Expected: a proper client Frame object returned
		"""
		message = b"Hello"
		masked_payload, mask = Frame.mask_payload(message)
		# Fin set to 1 and opcode for text
		first_byte = (1 << 7 | 0x01).to_bytes(1, 'big')
		# Mask bit set to 1 and length of a message
		length_byte = (1 << 7 | len(message)).to_bytes(1, 'big')
		data = b''.join([first_byte, length_byte, mask, masked_payload])
		frame = Frame.parse_frame(data, is_client_frame=True)

		self.assertEqual(frame.frame, data)
		self.assertEqual(frame.fin, 1)
		self.assertEqual(frame.rsv1, 0)
		self.assertEqual(frame.rsv2, 0)
		self.assertEqual(frame.rsv3, 0)
		self.assertEqual(frame.opcode, TEXT)
		self.assertEqual(frame.length, 5)
		self.assertEqual(frame.mask, mask)
		self.assertEqual(frame.data_first_byte_index, 6)
		self.assertEqual(frame.payload, "Hello")

	def test_parse_frame_from_client_not_masked(self):
		"""
		All frames from client must be masked.
		Expected: a ValueError to be raised
		"""
		message = b"Hello"
		# Fin set to 1 and opcode for text
		first_byte = (1 << 7 | 0x01).to_bytes(1, 'big')

		# Mask bit set to 0 and length of a message
		length_byte = (0 << 7 | len(message)).to_bytes(1, 'big')
		data = b''.join([first_byte, length_byte, message])

		with self.assertRaises(ValueError) as e:
			Frame.parse_frame(data, is_client_frame=True)

	def test_parse_frame_from_server(self):
		"""
		Expected: a proper server Frame object returned
		"""
		message = b"Hello"
		# Fin set to 1 and opcode for text
		first_byte = (1 << 7 | 0x01).to_bytes(1, 'big')
		# Mask bit set to 0 and length of a message
		length_byte = (0 << 7 | len(message)).to_bytes(1, 'big')
		data = b''.join([first_byte, length_byte, message])
		frame = Frame.parse_frame(data, is_client_frame=False)

		self.assertEqual(frame.frame, data)
		self.assertEqual(frame.fin, 1)
		self.assertEqual(frame.rsv1, 0)
		self.assertEqual(frame.rsv2, 0)
		self.assertEqual(frame.rsv3, 0)
		self.assertEqual(frame.opcode, TEXT)
		self.assertEqual(frame.length, 5)
		self.assertIsNone(frame.mask)
		self.assertEqual(frame.data_first_byte_index, 2)
		self.assertEqual(frame.payload, "Hello")

		# Long message

		message = b"a" * 300
		# Fin set to 1 and opcode for text
		first_byte = (1 << 7 | 0x01).to_bytes(1, 'big')
		# Mask bit set to 0 and length of a message
		length_byte = (0 << 7 | 126).to_bytes(1, 'big')
		length_byte += struct.pack("!H", len(message))
		data = b''.join([first_byte, length_byte, message])
		frame = Frame.parse_frame(data, is_client_frame=False)

		self.assertEqual(frame.frame, data)
		self.assertEqual(frame.fin, 1)
		self.assertEqual(frame.rsv1, 0)
		self.assertEqual(frame.rsv2, 0)
		self.assertEqual(frame.rsv3, 0)
		self.assertEqual(frame.opcode, TEXT)
		self.assertEqual(frame.length, 300)
		self.assertIsNone(frame.mask)
		self.assertEqual(frame.data_first_byte_index, 4)
		self.assertEqual(frame.payload, "a" * 300)

	def test_parse_frame_from_server_masked(self):
		"""
		All frames from server must not be masked.
		Expected: a ValueError to be raised
		"""
		message = b"Hello"
		# Fin set to 1 and opcode for text
		first_byte = (1 << 7 | 0x01).to_bytes(1, 'big')

		# Mask bit set to 1 and length of a message
		length_byte = (1 << 7 | len(message)).to_bytes(1, 'big')
		data = b''.join([first_byte, length_byte, message])

		with self.assertRaises(ValueError) as e:
			Frame.parse_frame(data, is_client_frame=False)

	def test_parse_message_length_frame_not_masked(self):
		data = bytearray([0x81, 0x7D])
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 125)
		self.assertEqual(index, 2)

		# 16-bit integer
		data = bytearray([0x81, 0x7E]) + struct.pack("!H", 126)
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 126)
		self.assertEqual(index, 4)

		data = bytearray([0x81, 0x7E]) + struct.pack("!H", 2**16 - 1)
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 65535)
		self.assertEqual(index, 4)

		# 64-bit integer 
		data = bytearray([0x81, 0x7F]) + struct.pack("!Q", 2**16)
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 65536)
		self.assertEqual(index, 10)

		data = bytearray([0x81, 0x7F]) + struct.pack("!Q", 2**64 - 1)
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 2**64 - 1)
		self.assertEqual(index, 10)

	def test_parse_message_length_frame_masked(self):
		data = bytearray([0x81, 1 << 7 | 0x7D])
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 125)
		self.assertEqual(index, 6)

		# 16-bit integer
		data = bytearray([0x81, 1 << 7 | 0x7E]) + struct.pack("!H", 126)
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 126)
		self.assertEqual(index, 8)

		data = bytearray([0x81, 1 << 7 | 0x7E]) + struct.pack("!H", 2**16 - 1)
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 65535)
		self.assertEqual(index, 8)

		# 64-bit integer 
		data = bytearray([0x81, 1 << 7 | 0x7F]) + struct.pack("!Q", 2**16)
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 65536)
		self.assertEqual(index, 14)

		data = bytearray([0x81, 1 << 7 | 0x7F]) + struct.pack("!Q", 2**64 - 1)
		length, index = Frame.parse_message_length(data)
		self.assertEqual(length, 2**64 - 1)
		self.assertEqual(index, 14)

	def test_parse_mask(self):
		# Message not masked
		mask_bits = struct.pack("!I", random.getrandbits(32))
		data = bytearray([0x81, 0x05]) + mask_bits
		result = Frame.parse_mask(data)
		self.assertIsNone(result)

		# Length less than 126
		mask_bits = struct.pack("!I", random.getrandbits(32))
		data = bytearray([0x81, 0x85]) + mask_bits
		mask = Frame.parse_mask(data)
		self.assertEqual(mask, mask_bits)

		# Length 16-bit integer
		length = struct.pack("!H", 300)
		mask_bits = struct.pack("!I", random.getrandbits(32))
		data = bytearray([0x81, 0xFE]) + length + mask_bits
		mask = Frame.parse_mask(data)
		self.assertEqual(mask, mask_bits)

		# Length 64-bit integer
		length = struct.pack("!Q", 2**16)
		mask_bits = struct.pack("!I", random.getrandbits(32))
		data = bytearray([0x81, 0xFF]) + length + mask_bits
		mask = Frame.parse_mask(data)
		self.assertEqual(mask, mask_bits)

	@mock.patch("websocket_protocol.random.getrandbits")
	def test_create_frame_short_masked(self, mock_randbits):
		randbits = 2095544415
		mock_randbits.return_value = randbits
		message = b'Ok from server'
		expected_data, mock_mask = Frame.mask_payload(message)
		opcode = TEXT
		frame = Frame.create_frame(message, opcode, mask=True)

		expected_frame = b'\x81\x8e' + mock_mask + expected_data
		self.assertEqual(frame.frame, expected_frame)
		self.assertEqual(frame.fin, 1)
		self.assertEqual((frame.rsv1, frame.rsv2, frame.rsv3), (0, 0, 0))
		self.assertEqual(frame.opcode, 1)
		self.assertEqual(frame.length, 14)
		self.assertEqual(frame.data_first_byte_index, 6)
		self.assertEqual(frame.mask, mock_mask)
		self.assertEqual(Frame.decode_data(frame.frame, mock_mask, 6), 'Ok from server')

	def test_create_frame_short_not_masked(self):
		message = b'Ok from server'
		opcode = TEXT
		frame = Frame.create_frame(message, opcode, mask=False)

		self.assertEqual(frame.frame, b'\x81\x0eOk from server')
		self.assertEqual(frame.fin, 1)
		self.assertEqual((frame.rsv1, frame.rsv2, frame.rsv3), (0, 0, 0))
		self.assertEqual(frame.opcode, 1)
		self.assertEqual(frame.length, 14)
		self.assertEqual(frame.data_first_byte_index, 2)
		self.assertEqual(frame.mask, b'')
		self.assertEqual(frame.payload, b'Ok from server')

		self.assertFalse(frame.is_masked)

	def test_create_frame_medium_not_masked(self):
		message = b'a' * 126
		opcode = TEXT
		frame = Frame.create_frame(message, opcode, mask=False)

		self.assertEqual(frame.frame, b'\x81\x7e\x00~' + message)
		self.assertEqual(frame.fin, 1)
		self.assertEqual((frame.rsv1, frame.rsv2, frame.rsv3), (0, 0, 0))
		self.assertEqual(frame.opcode, 1)
		self.assertEqual(frame.length, 126)
		self.assertEqual(frame.data_first_byte_index, 4)
		self.assertEqual(frame.mask, b'')
		self.assertEqual(frame.payload, b'a' * 126)

	def test_create_frame_long_not_masked(self):
		message = b'a' * 65536
		opcode = TEXT
		frame = Frame.create_frame(message, opcode, mask=False)

		self.assertEqual(frame.frame, b'\x81\x7f\x00\x00\x00\x00\x00\x01\x00\x00' + message)
		self.assertEqual(frame.fin, 1)
		self.assertEqual((frame.rsv1, frame.rsv2, frame.rsv3), (0, 0, 0))
		self.assertEqual(frame.opcode, 1)
		self.assertEqual(frame.length, 65536)
		self.assertEqual(frame.data_first_byte_index, 10)
		self.assertEqual(frame.mask, b'')
		self.assertEqual(frame.payload, b'a' * 65536)


class WebSocketTest(TestCase):
	def test_str(self):
		address = ("0.0.0.0", 80)
		ws = WebSocket(socket.socket, address, is_client=False)
		self.assertEqual(str(ws), "WebSocket((\'0.0.0.0\', 80):0)")

	def test_receive_message(self):
		"""
		receive_message requires research
		"""
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.recv.side_effect = [b'mock payload', b'']
		ws = WebSocket(mock_socket, address, is_client=True)

		message: bytes = ws.receive_message()
		self.assertEqual(message, b'mock payload')

	def test_receive_message_socket_error(self):
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.recv.side_effect = [b'mock', b' payload', IOError(errno.EAGAIN, "mock error")]
		ws = WebSocket(mock_socket, address, is_client=True)

		message: bytes = ws.receive_message()
		self.assertEqual(message, b'mock payload')

	def test_receive_message_socket_error_connection_closed(self):
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.recv.side_effect = [b'mock', b' payload', IOError(errno.ECONNRESET, "mock error")]
		ws = WebSocket(mock_socket, address, is_client=True)

		with self.assertRaises(ConnectionClosedError):
			ws.receive_message()

	def test_receive_message_socket_error_other(self):
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.recv.side_effect = [b'mock', b' payload', IOError(errno.EACCES, "mock error")]
		ws = WebSocket(mock_socket, address, is_client=True)

		with self.assertRaises(socket.error):
			ws.receive_message()

	def test_send_buffer(self):
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.send.return_value = 11
		ws = WebSocket(mock_socket, address, is_client=True)

		buff = b'mock buffer'
		ws.send_buffer(buff)
		mock_socket.send.assert_called_with(b'mock buffer')

	def test_send_buffer_connection_broken(self):
		"""
		Expected: SocketConnectionBroken exception raised when no bytes have been sent
		"""
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.send.return_value = 0
		ws = WebSocket(mock_socket, address, is_client=True)

		buff = b'mock buffer'
		with self.assertRaises(SocketConnectionBroken):
			ws.send_buffer(buff)

	def test_send_buffer_socket_error(self):
		"""
		While sending buffer EAGAIN or EWOULDBLOCK exceptions might occur
		Expected: remaining buffer to be returned by the method
		"""
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.send.side_effect = [5, IOError(errno.EAGAIN, "mock error")]
		ws = WebSocket(mock_socket, address, is_client=True)

		buff = b'mock buffer'
		remaining = ws.send_buffer(buff)
		self.assertEqual(remaining, b'buffer')

	def test_send_buffer_socket_error_send_all(self):
		"""
		While sending buffer EAGAIN or EWOULDBLOCK exceptions might occur
		Expected: whole buffer sent due to passing send_all=True to the method
		"""
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.send.side_effect = [5, IOError(errno.EAGAIN, "mock error"), 6]
		ws = WebSocket(mock_socket, address, is_client=True)

		buff = b'mock buffer'
		remaining = ws.send_buffer(buff, send_all=True)
		self.assertIsNone(remaining)

	def test_send_buffer_socket_error_propagation(self):
		"""
		Expected: socket exception raised if different than EAGAIN or EWOULDBLOCK
		"""
		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.send.side_effect = IOError(errno.EACCES, "mock error")
		ws = WebSocket(mock_socket, address, is_client=True)

		with self.assertRaises(IOError):
			ws.send_buffer(b'mock buffer', send_all=True)

	@mock.patch("websocket_protocol.WebSocket.compare_sec_websocket_key")
	def test_send_handshake(self, mock_compare):
		mock_compare.return_value = True

		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.recv.return_value = SERVER_HANDSHAKE_RESPONSE % b'mock hash'
		mock_socket.send.return_value = 151
		ws = WebSocket(mock_socket, address, is_client=True)

		ws.send_handshake()

		self.assertTrue(ws.handshake_complete)
		self.assertEqual(ws.state, WebSocketState.OPEN)
		self.assertEqual(mock_compare.call_args[0][1], b'mock hash')

	@mock.patch("websocket_protocol.WebSocket.compare_sec_websocket_key")
	def test_send_handshake_sec_websocket_key_incorrect(self, mock_compare):
		mock_compare.return_value = False

		address = ("0.0.0.0", 80)
		mock_socket = mock.MagicMock()
		mock_socket.recv.return_value = SERVER_HANDSHAKE_RESPONSE % b'mock hash'
		mock_socket.send.return_value = 151
		ws = WebSocket(mock_socket, address, is_client=True)

		with self.assertRaises(ValueError):
			ws.send_handshake()

	def test_compare_sec_websocket_key(self):
		ws = WebSocket(mock.MagicMock(), ("0.0.0.0", 80), is_client=True)
		raw_key = b'#j\x11\x02\xe3\x18\xbb\xcdg>D\x1c\x03zA('
		key = base64encode(raw_key)[:-1]

		is_equal = ws.compare_sec_websocket_key(key, b'VWTAUcEHWkI7yCMbenHRDkoqqY0=')
		self.assertTrue(is_equal)

		is_equal = ws.compare_sec_websocket_key(key, b'VWTAUcEHWkI7yCMbenHRDkoQqY0=')
		self.assertFalse(is_equal)

	def test_hash_key(self):
		ws = WebSocket(mock.MagicMock(), ("0.0.0.0", 80), is_client=True)
		raw_key = b'#j\x11\x02\xe3\x18\xbb\xcdg>D\x1c\x03zA('
		key = base64encode(raw_key)[:-1]
		hash_ = ws.hash_key(key)
		self.assertEqual(hash_, b'VWTAUcEHWkI7yCMbenHRDkoqqY0=')

	def test_get_sec_websocket_key_from_response(self):
		ws = WebSocket(mock.MagicMock(), ("0.0.0.0", 80), is_client=True)
		response: bytes = SERVER_HANDSHAKE_RESPONSE % b'mock hash'

		key = ws.get_sec_websocket_key_from_response(response)
		self.assertEqual(key, b'mock hash')

	def test_get_sec_websocket_key_from_response_key_missing(self):
		ws = WebSocket(mock.MagicMock(), ("0.0.0.0", 80), is_client=True)
		incorrect_response: bytes = b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: WebSocket\r\nConnection: Upgrade\r\n\r'

		with self.assertRaises(ValueError):
			ws.get_sec_websocket_key_from_response(incorrect_response)

	def test_handle_data_handshake_not_complete(self):
		ws = WebSocket(mock.MagicMock(), ("0.0.0.0", 80), is_client=True)
		with self.assertRaises(WebSocketException):
			ws.handle_data()

	def test_handle_data_no_data(self):
		mock_socket = mock.MagicMock()
		mock_socket.recv.return_value = None
		ws = WebSocket(mock_socket, ("0.0.0.0", 80), is_client=True)
		ws.handshake_complete = True
		ret = ws.handle_data()
		self.assertIsNone(ret)

	@mock.patch("websocket_protocol.WebSocket.send_message")
	@mock.patch("websocket_protocol.Frame.parse_frame")
	def test_handle_data_frame_mask_error(self, mock_frame, mock_send):
		"""
		Expected: close frame sent and exception propagated
		"""
		mock_frame.side_effect = FrameMaskError("Mock exception")
		mock_socket = mock.MagicMock()
		mock_socket.recv.return_value = b'mock buffer'
		ws = WebSocket(mock_socket, ("0.0.0.0", 80), is_client=True)
		ws.handshake_complete = True
		with self.assertRaises(FrameMaskError):
			ws.handle_data()

		mock_send.assert_called_with(b'', CLOSE)

	@mock.patch("websocket_protocol.Frame.parse_frame")
	def test_handle_data_frame_returned(self, mock_parse_frame):
		mock_frame = mock.MagicMock()
		mock_parse_frame.return_value = mock_frame
		mock_socket = mock.MagicMock()
		mock_socket.recv.return_value = b'mock payload'
		ws = WebSocket(mock_socket, ("0.0.0.0", 80), is_client=True)
		ws.handshake_complete = True
		ret = ws.handle_data()
		self.assertIs(ret, mock_frame)

	@mock.patch("websocket_protocol.Frame.create_frame")
	@mock.patch("websocket_protocol.WebSocket.send_buffer")
	def test_send_message(self, mock_send, mock_create_frame):
		mock_frame = mock.MagicMock(frame=b'mock buffer')
		mock_create_frame.return_value = mock_frame
		ws = WebSocket(mock.MagicMock(), ("0.0.0.0", 80), is_client=True)

		ws.send_message(b'this will be disarcded anyway', TEXT)
		mock_send.assert_called_with(b'mock buffer')

	@mock.patch("websocket_protocol.WebSocket.accept_handshake")
	@mock.patch("websocket_protocol.WebSocket.send_handshake")
	def test_handshake(self, mock_send, mock_accept):
		ws = WebSocket(mock.MagicMock(), ("0.0.0.0", 80), is_client=True)

		ws.handshake()
		mock_accept.assert_called()

		ws.is_client = False
		ws.handshake()
		mock_send.assert_called()

	@mock.patch("websocket_protocol.WebSocket.receive_message")
	def test_accept_handshake(self, mock_receive):
		mock_receive.return_value = MOCK_HANDSHAKE_REQUEST
		mock_socket = mock.MagicMock()
		ws = WebSocket(mock_socket, ("0.0.0.0", 80), is_client=True)
		expected_response_key = b'VWTAUcEHWkI7yCMbenHRDkoqqY0='

		ws.accept_handshake()

		self.assertIn(expected_response_key, mock_socket.send.call_args[0][0])
		self.assertTrue(ws.handshake_complete)
		self.assertEqual(ws.state, WebSocketState.OPEN)

	@mock.patch("websocket_protocol.WebSocket.receive_message")
	def test_accept_handshake_no_data(self, mock_receive):
		mock_receive.return_value = None
		mock_socket = mock.MagicMock()
		ws = WebSocket(mock_socket, ("0.0.0.0", 80), is_client=True)

		with self.assertRaises(ConnectionClosedError):
			ws.accept_handshake()

	@mock.patch("websocket_protocol.WebSocket.receive_message")
	@mock.patch("websocket_protocol.WebSocket.send_buffer")
	def test_accept_handshake_failed(self, send_buffer, mock_receive):
		mock_receive.return_value = MOCK_INVALID_HANDSHAKE_REQUEST
		mock_socket = mock.MagicMock()
		ws = WebSocket(mock_socket, ("0.0.0.0", 80), is_client=True)

		with self.assertRaises(AttributeError):
			ws.accept_handshake()

		send_buffer.assert_called_with(SERVER_HANDSHAKE_FAILED_RESPONSE.encode('ascii'), send_all=True)
