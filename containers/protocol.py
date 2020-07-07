import errno
import hashlib
import logging
import socket
import time
import uuid

from base64 import encodebytes as base64encode
from typing import Dict, Tuple

from constants import DestinationType, MessageType
from settings import HEADER_LENGTH


Address = Tuple[str, int]


class Connection(object):
	def __init__(self, id_: uuid.UUID, sock: socket.socket, address: Address):
		self.id: uuid.UUID = id_
		self.socket: socket.socket = sock
		self.address: Address = address

	def __str__(self) -> str:
		return "Connection({})".format(self.id)


class Client(Connection):
	def __str__(self) -> str:
		return "Client({})".format(self.id)


class Master(Connection):
	def __str__(self) -> str:
		return "Master({})".format(self.id)


class Worker(Connection):
	def __str__(self) -> str:
		return "Worker({})".format(self.id)


class Request(object):
	def __init__(self, raw_header: bytes, raw_message: bytes, source: uuid.UUID, destination: uuid.UUID,
			destination_type: DestinationType, time_sent: int, message_type: MessageType, message_length: int,
			message: str
		):
		self.raw_header: bytes = raw_header
		self.raw_message: bytes = raw_message
		self.source: uuid.UUID = source
		self.destination: uuid.UUID = destination
		self.destination_type: DestinationType = destination_type
		self.time_sent: int = time_sent
		self.message_type: MessageType = message_type
		self.message_length: int = message_length
		self.message: str = message

	def __str__(self) -> str:
		return f"Request({self.source}/{self.destination_type}{self.destination}:{self.message_type})"

	def payload(self) -> bytes:
		return self.raw_header + self.raw_message


def create_payload(source: uuid.UUID, destination: uuid.UUID, destination_type: DestinationType, message: str,
		message_type: MessageType) -> bytes:
	message_length = len(message)
	now = int(time.time())
	payload = "{source}|{destination_type}|{destination}|{time_sent}|{message_type:02d}|{message_length:010d} {message}".format(
		source=source,
		destination_type=destination_type,
		destination=destination,
		time_sent=now,
		message_type=message_type,
		message_length=message_length,
		message=message
	)
	return payload.encode("utf-8")


def parse_header(header: bytes) -> Dict:
	values = header.decode("utf-8").split("|")
	return {
		"source": uuid.UUID(values[0]),
		"destination": uuid.UUID(values[2]),
		"destination_type": DestinationType(values[1]),
		"time_sent": int(values[3]),
		"message_type": MessageType(int(values[4])),
		"message_length": int(values[5]),
	}


def handle_handshake(client_socket: socket.socket) -> bytes:
	message = receive_message(client_socket)
	headers = parse_handshake(message.decode("utf-8"))
	hash_ = generate_hash(headers["Sec-WebSocket-Key"])
	res = create_handshake_response(hash_)
	print("res", res)
	return res

def receive_message(client_socket: socket.socket):
	try:
		chunks = []
		bytes_received = 0
		BUFFER = 1024
		while True:
			chunk = client_socket.recv(BUFFER)
			logging.debug("Chunk: {!r}".format(chunk))
			chunks.append(chunk)
			bytes_received += len(chunk)
			if len(chunk) < BUFFER:
				return b''.join(chunks)
	except socket.error as e:
		logging.error("Error: {}".format(e))
		err = e.args[0]
		if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
			logging.info("No more data available, {}".format(chunks))
			# Assume: whole message received, parse it
			return b''.join(chunks)
		else:
			logging.error("Error receiving data {}".format(e))
			sys.exit()


def parse_handshake(handshake: str) -> Dict[str, str]:
	lines = handshake.split("\r\n")
	headers = {}
	# Skip first line with method
	# and two empty lines at the end
	for line in lines[1:-2]:
		try:
			key, value = line.split(": ")
			headers[key] = value
		except ValueError:
			pass
	return headers


def generate_hash(key: str):
	value = (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode('utf-8')
	hashed = base64encode(hashlib.sha1(value).digest()).strip()
	# print()
	# print(key)
	# print(hashed)
	# print()
	return hashed


def handle_message(client_socket: socket.socket) -> bytes:
	message = receive_message(client_socket)
	return try_decode(message)


def create_handshake_response(hash_) -> bytes:
	values = [
		b'HTTP/1.1 101 Switching Protocols',
		b'Upgrade: websocket',
		b'Connection: Upgrade',
		b'Sec-WebSocket-Accept: ' + hash_,
		b'\n\r'
	]
	return b'\n\r'.join(values)


# https://tools.ietf.org/html/rfc6455#page-27
# https://github.com/dpallot/simple-websocket-server/blob/master/SimpleWebSocketServer/SimpleWebSocketServer.py
# line 270
# https://pymotw.com/2/socket/binary.html

# decoding data from websocket decodeCharArray
# https://gist.github.com/rich20bb/4190781
# https://stackoverflow.com/questions/8125507/how-can-i-send-and-receive-websocket-messages-on-the-server-side

def try_decode(data: bytes):
	# TODO: homework - python bitwise operations
	secondByte = data[1]
	length = secondByte & 127
	index_first_mask = 2
	if length == 126:
		index_first_mask = 4
	elif length == 127:
		index_first_mask = 10

	masks = data[index_first_mask:index_first_mask + 4] 	# four bytes starting from index_first_mask
	index_first_data_byte = index_first_mask + 4 	# four bytes further

	decoded_data = []
	j = 0
	print()
	print("len", len(data))
	print(masks, "masks")
	print(secondByte, "secondByte")
	print("index_first_mask", index_first_mask)
	print("data", data)
	print(length)
	# import pdb; pdb.set_trace()
	for i in range(index_first_data_byte, len(data)):
		decoded_data.append(data[i] ^ masks[j % 4])
		j += 1

	return ''.join([chr(c) for c in decoded_data])
