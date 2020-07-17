import random
import struct

from unittest import main, TestCase, mock

from websocket_protocol import WebSocket, Frame, TEXT


class FrameTest(TestCase):
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

	def test_is_masked(self):
		frame = Frame(b'', 1, (0, 0, 0,), TEXT, 5, 1, b'mock_mask', '')
		self.assertTrue(frame.is_masked)

		frame = Frame(b'', 1, (0, 0, 0,), TEXT, 5, 1, None, '')
		self.assertFalse(frame.is_masked)

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
