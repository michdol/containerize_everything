import errno
import logging
import select
import socket
import sys
import threading
import time
import uuid
import queue

from typing import Dict, List, Tuple, Optional

from constants import (
	MessageType,
	DestinationType,
)
from errors import (
	AuthenticationError,
	MasterAlreadyConnectedError,
)
from protocol import (
	Address,
	Connection,
	Client,
	Worker,
	Master,
)
from websocket_protocol import (
	ConnectionClosedError,
	Frame,
	WebSocket,
	WebSocketState,
	PING,
	PONG,
	TEXT,
	CLOSE
)
from settings import (
	CLIENTS,
	WORKERS,
	HEADER_LENGTH,
	DUMMY_UUID,
	SERVER_ADDRESS,
)


class Server(object):
	def __init__(self, host: str, port: int):
		self.id: uuid.UUID = uuid.uuid4()
		self.address: Address = (host, port)
		self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind(self.address)
		self.sockets: List[socket.socket] = [self.socket]

		self.lock = threading.Lock()
		self.master: Optional[Master] = None
		self.clients: Dict[socket.socket, Connection] = {}
		self.clients_index: Dict[uuid.UUID, socket.socket] = {}
		self.workers: Dict[socket.socket, Worker] = {}
		self.messages: queue.Queue = queue.Queue()
		self.event = threading.Event()
		self.main_event = threading.Event()
		self.broadcast_thread = None

	def is_running(self):
		return not self.main_event.is_set()

	def shutdown(self):
		logging.info("Shutting down")
		self.main_event.set()

	def broadcast_subroutine(self):
		logging.info("Starting broadcast subroutine")
		while not self.event.is_set():
			if not self.messages.empty():
				self.dispatch(self.messages.get())
		logging.info("Broadcast subroutine finished")

	def serve_forever(self):
		logging.info("Listening on {}:{}".format(*self.address))
		self.socket.listen()
		self.broadcast_thread = threading.Thread(target=self.broadcast_subroutine, daemon=True)
		self.broadcast_thread.start()

		try:
			logging.debug("Main thread continues")
			while self.is_running():
				read, _, exception = select.select(self.sockets, [], self.sockets)
				for notified_socket in read:
					if notified_socket is self.socket:
						client_socket, address = self.socket.accept()
						self.handle_new_connection(client_socket, address)
					else:
						self.handle_message(notified_socket)
		finally:
			self.socket.shutdown(socket.SHUT_RDWR)
			self.socket.close()
			self.event.set()
			for connection in self.sockets:
				connection.close()
			logging.info("Exiting")

	def handle_new_connection(self, client_socket: socket.socket, address: Address):
		try:
			client = WebSocket(client_socket, address, is_client=True)
			client.handshake()
			if client.handshake_complete:
				logging.info("{} Handshake complete".format(client))
				# TODO: this might should go with lock?
				self.clients[client_socket] = client
				self.sockets.append(client_socket)
		except Exception as e:
			client_socket.close()
			logging.error("Exception handling new connection: {}".format(e))
			self.handle_exception(client_socket, e)

	def handle_message(self, client_socket: socket.socket):
		"""
		https://tools.ietf.org/html/rfc6455#section-5.1

		The server MUST close the connection upon receiving a
		frame that is not masked.  In this case, a server MAY send a Close
		frame with a status code of 1002 (protocol error) as defined in
		Section 7.4.1.
		A server MUST NOT mask any frames that it sends to
		the client.
			A client MUST close a connection if it detects a masked
		frame.  In this case, it MAY use the status code 1002 (protocol
		error) as defined in Section 7.4.1.  (These rules might be relaxed in
		a future specification.)
		"""
		try:
			client = self.clients[client_socket]
			client_message: Frame = client.handle_data()
			logging.info("{} Received {} : {}".format(client, client_message, client_message.payload))

			response: Optional[Tuple[bytes, int]] = None
			if client_message.opcode == PING:
				response = (b'', PONG)
			elif client_message.opcode == TEXT:
				response = self.handle_text(client, client_message)
			elif client_message.opcode == CLOSE:
				self.handle_close(client)

			if response:
				logging.info("{} Sending response {} : {}".format(client, *response))
				client.send_message(*response)
		except Exception as e:
			if isinstance(e, ConnectionClosedError):
				logging.info("{} abnormally closed connection".format(client, e))
				client.state = WebSocketState.CLOSED
			else:
				logging.error("{} Exception handling message: {}".format(client, e))
			self.remove_client(client_socket)
			self.handle_exception(client_socket, e)

	def handle_close(self, client: WebSocket):
		logging.info("{} Closing connection".format(client))
		# Server initiated Close Handshake.
		if client.state == WebSocketState.CLOSING:
			client.state = WebSocketState.CLOSED
			self.remove_client(client.socket)
		# Client initiated Close Handshake. Server must respond with CLOSE
		else:
			client.state = WebSocketState.CLOSED
			client.send_message(b'', CLOSE)
			self.remove_client(client.socket)

	def handle_text(self, client: WebSocket, frame: Frame) -> Tuple[bytes, int]:
		message: bytes = b''
		opcode: int = TEXT
		# Temporary feature for debugging
		if frame.payload == "close":
			logging.debug("{} closing connection".format(client))
			client.state = WebSocketState.CLOSING
			message = b''
			opcode = CLOSE
		else:
			message = b'Ok from server'
		return (message, opcode)

	def remove_client(self, client_socket: socket.socket):
		client = self.clients.get(client_socket)
		if client_socket in self.clients:
			del self.clients[client_socket]
		client_socket.close()
		self.sockets.remove(client_socket)
		logging.info("{} removed".format(client))

	def handle_exception(self, client_socket: socket.socket, error: Exception):
		# TODO: add tests aswell
		# send error response to client
		pass

	"""

	def handle_worker_request(self, worker: Worker, request: Request):
		logging.info("{} Incomming new message {}".format(worker, request))
		self.messages.put(request)

	def handle_master_request(self, request: Request):
		logging.info("{} Incomming new message {}".format(self.master, request))

	def handle_client_request(self, client: Client, request: Request):
		logging.info("{} Incomming new message {}".format(client, request))
		self.messages.put(request)

	def dispatch(self, request: Request):
		recipients = self.get_recipients(request.destination, request.destination_type)
		payload = request.payload()
		logging.info("Sending {} to {} clients".format(request, len(recipients)))
		sent_count = 0
		for client_socket in recipients:
			try:
				client_socket.send(payload)
				sent_count += 1
			except Exception as e:
				client = self.identify_client(client_socket)
				logging.error("Failed to send {} to {}, error: {}".format(request, client, e))
				self.remove_client(client)
		logging.info("Successfully sent {} to {} clients".format(request, sent_count))

	def get_recipients(self, destination: uuid.UUID, destination_type: DestinationType) -> List[socket.socket]:
		recipients = []
		if destination_type == DestinationType.GROUP:
			if destination == CLIENTS:
				recipients = list(self.clients.keys())
			elif destination == WORKERS:
				recipients = list(self.workers.keys())
		elif destination_type == DestinationType.SERVER:
			# Do nothing for now
			pass
		else:
			if destination in self.clients_index:
				recipients.append(self.clients_index[destination])
		return recipients

	def old_remove_client(self, client: Connection):
		try:
			logging.debug("{} Acquiring lock to remove client".format(client))
			self.lock.acquire()
			if isinstance(client, Client) or isinstance(client, Master):
				del self.clients[client.socket]
				del self.clients_index[client.id]
			elif isinstance(client, Worker):
				del self.workers[client.socket]
			if self.master and client is self.master:
				logging.info("{} Master has been removed".format(client))
				self.master = None
			self.sockets.remove(client.socket)
		except Exception as e:
			logging.error("{} Error while removing client {}".format(client, e))
		finally:
			logging.debug("{} Releasing lock after removal".format(client))
			self.lock.release()

	def identify_client(self, client_socket: socket.socket) -> Connection:
		if client_socket in self.clients:
			return self.clients[client_socket]
		elif client_socket in self.workers:
			return self.workers[client_socket]

	"""


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	server = Server(*SERVER_ADDRESS)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		server.shutdown()
