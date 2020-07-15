import random
import struct

from unittest import main, TestCase, mock

from websocket_protocol import WebSocket


class WebSocketTest(TestCase):
	def test_parse_message_length(self):
		ws = WebSocket(mock.MagicMock(), ("", 0))
		data = bytearray([0x81, 0x7D])
		length = ws.parse_message_length(data)
		self.assertEqual(length, 125)

		# 16-bit integer
		data = bytearray([0x81, 0x7E]) + struct.pack("!H", 126)
		length = ws.parse_message_length(data)
		self.assertEqual(length, 126)

		data = bytearray([0x81, 0x7E]) + struct.pack("!H", 2**16 - 1)
		length = ws.parse_message_length(data)
		self.assertEqual(length, 65535)

		# 64-bit integer 
		data = bytearray([0x81, 0x7F]) + struct.pack("!Q", 2**16)
		length = ws.parse_message_length(data)
		self.assertEqual(length, 65536)

		data = bytearray([0x81, 0x7F]) + struct.pack("!Q", 2**64 - 1)
		length = ws.parse_message_length(data)
		self.assertEqual(length, 2**64 - 1)

	def test_parse_mask(self):
		ws = WebSocket(mock.MagicMock(), ("", 0))

		# Message not masked
		mask_bits = struct.pack("!I", random.getrandbits(32))
		data = bytearray([0x81, 0x05]) + mask_bits
		result, index = ws.parse_mask(data)
		self.assertIsNone(result)
		self.assertEqual(index, 2)

		# Length less than 126
		mask_bits = struct.pack("!I", random.getrandbits(32))
		data = bytearray([0x81, 0x85]) + mask_bits
		mask, index = ws.parse_mask(data)
		self.assertEqual(mask, mask_bits)
		self.assertEqual(index, 6)

		# Length 16-bit integer
		length = struct.pack("!H", 300)
		mask_bits = struct.pack("!I", random.getrandbits(32))
		data = bytearray([0x81, 0xFE]) + length + mask_bits
		mask, index = ws.parse_mask(data)
		self.assertEqual(mask, mask_bits)
		self.assertEqual(index, 8)

		# Length 64-bit integer
		length = struct.pack("!Q", 2**16)
		mask_bits = struct.pack("!I", random.getrandbits(32))
		data = bytearray([0x81, 0xFF]) + length + mask_bits
		mask, index = ws.parse_mask(data)
		self.assertEqual(mask, mask_bits)
		self.assertEqual(index, 14)
