import errno
import hashlib
import itertools
import logging
import six
import socket
import struct
import sys

from base64 import encodebytes as base64encode
from http.server import BaseHTTPRequestHandler
from io import BytesIO
from typing import Dict, Tuple, Optional, List
# https://tools.ietf.org/html/rfc6455#page-27
# https://github.com/dpallot/simple-websocket-server/blob/master/SimpleWebSocketServer/SimpleWebSocketServer.py
# line 270
# https://pymotw.com/2/socket/binary.html

# decoding data from websocket decodeCharArray
# https://gist.github.com/rich20bb/4190781
# https://stackoverflow.com/questions/8125507/how-can-i-send-and-receive-websocket-messages-on-the-server-side

# https://github.com/crossbario/autobahn-python/blob/80fe02de9754b0898d01d31f2252afdcf9ea2764/autobahn/websocket/protocol.py#L2340
# https://github.com/crossbario/autobahn-python/blob/80fe02de9754b0898d01d31f2252afdcf9ea2764/autobahn/websocket/protocol.py#L1798

class WebSocketException(Exception):
	pass


class ConnectionClosedError(WebSocketException):
	pass


class SocketConnectionBroken(WebSocketException):
	pass


def receive_message(client_socket: socket.socket):
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


class HTTPRequest(BaseHTTPRequestHandler):
	def __init__(self, request_text):
		self.rfile = BytesIO(request_text)
		self.raw_requestline = self.rfile.readline()
		self.error_code = self.error_message = None
		self.parse_request()

	def send_error(self, code, message):
		self.error_code = code
		self.error_message = message


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
class WebSocket(object):
	def __init__(self, sock: socket.socket, address: Address):
		self.client_socket = sock
		self.address = address

		self.handshake_complete = False

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

	def create_frame(self, message: bytes, mask: bool, opcode: int=0x1) -> bytes:
		length = len(message)
		# TODO: add fragmentation
		fin, rsv1, rsv2, rsv3, opcode = 1, 0, 0, 0, opcode
		byte_1 = fin << 7 | rsv1 << 6 | rsv2 << 5 | rsv3 << 4 | opcode
		byte_2 = 0
		payload = message
		if mask:
			byte_2 |= 1 << 7
			payload = self.mask_payload(payload)
		length_payload = b''
		if length < 126:
			byte_2 |= length
		elif length < 2**16:
			byte_2 |= 126
			length_payload = struct.pack("!H", length)
		else:
			byte_2 |= 127
			length_payload = struct.pack("!Q", length)

		return b''.join([
			byte_1.to_bytes(1, 'big'),
			byte_2.to_bytes(1, 'big'),
			length_payload,
			payload
		])

	def handle_data(self):
		if self.handshake_complete:
			data = receive_message(self.client_socket)
			message = self.parse_message(data)
			# TODO: decide what to do with the message
			logging.info("Parsed message {}".format(message))
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

	def parse_message(self, data):
		first_byte = data[0]
		# If 1, it is final frame, 0 otherwise
		fin = first_byte >> 7 & 1
		rsv1 = first_byte >> 6 & 1
		rsv2 = first_byte >> 5 & 1
		rsv3 = first_byte >> 4 & 1
		opcode = first_byte & 0x0F

		second_byte = data[1]
		length = self.parse_message_length(data)
		mask, data_first_byte_index = self.parse_mask(data)

		decoded_data = []
		j = 0
		for i in range(data_first_byte_index, len(data)):
			character = data[i] ^ mask[j % 4]
			decoded_data.append(chr(character))
			j += 1
		return ''.join(decoded_data)

	def parse_message_length(self, data: bytes) -> int:
		second_byte = data[1]
		length = second_byte & 0x7F
		message_length: int = 0
		if length <= 125:
			message_length = length
		elif length == 126:
			# Third and fourth bytes server as 16-bit unsigned integer
			length_array = data[2:4]
			message_length = struct.unpack_from("!H", length_array)[0]
		elif length == 127:
			length_array = data[2:10]
			message_length = struct.unpack_from("!Q", length_array)[0]
		return message_length

	def parse_mask(self, data: bytes) -> Optional[Tuple[List[bytes], int]]:
		"""
		TODO: docstring
		"""
		second_byte = data[1]
		is_masked = second_byte >> 7 & 1
		if not is_masked:
			raise ValueError("Message from client must be masked")
		length = second_byte & 0x7F
		mask_first_byte_index = 2
		if length == 126:
			mask_first_byte_index = 4
		elif length == 127:
			mask_first_byte_index = 10
		mask = data[mask_first_byte_index:mask_first_byte_index + 4] if is_masked else None
		data_first_byte_index = mask_first_byte_index + 4 if is_masked else mask_first_byte_index
		return mask, data_first_byte_index

	def mask_payload(self, payload: bytes):
		mask = struct.pack("!I", random.getrandbits(32))
		return bytes(b ^ m for b, m in zip(payload, itertools.cycle(mask)))
