from __future__ import annotations

import errno
import hashlib
import hmac
import itertools
import logging
import random
import six
import socket
import struct
import sys

from base64 import encodebytes as base64encode
from enum import IntEnum
from http.client import HTTPResponse
from io import BytesIO

from typing import Dict, Tuple, Optional, List, Union
from _http import HTTPRequest, BytesIOSocket


Address = Tuple[str, int]


class WebSocketException(Exception):
	pass


class ConnectionClosedError(WebSocketException):
	pass


class SocketConnectionBroken(WebSocketException):
	pass


class FrameMaskError(WebSocketException):
	pass


MAGIC_KEY = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

TEXT = 0x01
BINARY = 0x02
CLOSE = 0x8
PING = 0x9
PONG = 0xA

HANDSHAKE_HEADER_LENGTH = 2048
MAX_HEADER_LENGTH = 65536
BUFFER_LENGTH = 16384

SERVER_HANDSHAKE_RESPONSE = (
	b"HTTP/1.1 101 Switching Protocols\r\n"
	b"Upgrade: WebSocket\r\n"
	b"Connection: Upgrade\r\n"
	b"Sec-WebSocket-Accept: %s\r\n\r\n"
)

SERVER_HANDSHAKE_FAILED_RESPONSE = (
	"HTTP/1.1 426 Upgrade Required\r\n"
	"Upgrade: WebSocket\r\n"
	"Connection: Upgrade\r\n"
	"Sec-WebSocket-Version: 13\r\n"
	"Content-Type: text/plain\r\n\r\n"
	"This service requires use of the WebSocket protocol\r\n"
)


