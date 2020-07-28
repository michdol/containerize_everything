import errno
import json
import logging
import select
import socket
import sys
import threading
import time
import uuid
import queue

from typing import Dict, List, Tuple, Optional

import settings

from constants import MessageType, Command, WorkerStatus, JobName
from server_side_client import ClientWebSocketBase, Worker, ClientError
from websocket_protocol import (
	Address,
	ConnectionClosedError,
	Frame,
	WebSocket,
	WebSocketState,
	PING,
	PONG,
	TEXT,
	CLOSE
)


class Server(object):
	def __init__(self, host: str, port: int):
		self.id: uuid.UUID = uuid.uuid4()
		self.address: Address = (host, port)
		self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind(self.address)
		self.socket.setblocking(False)
		self.sockets: List[socket.socket] = [self.socket]

		self.lock = threading.Lock()
		self.clients: Dict[socket.socket, WebSocket] = {}
		self.workers: Dict[socket.socket, WebSocket] = {}
		self.master: Optional[WebSocket] = None
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
						client_socket.setblocking(False)
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
			client = ClientWebSocketBase(client_socket, address, True, self)
			client.handshake()
			if client.handshake_complete:
				logging.info("{} Handshake complete".format(client))
				# TODO: this might should go with lock?
				self.clients[client_socket] = client
				self.sockets.append(client_socket)
			else:
				logging.info("{} handshake failed".format(address))
		except Exception as e:
			raise e
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
			response = client.handle_message()

			if response:
				logging.info("{} Sending response {} : {}".format(client, *response))
				client.send_message(*response)
		except ClientError as e:
			logging.warning("{} exception: {}".format(client, e))
			self.handle_client_error(client, e)
		except Exception as e:
			raise e
			if isinstance(e, ConnectionClosedError):
				logging.info("{} abnormally closed connection: {}".format(client, e))
				client.state = WebSocketState.CLOSED
			else:
				logging.error("{} Exception handling message: {}".format(client, e))
			self.remove_client(client_socket)
			self.handle_exception(client_socket, e)

	def handle_command(self, payload: bytes):
		"""
		TODO: Append parsed command with arguments to send_queue

		Expected payload format:
		payload = {
			"name": str - name of the job,
			"args": Optional[Union[str, int]] - arguments passed to the job - depends on Job definition
		}
		"""
		# TMP implementation
		workers = [worker for worker in self.clients.values() if isinstance(worker, Worker)]
		logging.info("Sending command to {} workers".format(len(workers)))
		for worker in workers:
			worker.send_message(payload, TEXT)

	def broadcast_message(self, payload: bytes):
		"""
		Append message to send_queue
		"""
		# TMP implementation
		clients = [client for client in self.clients.values() if client.is_recipient]
		logging.info("Sending message to {} clients".format(len(clients)))
		for client in clients:
			client.send_message(payload, TEXT)

	def generate_response(self, type_: MessageType, payload: str) -> bytes:
		response = {
			"type": type_,
			"payload": payload,
		}
		return json.dumps(response).encode('utf-8')

	def handle_close(self, client: WebSocket):
		"""
		https://tools.ietf.org/html/rfc6455#section-7
		"""
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

	def remove_client(self, client_socket: socket.socket):
		client = self.clients.get(client_socket)
		if not client:
			client = self.workers.get(client_socket)
		if client_socket in self.clients:
			del self.clients[client_socket]
		elif client_socket in self.workers:
			del self.workers[client_socket]
		if self.master and client_socket is self.master.socket:
			self.master = None
		client_socket.close()
		self.sockets.remove(client_socket)
		logging.info("{} removed".format(client))

	def handle_exception(self, client_socket: socket.socket, error: Exception):
		# TODO: add tests aswell
		# send error response to client
		pass

	def handle_client_error(self, client: WebSocket, error: ClientError):
		payload = self.generate_response(MessageType.Error, error.args[0])
		client.send_message(payload, TEXT)


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	server = Server(*settings.SERVER_ADDRESS)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		server.shutdown()
