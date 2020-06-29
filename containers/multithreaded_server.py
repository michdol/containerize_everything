import logging
import select
import socket
import threading
import uuid
import queue

from typing import Dict, List, Tuple, Optional

from constants import (
	HEADER_LENGTH,
	DUMMY_UUID,
	SERVER_ADDRESS,
	MessageType,
	DestinationType,
)
from custom_types.custom_types import Address, WorkerHeader
from errors import (
	AuthenticationError,
	MasterAlreadyConnectedError,
)
from payload_related import create_payload
from protocol import Request, Connection, Client, Worker, Master


class Server(object):
	def __init__(self, host: str, port: int):
		self.id = uuid.uuid4()
		self.address: Address = (host, port)
		self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind(self.address)
		self.sockets: List[socket.socket] = [self.socket]

		self.master: Optional[Master] = None
		self.clients: Dict[socket.socket, Connection] = {}
		self.workers: Dict[socket.socket, Worker] = {}
		self.messages: queue.Queue = queue.Queue()
		self.event = threading.Event()
		self.broadcast_thread = None

	def broadcast_subroutine(self):
		while not self.event.is_set():
			if not self.messages.empty():
				self.dispatch(self.messages.get())

	def serve_forever(self):
		logging.info("Listening on {}:{}".format(*self.address))
		self.socket.listen()
		try:
			# TODO:
			# - implement simple client/worker scripts
			# - implement basic main functionalities
			# - continue

			#	-	start thread for broadcasting
			# - add broadcasting feature
			# - implement authentication logic
			read, _, exception = select.select(self.sockets, [], self.sockets)
			for notified_socket in self.sockets:
				if notified_socket is self.socket:
					client_socket, address = self.socket.accept()
					self.handle_new_connection(client_socket, address)
				else:
					self.handle_message(notified_socket)
		finally:
			for connection in self.sockets:
				connection.close()
			self.socket.close()

	def handle_new_connection(self, client_socket: socket.socket, address: Address):
		try:
			request: Request = self.build_request(client_socket)
			logging.debug("Received {}".format(request))
			client: Connection = self.authenticate(client_socket, address, request)
			logging.debug("{} connected".format(client))
			response: bytes = create_payload(
				source=self.id,
				destination=client.id,
				destination_type=DestinationType.CLIENT,
				message="connected, ok",
				message_type=MessageType.MESSAGE
			)
			logging.debug("{} sending response {}".format(client, response))
			client.socket.send(response)
		except Exception as e:
			logging.error("Exception while handling new connection {}".format(e))
			self.handle_exception(client_socket, e)

	def build_request(self, client_socket: socket.socket) -> Request:
		"""
		Retrieves and build request from client.
		Retrieval takes place in two stages.
		First - receive request header of specified length (check constants.py).
		Second - receive the message following the head. Message length is specified
						 in the header.

		Example request:
		0				 1															 2					 3							4
		{source}|{destination_type}{destination}|{time_sent}|{message_type}|{message_length} {message}

		source - uuid.UUID (32 characters)
		destination_type - str 'i' or 'g'
									i - id, destination is specific client
									g - group, destination is a group of clients
		destination - uuid.UUID (32 characters)
		time_sent - int (10 digits)
		message_type - int (zero-padded 2 digits) (check constants.py)
		message_length - int (zero-padded 10 digits), length of the message
										 following the header

		Space character separates header with message.
		message - json

		Considering above HEADER_LENGTH constants has been choosen to 100 characters
		including the space separating header from message. Any socket after receiving header
		will have to receive only message without having to worry about the space.

		Args:
			client_socket (socket.socket)

		Returns:
			request (Request)
		"""
		header: bytes = client_socket.recv(HEADER_LENGTH)
		logging.debug("HEADER BYTES {}".format(header))
		values = [value for value in header.decode("utf-8").split("|")]
		logging.debug("VALUES {}".format(values))
		message_length = int(values[4])
		message: bytes = client_socket.recv(message_length)
		return Request(
			raw_header=header,
			raw_message=message,
			source=values[0],
			destination=values[1],
			time_sent=int(values[2]),
			message_type=int(values[3]),
			message_length=int(values[4]),
			message=message.decode("utf-8")  # TODO: should this be json.loads(message)
		)

	def authenticate(self, client_socket: socket.socket, address: Address, request: Request) -> Connection:
		"""
		Authenticate new connection - currently dummy authentication
		Create apropriate client and associate with corrent group
		Add client_socket to self.sockets

		Args:
			client_socket - socket sending its initial request
			address - address of the socket
			request - parsed request sent by the socket

		Returns:
			client (Connection) - authenticated client, worker or master

		Raises:
			MasterAlreadyConnectedError - if Master client has already been connected
			AuthenticationError - in case authentication fails
		"""
		client: Optional[Connection] = None
		id_ = uuid.uuid4()
		if request.message == "I'm a client":
			client = Client(id_=id_, sock=client_socket, address=address)
			self.clients[client_socket] = client
		elif request.message == "I'm a worker":
			client = Worker(id_=id_, sock=client_socket, address=address)
			self.workers[client_socket] = client
		elif request.message == "I'm a master":
			client = Master(id_=id_, sock=client_socket, address=address)
			if not self.master:
				logging.info("{} has connected")
				self.master = client
				self.clients[client_socket] = client
			else:
				raise MasterAlreadyConnectedError("TODO: master attempted connect when already one has been connected")
		else:
			raise AuthenticationError("TODO: unknown user")
		self.sockets.append(client_socket)
		logging.info("{} authenticated".format(client))
		return client

	def handle_message(self, client_socket: socket.socket):
		request: Request = self.build_request(client_socket)
		logging.debug("Received {}".format(request))
		if client_socket in self.workers:
			# self.handle_worker_message(self.workers[client_socket])
			pass
		elif self.master and client_socket is self.master:
			# self.handle_master_message()
			pass
		elif client_socket in self.clients:
			# self.handle_client_message(self.clients[client_socket])
			pass
		else:
			logging.debug("I don't know what to do atm")
		# Broadcast message to request's destination

	def tmp_handle_message(self, client: Connection):
		try:
			request: Request = self.build_request(client.socket)
			logging.debug("Received {}".format(request))
			# TODO:
			# handle each type of client in separate method (thread?)
			client: Connection = self.identify(client_socket)
			logging.debug("{} connected".format(client))
			response: bytes = create_payload(
				source=self.id,
				destination=client.id,
				destination_type=DestinationType.CLIENT,
				message="connected, ok",
				message_type=MessageType.MESSAGE
			)
			logging.debug("{} sending response {}".format(client, response))
			client.socket.send(response)
		except Exception as e:
			logging.error("Exception while handling new connection {}".format(e))
			self.handle_exception(client_socket, e)

	def identify(self, client_socket: socket.socket) -> Connection:
		if client_socket in self.workers:
			return self.workers[client_socket]
		elif client_socket in self.clients:
			return self.clients[client_socket]

	def handle_exception(self, client_socket: socket.socket, error: Exception):
		pass

	def build_response(self, client: Connection, request: Request) -> bytes:
		# Response just with json
		return b''

	def broadcast(self, request: Request):
		pass

	def dispatch(self, request: Request):
		pass


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	server = Server(*SERVER_ADDRESS)
	server.serve_forever()
