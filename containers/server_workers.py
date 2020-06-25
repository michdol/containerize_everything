import select
import socket
import logging
import queue

from typing import List, Dict

from constants import (
	HEADER_LENGTH,
	WORKER_HEADER_LENGTH,
	SERVER_ADDRESS_WORKERS
)
from custom_types.custom_types import Address, WorkerHeader
from client import Client
from worker import Worker


class WorkersServer(object):
	def __init__(self, host: str, port: int, pipeline: queue.Queue):
		self.address: Address = (host, port)
		self.pipeline: queue.Queue = pipeline
		self.workers: Dict = {}
		self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind(self.address)
		self.sockets: List[socket.socket] = [self.socket]
		self.last_worker_id = 0

	def serve_forever(self):
		logging.info("Workers socket listening on {}:{}".format(*self.address))
		self.socket.listen()
		try:
			while True:
				read, _, exception = select.select(self.sockets, [], self.sockets)
				for notified_socket in read:
					if notified_socket == self.socket:
						worker_socket, worker_address = self.socket.accept()
						worker = Worker(worker_socket, worker_address)
						# TODO: should this expect message here if this is initial connection
						payload: Dict = self.receive_worker_payload(worker)
						if not payload:
							logging.info("{} Payload empty, connection closed".format(worker))
							continue
						self.last_worker_id += 1
						worker.id = self.last_worker_id
						self.sockets.append(worker.socket)
						self.workers[worker.socket] = worker
						logging.info("{} connected\n{}".format(worker, payload))
					else:
						worker: Worker = self.workers[notified_socket]
						payload: Dict = self.receive_worker_payload(worker)
						if not payload:
							logging.info("{} Connection closed, removing".format(worker))
							self.sockets.remove(notified_socket)
							del self.workers[notified_socket]
							notified_socket.close()
							continue
						logging.debug("{} TMP PAYLOAD {}".format(worker, payload))
						# TODO: if results > notify clients
						# if statistics, errors > take server action
						# broadcast_payload = self.get_broadcast_payload
						# send it/append it to some queue that will pass message to other thread
						self.pipeline.set_message("Workers server", payload["message"])
		finally:
			for connection in self.sockets:
				connection.close()

	def get_broadcast_payload(self, client: Client, payload) -> bytes:
		# TODO: this payload sucks
		payload_str = "{username_header!r}{username!r}{payload_header!r}{payload!r}".format(
			username_header=client.raw_header,
			username=client.raw_username,
			payload_header=payload["header"],
			payload=payload["data"]
		)
		return payload_str.encode("utf-8")

	def receive_worker_payload(self, worker: Worker) -> Dict:
		try:
			logging.info("{} Receiving message".format(worker))
			header: bytes = worker.socket.recv(WORKER_HEADER_LENGTH)
			logging.debug("BHEADER: {}".format(header))
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


if __name__ == "__main__":
	"""
	This class should:
	- Have a Command/Job queue/pipeline between this server and worker's server
	- Have a Job Results queue/pipeline between this server and worker's server
	- Handle workers
		Accept connections
		Send out commands from Job queue to workers
		Accept Job Results or Errors and pass it to Client's server

	Command example:
	Workers' status - send current status of each worker like address, status, current job if any etc.
	"""
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG,
											datefmt="%H:%M:%S")

	server = WorkersServer("0.0.0.0", 8001)
	server.serve_forever()
