import errno
import hashlib
import itertools
import logging
import random
import six
import socket
import struct
import sys

from base64 import encodebytes as base64encode
from http.server import BaseHTTPRequestHandler
from io import BytesIO
from typing import Dict, Tuple, Optional, List, Union
# https://tools.ietf.org/html/rfc6455#page-27
# https://github.com/dpallot/simple-websocket-server/blob/master/SimpleWebSocketServer/SimpleWebSocketServer.py
# line 270
# https://pymotw.com/2/socket/binary.html

# decoding data from websocket decodeCharArray
# https://gist.github.com/rich20bb/4190781
# https://stackoverflow.com/questions/8125507/how-can-i-send-and-receive-websocket-messages-on-the-server-side

# https://github.com/crossbario/autobahn-python/blob/80fe02de9754b0898d01d31f2252afdcf9ea2764/autobahn/websocket/protocol.py#L2340
# https://github.com/crossbario/autobahn-python/blob/80fe02de9754b0898d01d31f2252afdcf9ea2764/autobahn/websocket/protocol.py#L1798

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


class WebSocketException(Exception):
	pass


class ConnectionClosedError(WebSocketException):
	pass


class SocketConnectionBroken(WebSocketException):
	pass


def receive_message(client_socket: socket.socket) -> Optional[bytes]:
	try:
		chunks: List[bytes] = []
		bytes_received: int = 0
		while True:
			chunk = client_socket.recv(BUFFER_LENGTH)
			chunks.append(chunk)
			bytes_received += len(chunk)
			length: int = len(chunk)
			logging.debug("CHUNK: {!r}".format(chunk))
			if length == 0:
				raise ConnectionClosedError("Client closed connection")
			elif length < BUFFER_LENGTH:
				return b''.join(chunks)
	except socket.error as e:
		logging.error("{} Error: {}".format(e))
		err = e.args[0]
		if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
			logging.info("No more data available, {}".format(chunks))
			# Assume: whole message received, parse it
			return b''.join(chunks)
		else:
			logging.error("Error receiving data {}".format(e))
			sys.exit()


MAGIC_KEY = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

TEXT = 0x01
BINARY = 0x02
CLOSE = 0x8
PING = 0x9
PONG = 0xA

Address = Tuple[str, int]
HANDSHAKE_HEADER_LENGTH = 2048
MAX_HEADER_LENGTH = 65536
BUFFER_LENGTH = 16384

HANDSHAKE_STR = (
	b"HTTP/1.1 101 Switching Protocols\r\n"
	b"Upgrade: WebSocket\r\n"
	b"Connection: Upgrade\r\n"
	b"Sec-WebSocket-Accept: %s\r\n\r\n"
)

FAILED_HANDSHAKE_STR = (
	"HTTP/1.1 426 Upgrade Required\r\n"
	"Upgrade: WebSocket\r\n"
	"Connection: Upgrade\r\n"
	"Sec-WebSocket-Version: 13\r\n"
	"Content-Type: text/plain\r\n\r\n"
	"This service requires use of the WebSocket protocol\r\n"
)

Mask = List[bytes]

class Frame(object):
	OPCODE_STR = {
		TEXT: "text",
		BINARY: "binary",
		CLOSE: "close",
		PING: "ping",
		PONG: "pong",
	}

	def __init__(self, frame: bytes, fin: int, rsv: Tuple[int], opcode: int, length: int,
							 data_byte_idx: int, mask: Optional[Mask], payload: Union[str, bytes]):
		self.frame: bytes = frame
		self.fin: int = fin
		self.rsv1, self.rsv2, self.rsv3 = rsv
		self.opcode: int = opcode
		self.length: int = length
		self.mask: Optional[Mask] = mask
		self.data_first_byte_index = data_byte_idx
		self.payload: str = payload

	def __str__(self) -> str:
		return "Frame({fin}:{opcode}:{is_masked})".format(
			fin=self.fin,
			opcode=self.OPCODE_STR.get(self.opcode, self.opcode),
			is_masked=int(self.is_masked)
		)

	@property
	def is_masked(self) -> bool:
		return self.mask is not None

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
	def parse_mask(data: bytes) -> Optional[Mask]:
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
	def decode_data(data: bytes, mask: bytes, data_index: int) -> str:
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
	def create_frame(cls, message: bytes, mask: bool, opcode: int=TEXT) -> bytes:
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



class HTTPRequest(BaseHTTPRequestHandler):
	def __init__(self, request_text):
		self.rfile = BytesIO(request_text)
		self.raw_requestline = self.rfile.readline()
		self.error_code = self.error_message = None
		self.parse_request()

	def send_error(self, code, message):
		self.error_code = code
		self.error_message = message


class WebSocket(object):
	def __init__(self, server: socket.socket, sock: socket.socket, address: Address):
		self.server: socket.socket = server
		self.client_socket: socket.socket = sock
		self.address: Address = address

		self.handshake_complete: bool = False

	def __str__(self) -> str:
		return "WebSocket({address})".format(address=self.address)

	def send_buffer(self, buff: bytes, send_all: bool = False) -> Optional[bytes]:
		size = len(buff)
		to_send = size
		already_sent = 0

		while to_send > 0:
			try:
				sent = self.client_socket.send(buff[already_sent:])
				if sent == 0:
					raise SocketConnectionBroken("Client closed connection")
				already_sent += sent
				to_send -= sent
			except socket.error as e:
				if e.errno in [errno.EAGAIN, errno.EWOULDBLOCK]:
					if send_all:
						continue
					return buff[alread_sent:]
				else:
					raise e

	def handle_data(self) -> Optional[Frame]:
		if self.handshake_complete:
			data: bytes = receive_message(self.client_socket)
			message: Frame = Frame.parse_frame(data)
			logging.info("Parsed message {}".format(message))
			return message
		else:
			self.handshake()

	def handshake(self):
		data = self.client_socket.recv(HANDSHAKE_HEADER_LENGTH)
		if not data:
			raise ConnectionClosedError()
		if b'\r\n\r\n' in data:
			request = HTTPRequest(data)
			response: bytes = b''
			try:
				key = request.headers['Sec-WebSocket-Key']
				value = (key + MAGIC_KEY).encode('utf-8')
				hash_ = base64encode(hashlib.sha1(value).digest()).strip()
				response: bytes = (HANDSHAKE_STR % hash_)
				logging.debug("Handshake response {}".format(response))
				self.client_socket.send(response)
				self.handshake_complete = True
			except Exception as e:
				response = FAILED_HANDSHAKE_STR.encode('ascii')
				self.send_buffer(response, send_all=True)
				self.client_socket.close()
				raise e