class Frame(object):
	"""
	https://tools.ietf.org/html/rfc6455#section-5.2

	0                   1                   2                   3
	0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
	+-+-+-+-+-------+-+-------------+-------------------------------+
	|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
	|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
	|N|V|V|V|       |S|             |   (if payload len==126/127)   |
	| |1|2|3|       |K|             |                               |
	+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
	|     Extended payload length continued, if payload len == 127  |
	+ - - - - - - - - - - - - - - - +-------------------------------+
	|                               |Masking-key, if MASK set to 1  |
	+-------------------------------+-------------------------------+
	| Masking-key (continued)       |          Payload Data         |
	+-------------------------------- - - - - - - - - - - - - - - - +
	:                     Payload Data continued ...                :
	+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
	|                     Payload Data continued ...                |
	+---------------------------------------------------------------+
	"""
	OPCODE_STR = {
		TEXT: "text",
		BINARY: "binary",
		CLOSE: "close",
		PING: "ping",
		PONG: "pong",
	}

	def __init__(self, frame: bytes, fin: int, rsv: Tuple[int, int, int], opcode: int, length: int,
							 data_byte_idx: int, mask: Optional[bytes], payload: Union[str, bytes]):
		self.frame: bytes = frame
		self.fin: int = fin
		self.rsv1, self.rsv2, self.rsv3 = rsv
		self.opcode: int = opcode
		self.length: int = length
		self.mask: Optional[bytes] = mask
		self.data_first_byte_index = data_byte_idx
		self.payload: Union[str, bytes] = payload

	def __str__(self) -> str:
		return "Frame({fin}:{opcode}:{is_masked})".format(
			fin=self.fin,
			opcode=self.OPCODE_STR.get(self.opcode, self.opcode),
			is_masked=int(self.is_masked)
		)

	@property
	def is_masked(self) -> bool:
		return bool(self.mask)

	@classmethod
	def parse_frame(cls, data: bytes, is_client_frame=False):
		first_byte = data[0]
		fin: int = first_byte >> 7 & 1
		rsv1: int = first_byte >> 6 & 1
		rsv2: int = first_byte >> 5 & 1
		rsv3: int = first_byte >> 4 & 1
		opcode: int = first_byte & 0x0F

		second_byte = data[1]
		is_masked = second_byte >> 7 & 1
		if is_client_frame and not is_masked:
			raise ValueError("Message from client MUST be masked")
		elif not is_client_frame and is_masked:
			raise ValueError("Message from server MUST not be masked")

		length, data_first_byte_index = cls.parse_message_length(data)
		mask: Optional[bytes] = cls.parse_mask(data)
		decoded_data: str = cls.decode_data(data, mask, data_first_byte_index)

		return Frame(
			frame=data,
			fin=fin,
			rsv=(rsv1, rsv2, rsv3),
			opcode=opcode,
			length=length,
			data_byte_idx=data_first_byte_index,
			mask=mask,
			payload=decoded_data
		)

	@staticmethod
	def parse_message_length(data: bytes) -> Tuple[int, int]:
		second_byte = data[1]
		length = second_byte & 0x7F
		message_length: int = 0
		is_masked = second_byte >> 7 & 1
		data_first_byte_index = 6 if is_masked else 2
		if length <= 125:
			message_length = length
		elif length == 126:
			# Third and fourth bytes server as 16-bit unsigned integer
			length_array = data[2:4]
			message_length = struct.unpack_from("!H", length_array)[0]
			data_first_byte_index += 2
		elif length == 127:
			length_array = data[2:10]
			message_length = struct.unpack_from("!Q", length_array)[0]
			data_first_byte_index += 8
		return message_length, data_first_byte_index

	@staticmethod
	def parse_mask(data: bytes) -> Optional[bytes]:
		"""
		TODO: docstring
		"""
		second_byte = data[1]
		is_masked = second_byte >> 7 & 1
		length = second_byte & 0x7F
		mask_first_byte_index = 2
		if length == 126:
			mask_first_byte_index = 4
		elif length == 127:
			mask_first_byte_index = 10
		return data[mask_first_byte_index:mask_first_byte_index + 4] if is_masked else None

	@staticmethod
	def decode_data(data: bytes, mask: Optional[bytes], data_index: int) -> str:
		if mask:
			decoded_data = []
			j = 0
			for i in range(data_index, len(data)):
				character = data[i] ^ mask[j % 4]
				decoded_data.append(chr(character))
				j += 1
			return ''.join(decoded_data)
		else:
			# TODO: add opcode
			return data[data_index:].decode('utf-8')

	@classmethod
	def create_frame(cls, message: bytes, opcode: int, mask: bool) -> Frame:
		length: int = len(message)
		# TODO: add fragmentation
		fin, rsv1, rsv2, rsv3, opcode = 1, 0, 0, 0, opcode
		byte_1: int = fin << 7 | rsv1 << 6 | rsv2 << 5 | rsv3 << 4 | opcode
		byte_2: int = 0
		payload: bytes = message
		data_first_byte_index: int = 2
		payload_mask: bytes = b''
		if mask:
			byte_2 |= 1 << 7
			payload, payload_mask = cls.mask_payload(payload)
			data_first_byte_index += 4
		length_payload = b''
		if length < 126:
			byte_2 |= length
		elif length < 2**16:
			byte_2 |= 126
			length_payload = struct.pack("!H", length)
			data_first_byte_index += 2
		else:
			byte_2 |= 127
			length_payload = struct.pack("!Q", length)
			data_first_byte_index += 8

		frame: bytes = b''.join([
			byte_1.to_bytes(1, 'big'),
			byte_2.to_bytes(1, 'big'),
			length_payload,
			payload_mask,
			payload
		])
		return Frame(
			frame=frame,
			fin=fin,
			rsv=(rsv1, rsv2, rsv3),
			opcode=opcode,
			length=length,
			data_byte_idx=data_first_byte_index,
			mask=payload_mask,
			payload=payload
		)

	@staticmethod
	def mask_payload(payload: bytes) -> Tuple[bytes, bytes]:
		mask = struct.pack("!I", random.getrandbits(32))
		return bytes(b ^ m for b, m in zip(payload, itertools.cycle(mask))), mask


class WebSocketState(IntEnum):
	CONNECTING = 0
	OPEN = 1
	CLOSING = 2
	CLOSED = 3


