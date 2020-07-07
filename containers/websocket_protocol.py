import errno
import logging
import socket
import sys
# https://tools.ietf.org/html/rfc6455#page-27
# https://github.com/dpallot/simple-websocket-server/blob/master/SimpleWebSocketServer/SimpleWebSocketServer.py
# line 270
# https://pymotw.com/2/socket/binary.html

# decoding data from websocket decodeCharArray
# https://gist.github.com/rich20bb/4190781
# https://stackoverflow.com/questions/8125507/how-can-i-send-and-receive-websocket-messages-on-the-server-side

BUFFER = 1024
MAGIC_KEY = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

### Server ###
def handle_handshake(client_socket: socket.socket) -> bytes:
	message = receive_message(client_socket)
	headers = parse_handshake(message.decode("utf-8"))
	hash_ = generate_hash(headers["Sec-WebSocket-Key"])
	return create_handshake_response(hash_)


def receive_message(client_socket: socket.socket):
	try:
		chunks = []
		bytes_received = 0
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


def send_message(target_socket: socket.socket):
	pass


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
			# TODO: refactor this
			pass
	return headers


def generate_hash(key: str) -> bytes:
	value = (key + MAGIC_KEY).encode('utf-8')
	return base64encode(hashlib.sha1(value).digest()).strip()


def handle_message(client_socket: socket.socket) -> bytes:
	message: bytes = receive_message(client_socket)
	return decode_message(message)


def create_handshake_response(hash_: bytes) -> bytes:
	values = [
		b'HTTP/1.1 101 Switching Protocols',
		b'Upgrade: websocket',
		b'Connection: Upgrade',
		b'Sec-WebSocket-Accept: ' + hash_,
		b'\n\r'
	]
	return '\n\r'.join(values)


def decode_message(data: bytes):
	# TODO: return response object -> Response
	# TODO: homework - python bitwise operations
	secondByte = data[1]
	length = secondByte & 127
	first_mask_byte_index = 2
	if length == 126:
		first_mask_byte_index = 4
	elif length == 127:
		first_mask_byte_index = 10

	masks = data[first_mask_byte_index:first_mask_byte_index + 4] 	# four bytes starting from first_mask_byte_index
	index_first_data_byte = first_mask_byte_index + 4 	# four bytes further
	first_data_byte_index = 

	decoded_data = []
	j = 0
	for i in range(index_first_data_byte, len(data)):
		character = data[i] ^ masks[j % 4]
		decoded_data.append(chr(character))
		j += 1

	return ''.join(decoded_data)
