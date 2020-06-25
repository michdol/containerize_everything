import select
import socket
import logging
import threading
import queue

from time import sleep
from typing import List, Dict, Optional

from constants import (
	HEADER_LENGTH,
	WORKER_HEADER_LENGTH,
	SERVER_ADDRESS_WORKERS
)
from custom_types.custom_types import Address, WorkerHeader
from client import Client
from worker import Worker


class ClientsServer(object):
	def __init__(self, host: str, port: int, pipeline: queue.Queue):
		self.address: Address = (host, port)
		self.pipeline: queue.Queue = pipeline
		self.event: threading.Event = threading.Event()
		self.clients: Dict = {}
		self.master: Optional[Client] = None
		self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind(self.address)
		self.sockets: List[socket.socket] = [self.socket]

	def serve_forever(self):
		logging.info("Clients socket listening on {}:{}".format(*self.address))
		self.socket.listen()
		consume_job = threading.Thread(target=self.consume)
		consume_job.start()
		try:
			while True:
				read, _, exception = select.select(self.sockets, [], self.sockets)
				logging.debug("MASTER: {}".format(self.master))
				for notified_socket in read:
					# New connection
					if notified_socket is self.socket:
						client_socket, client_address = self.socket.accept()
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

					for notified_socket in exception:
						logging.info("Removing sockets with exception\t{}:{}".format(*notified_socket.getpeername()))
						self.sockets.remove(notified_socket)
						del self.clients[notified_socket]
						notified_socket.close()
		finally:
			for connection in self.sockets:
				connection.close()
			self.event.set()

	def broadcast(self, client: Client, payload):
		for client_socket in self.clients:
			if client_socket != client.socket:
				client_socket.send(payload)

	def get_broadcast_payload(self, client: Client, payload) -> bytes:
		# TODO: this payload sucks
		payload_str = "{username_header}{username}{payload_header}{payload}".format(
			username_header=client.raw_header.decode('utf-8'),
			username=client.raw_username.decode('utf-8'),
			payload_header=payload["header"].decode("utf-8"),
			payload=payload["data"].decode("utf-8")
		)
		return payload_str.encode("utf-8")

	def broadcast_worker_payload(self, worker: Worker, payload: Dict):
		message_type = payload["header"].message_type
		# data = worker.build_payload(payload["message"], message_type)
		data = ""
		for client_socket in self.clients:
			client_socket.send(data)

	def receive_message(self, client: Client) -> Dict[str, bytes]:
		try:
			logging.info("{}: Receiving a message".format(client))
			message_header: bytes = client.socket.recv(HEADER_LENGTH)
			if len(message_header) == 0:
				logging.info("{}: No data received, connection has been closed.".format(client))
				return {}
			message_length = int(message_header.decode("utf-8"))
			logging.info("Message length {}".format(message_length))
			message: bytes = client.socket.recv(message_length)
			logging.info("{}: Received message\n{}".format(client, message.decode("utf-8")))
			return {"header": message_header, "data": message}
		except Exception as e:
			logging.error("{}: Error receiving a message: {}".format(client, e))
			return {}

	def receive_worker_payload(self, worker: Worker) -> Dict:
		try:
			logging.info("{} Receiving message".format(worker))
			header: bytes = worker.socket.recv(WORKER_HEADER_LENGTH)
			if len(header) == 0:
				logging.info("{} No data received, connection has been closed".format(worker))
				return {}
			parsed_header: WorkerHeader = self.parse_worker_header(header)
			logging.debug("{} Parsed {}".format(worker, parsed_header))
			message: bytes = worker.socket.recv(parsed_header.message_length)
			return {"header": parsed_header, "message": message.decode("utf-8")}
		except Exception as e:
			logging.error("{} Error receiving message: {}".format(worker, e))
			return {}

	def parse_worker_header(self, header: bytes) -> WorkerHeader:
		# TODO: check Python typing Optional
		values = header.decode("utf-8").strip().split("|")
		return WorkerHeader(*[int(v) for v in values])

	def consume(self):
		while not self.event.is_set():
			if not self.pipeline.empty():
				message: str = self.pipeline.get_message("Client server")
				payload = self.prep_payload(message)
				for client_socket in self.clients:
					client_socket.send(payload)
			sleep(1)

	def prep_payload(self, message: str) -> bytes:
		username = "tmp name"
		return f"{len(username):<{HEADER_LENGTH}}{username}{len(message)}{message}".encode('utf-8')

if __name__ == "__main__":
	"""
	This class should:
	- Have a Command/Job queue/pipeline between this server and worker's server
	- Have a Job Results queue/pipeline between this server and worker's server
	- handle clients
		Accept connections
		Send data from queue/pipeline
	- handle master client
		Accept commands from master
		Return message errors in case of errors
	"""
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG,
											datefmt="%H:%M:%S")

	server = ClientsServer("0.0.0.0", 8000)
	server.serve_forever()
