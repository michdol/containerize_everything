import logging
import select
import socket

from typing import Dict, List, Tuple

from custom_types.custom_types import Address, WorkerHeader


class Server(object):
	def __init__(self, host: str, port: int):
		self.address: Address = (host, port)
		self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind(self.address)
		self.sockets: List[socket.socket] = [self.socket]

		self.clients: Dict = {}
		self.workers: Dict = {}

	def serve_forever(self):
		logging.info("Listening on {}:{}".format(*self.address))
		self.socket.listen()
		try:
			read, _, exception = select.select(self.sockets, [], self.sockets)
			for notified_socket in self.sockets:
				if notified_socket is self.socket:
					client_socket, address = self.socket.accept()
					self.handle_connection(client_socket, address)
				else:
					connection = self.identify(notified_socket)
					self.handle_message(connection)
		finally:
			for connection in self.sockets:
				connection.close()

	def handle_connection(self, connection, address):
		"""
		This should run on separate thread
		Authenticate incomming connection
		Assign id/group
		"""
		pass

	def handle_message(self, connection):
		"""
		Parse custom protocol
		Identify destination
		Forward to broadcast subroutine
		"""
		pass

	def identify(self, socket_: socket.socket):
		"""
		Identify connection
		return Worker/Client/Master
		"""
		pass

"""
TODO:
1. Client entities: Client, Worker, Master
2. Groups
3. self.identify
"""