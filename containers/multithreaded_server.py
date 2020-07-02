import errno
import logging
import select
import socket
import sys
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
from protocol import Request, Connection, Client, Worker, Master, create_payload


class Server(object):
	def __init__(self, host: str, port: int):
		self.id = uuid.uuid4()
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

	def broadcast_subroutine(self):
		logging.info("Starting broadcast subroutine")
		while not self.event.is_set():
			if not self.messages.empty():
				self.dispatch(self.messages.get())
		logging.info("Broadcast subroutine finished")

	def handle_new_connection(self, client_socket: socket.socket, address: Address):
		try:
			request: Request = self.build_request(client_socket)
			if not request:
				return
			logging.debug("Received {}".format(request))
			try:
				logging.debug("Acquiring lock to authenticate the client")
				self.lock.acquire()
				logging.debug("Lock acquired")
				client: Connection = self.authenticate(client_socket, address, request)
			finally:
				logging.debug("Releasing lock after authentication")
				self.lock.release()
			logging.info("{} connected".format(client))
			response: bytes = create_payload(
				source=self.id,
				destination=client.id,
				destination_type=DestinationType.CLIENT,
				message="connected, ok",
				message_type=MessageType.INITIAL_CONNECTION
			)
			logging.info("{} sending response {}".format(client, response))
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
		{source}|{destination_type}|{destination}|{time_sent}|{message_type}|{message_length} {message}

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

		Considering above HEADER_LENGTH constants has been choosen to 101 characters
		including the space separating header from message. Any socket after receiving header
		will have to receive only message without having to worry about the space.

		Args:
			client_socket (socket.socket)

		Returns:
			request (Request)
		"""
		try:
			header: bytes = client_socket.recv(HEADER_LENGTH)
			if len(header) == 0:
				return
			logging.debug("Received header: {}".format(header))
			values = [value for value in header.decode("utf-8").split("|")]
			message_length = int(values[5])
			message: bytes = client_socket.recv(message_length)
			destination_type = DestinationType(values[1])
			destination = uuid.UUID(values[2])
			return Request(
				raw_header=header,
				raw_message=message,
				source=uuid.UUID(values[0]),
				destination=destination,
				destination_type=destination_type,
				time_sent=int(values[3]),
				message_type=MessageType(int(values[4])),
				message_length=message_length,
				message=message.decode("utf-8")  # TODO: should this be json.loads(message)
			)
		except socket.error as e:
			err = e.args[0]
			if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
				logging.info("No data available")
			else:
				logging.error("Error receiving data {}".format(e))
				sys.exit()

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
			self.clients_index[client.id] = client_socket
		elif request.message == "I'm a worker":
			client = Worker(id_=id_, sock=client_socket, address=address)
			self.workers[client_socket] = client
		elif request.message == "I'm a master":
			client = Master(id_=id_, sock=client_socket, address=address)
			if not self.master:
				logging.info("{} has connected")
				self.master = client
				self.clients[client_socket] = client
				self.clients_index[client.id] = client_socket
			else:
				raise MasterAlreadyConnectedError("TODO: master attempted connect when already one has been connected")
		else:
			raise AuthenticationError("TODO: unknown user")
		self.sockets.append(client_socket)
		logging.info("{} authenticated".format(client))
		return client

	def handle_message(self, client_socket: socket.socket):
		try:
			request: Request = self.build_request(client_socket)
			client = self.identify_client(client_socket)
			if not request:
				logging.info("{} closed connection, removing".format(client))
				self.remove_client(client)
				return
			# TODO: handle each type of client in separate thread?
			if isinstance(client, Worker):
				self.handle_worker_request(client, request)
			elif client is self.master:
				self.handle_master_request(request)
			else:
				self.handle_client_request(client, request)
		except Exception as e:
			logging.error("Exception while handling message {}".format(e))
			self.handle_exception(client_socket, e)

	def handle_worker_request(self, worker: Worker, request: Request):
		logging.debug("{} Incomming new message {}".format(worker, request))
		self.messages.put(request)

	def handle_master_request(self, request: Request):
		logging.debug("{} Incomming new message {}".format(master, request))

	def handle_client_request(self, client: Client, request: Request):
		logging.debug("{} Incomming new message {}".format(client, request))

	def handle_exception(self, client_socket: socket.socket, error: Exception):
		# TODO: add tests aswell
		pass

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

	def get_recipients(self, destination: uuid.UUID, destination_type: DestinationType):
		recipients = []
		if destination_type == DestinationType.GROUP:
			# Get recipients from a group
			pass
		elif destination_type == DestinationType.SERVER:
			# Do nothing for now
			pass
		else:
			if destination in self.clients_index:
				recipients.append(self.clients_index[destination])
		return recipients

	def remove_client(self, client: Connection):
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


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	server = Server(*SERVER_ADDRESS)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		server.shutdown()