class WebSocket(object):
	def __init__(self, sock: socket.socket, address: Address, is_client: bool):
		self.socket: socket.socket = sock
		self.address: Address = address
		self.is_client = is_client

		self.handshake_complete: bool = False
		self.state: WebSocketState = WebSocketState.CONNECTING

	def __str__(self) -> str:
		return "WebSocket({address}:{state})".format(address=self.address, state=self.state)

	def send_message(self, message: bytes, opcode: int):
		frame: Frame = Frame.create_frame(message, opcode, mask=not self.is_client)
		logging.debug("Sending response {} : {!r}".format(frame, frame.payload))
		self.send_buffer(frame.frame)

	def send_buffer(self, buff: bytes, send_all: bool=False) -> Optional[bytes]:
		size = len(buff)
		to_send = size
		already_sent = 0

		while to_send > 0:
			try:
				sent = self.socket.send(buff[already_sent:])
				if sent == 0:
					raise SocketConnectionBroken("Connection has been closed")
				already_sent += sent
				to_send -= sent
			except socket.error as e:
				if e.errno in [errno.EAGAIN, errno.EWOULDBLOCK]:
					if send_all:
						continue
					return buff[already_sent:]
				else:
					raise e
		return None

	def handle_data(self) -> Optional[Frame]:
		if self.handshake_complete:
			data: bytes = self.receive_message(BUFFER_LENGTH)
			if not data:
				return None
			try:
				frame: Frame = Frame.parse_frame(data, is_client_frame=self.is_client)
			except FrameMaskError as e:
				logging.debug("Closing connection with {} - {}".format(self, e.args[0]))
				self.send_message(b'', CLOSE)
				raise e
			logging.debug("Parsed message {} : {!r}".format(frame, frame.payload))
			return frame
		raise WebSocketException("Handshake not complete")

	def receive_message(self, buff: int=BUFFER_LENGTH) -> bytes:
		"""
		This requires non-blocking sockets
		"""
		chunks = bytearray()
		try:
			while len(chunks) < buff:
				chunk = self.socket.recv(buff - len(chunks))
				logging.debug("CHUNK: {!r}".format(chunk))
				if not chunk:
					break
				chunks.extend(chunk)
		except socket.error as e:
			err = e.args[0]
			if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
				logging.debug("No more data available")
				# Assume: whole message received, return it
				pass
			elif err == errno.ECONNRESET:
				raise ConnectionClosedError("Clonnection closed")
			else:
				raise e
		logging.debug("Received {} bytes".format(len(chunks)))
		return bytes(chunks)

	def handshake(self):
		if self.is_client:
			self.accept_handshake()
		else:
			self.send_handshake()

	def accept_handshake(self):
		"""
		TODO: test this on incorrect request
		"""
		data = self.receive_message(HANDSHAKE_HEADER_LENGTH)
		if not data:
			raise ConnectionClosedError("Connection has been closed")
		if b'\r\n\r\n' in data:
			request = HTTPRequest(data)
			response: bytes = b''
			try:
				key: bytes = request.headers['Sec-WebSocket-Key'].strip().encode('utf-8')
				hash_ = self.hash_key(key)
				response: bytes = (SERVER_HANDSHAKE_RESPONSE % hash_)
				logging.debug("Handshake response {!r}".format(response))
				sent = self.socket.send(response)
				self.handshake_complete = True
				self.state = WebSocketState.OPEN
			except Exception as e:
				response = SERVER_HANDSHAKE_FAILED_RESPONSE.encode('ascii')
				self.send_buffer(response, send_all=True)
				raise e

	@staticmethod
	def hash_key(key: bytes) -> bytes:
		sha1 = hashlib.sha1()
		sha1.update(key + MAGIC_KEY)
		return base64encode(sha1.digest()).strip()

	def send_handshake(self):
		# Explicitly wait for response
		self.socket.setblocking(True)
		raw_key = bytes(random.getrandbits(8) for _ in range(16))
		key = base64encode(raw_key)[:-1]
		hostname: bytes = socket.gethostname().encode('utf-8')
		template = (
			b"GET / HTTP/1.1",
			b"Host: %s" % hostname,
			b"Connection: Upgrade",
			b"Upgrade: websocket",
			b"Sec-WebSocket-Version: 13",
			b"Sec-WebSocket-Key: %s\r\n\r\n" % key,
		)
		request: bytes = b'\r\n'.join(template)
		logging.debug("Sending handshake request {!r}".format(request))
		self.send_buffer(request)

		response = self.socket.recv(BUFFER_LENGTH)
		self.socket.setblocking(False)
		response_key: bytes = self.get_sec_websocket_key_from_response(response)
		logging.debug("Server response {}".format(response))
		key_correct = self.compare_sec_websocket_key(key, response_key)
		if not key_correct:
			raise ValueError("Key received from server is incorrect")
		logging.debug("Handshake complete")
		self.handshake_complete = True
		self.state = WebSocketState.OPEN

	def get_sec_websocket_key_from_response(self, response: bytes) -> bytes:
		source = BytesIOSocket(response)
		res = HTTPResponse(source)
		res.begin()
		key: str = res.headers.get('Sec-WebSocket-Accept')
		if not key:
			raise ValueError("Server response is missing Sec-WebSocket-Accept")
		return key.encode('utf-8')

	def compare_sec_websocket_key(self, key: bytes, response_key: bytes) -> bool:
		hashed = self.hash_key(key)
		logging.debug("Comparing {!r} {!r}".format(hashed, response_key))
		return hmac.compare_digest(hashed, response_key)
