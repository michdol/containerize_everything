import select
import socket
import logging

from typing import List, Dict

from constants import HEADER_LENGTH, WORKER_HEADER_LENGTH
from client import Client, UndefinedClient
from worker import Worker


class Server(object):
	def __init__(self, host: str, port: int, workers_port: int):
		self.address: Address = (host, port)
		self.workers_address: Address = (host, workers_port)
		self.clients: Dict = {}
		self.workers: Dict = {}
		self.master: Client = UndefinedClient("", -1)
		self.server_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.clients_socket = socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.workers_socket = socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.clients_socket.bind(self.address)
		self.server_socket.bind(self.workers_address)
		self.sockets: List[socket.socket] = [self.server_socket]
		self.workers_sockets: List[socket.socket] = [self.workers_socket]
		self.last_worker_id = 0

	def serve_forever(self):
		logging.info("Clients socket listening on {}:{}".format(*self.address))
		self.clients_socket.listen()
		logging.info("Workers socket listening on {}:{}".format(*self.workers_address))
		self.workers_socket.listen()
		while True:
			self.handle_clients_socket()
			self.handle_workers_socket()

	def handle_workers_socket(self):
		read, _, exception = select.select(self.workers_sockets, [], self.workers_sockets)
		for notified_socket in read:
			if notified_socket == self.workers_socket:
				worker_socket, worker_address = self.workers_socket.accept()
				worker = Worker(worker_socket, worker_address)
				payload = self.receive_worker_payload(worker)
				if not payload:
					logging.info("{} Payload empty, connection closed".format(worker))
					continue
				self.last_worker_id += 1
				worker.id = self.last_worker_id
				self.workers_sockets.append(worker.socket)
				self.workers[worker.socket] = worker
				logging.info("{} connected")
			else:
				worker: Worker = self.workers[notified_socket]
				payload = self.receive_worker_payload(worker)
				if not payload:
					logging.info("{} Connection closed, removing".format(worker))
					self.workers_sockets.remove(notified_socket)
					del self.workers[notified_socket]
					continue
				logging.debug("{} TMP PAYLOAD {}".format(payload))
				# TODO: if results > notify clients
				# if statistics, errors > take server action

	def handle_clients_socket(self):
		read, _, exception = select.select(self.sockets, [], self.sockets)
		for notified_socket in read:
			# New connection
			if notified_socket == self.clients_socket:
				client_socket, client_address = self.clients_socket.accept()
				client = Client(client_socket, client_address)
				incomming_payload: Dict = self.receive_message(client)
				if not incomming_payload:
					logging.info("{} Payload empty, connection closed".format(client))
					continue
				client.set_header(incomming_payload["header"])
				client.set_username(incomming_payload["data"])
				if client.is_master():
					logging.debug("Master connected")
					self.master = client
				self.sockets.append(client.socket)
				self.clients[client.socket] = client
				logging.info("{} New connection accepted".format(client))
			else:
				client: Client = self.clients[notified_socket]
				incomming_payload: Dict = self.receive_message(client)
				if not incomming_payload:
					logging.info("{} Connection closed, removing client".format(client))
					self.sockets.remove(notified_socket)
					del self.clients[notified_socket]
					continue
				logging.info("{} Notifying other clients by {}".format(client, client.username))
				payload: bytes = self.get_broadcast_payload(client, incomming_payload)
				self.broadcast(client, payload)

			for notified_socket in self.exception_sockets:
				logging.info("Removing sockets with exception\t{}:{}".format(*notified_socket.getpeername()))
				self.sockets.remove(notified_socket)
				del self.clients[notified_socket]

	def broadcast(self, client: Client, payload):
		for client_socket in self.clients:
			if client_socket != client.socket:
				client_socket.send(payload)

	def get_broadcast_payload(self, client: Client, payload) -> bytes:
		# TODO: this payload sucks
		payload_str = "{username_header!r}{username!r}{payload_header!r}{payload!r}".format(
			username_header=client.raw_header,
			username=client.raw_username,
			payload_header=payload["header"],
			payload=payload["data"]
		)
		return payload_str.encode("utf-8")

	def receive_message(self, client: Client) -> Dict[str, bytes]:
		try:
			logging.info("{}: Receiving a message".format(client))
			message_header: bytes = client.socket.recv(HEADER_LENGTH)
			if len(message_header) == 0:
				logging.info("{}: No data received, connection has been closed.".format(client))
				return {}
			message_length = int(message_header.decode("utf-8"))
			logging.info("Message length %d", message_length)
			message: bytes = client.socket.recv(message_length)
			logging.info("{}: Received message\n{}".format(client, message.decode("utf-8")))
			return {"header": message_header, "data": message}
		except Exception as e:
			logging.error("{}: Error receiving a message: {}".format(client, e))
			return {}

	def receive_worker_payload(self, worker: Worker) -> str:
		try:
			logging.info("{} Receiving message".format(worker))
			header: bytes = worker.socket.recv(WORKER_HEADER_LENGTH)
			if len(header) == 0:
				logging.info("{} No data received, connection has been closed".format(worker))
				return ""
		except Exception as e:
			logging.error("{} Error receiving message: {}".format(worker, e))
			return ""

	def parse_worker_header(self, header: str):
		message_length, message_type, status = header.split(":")
		# TODO: define if Message class would be better than plain dict
		# TODO: maybe named tuple


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG,
											datefmt="%H:%M:%S")

	server = Server("0.0.0.0", 8000, 8001)
	server.serve_forever()
