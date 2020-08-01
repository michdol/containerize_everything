import json
import logging
import socket
import threading
import queue

from typing import Optional, Union

import settings

from constants import MessageType
from websocket_protocol import (
	Address,
	Frame,
	WebSocket,
	WebSocketState,
	CLOSE,
	TEXT,
)


class ClientBase(object):
	def __init__(self):
		self.server: WebSocket = self.create_websocket()
		self.send_queue: queue.Queue = queue.Queue()
		self.is_running: bool = False

		self.receive_message_thread: Optional[threading.Thread] = None
		self.client_type: str = ""
		self.id: int = 0

	def create_websocket(self) -> WebSocket:
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect(settings.SERVER_ADDRESS)
		return WebSocket(sock, settings.SERVER_ADDRESS, is_client=False)

	def run(self):
		logging.info("Run")
		try:
			self.is_running = True
			self.server.handshake()
			logging.info("Handshake complete")

			self.receive_message_thread = threading.Thread(target=self.receive_message_subroutine, daemon=True)
			self.receive_message_thread.start()
			self.authenticate()

			logging.info("Entering main loop")
			while self.is_running:
				if not self.send_queue.empty():
					message, opcode = self.send_queue.get()
					_info_message = message if opcode == TEXT else "%d bytes" % len(message)
					# Suppress constant stream of logs
					if message["type"] != MessageType.Info:
						logging.info("Sending {} - {}".format(opcode, _info_message))
					payload: bytes = json.dumps(message).encode('utf-8')
					self.server.send_message(payload, opcode)
				self.main_loop()
		except Exception as e:
			raise e
			logging.error("Exception in main loop: {}".format(e))
		finally:
			self.is_running = False
			if self.server.state == WebSocketState.OPEN:
				self.try_close_connection()
			self.server.socket.close()

	def main_loop(self):
		pass

	def authenticate(self):
		# TODO: implement authentication
		message: bytes = json.dumps({
			"type": MessageType.Authentication,
			"payload": self.client_type
		}).encode('utf-8')
		self.server.send_message(message, TEXT)

	def receive_message_subroutine(self):
		while self.is_running:
			frame: Frame = self.server.handle_data()
			if frame:
				self._on_message(frame)
		logging.info("Receive message thread stopping")

	def _on_message(self, message: Frame):
		logging.info("Received message {} : {!r}".format(message, message.payload))
		if message.opcode == CLOSE:
			self.is_running = False
			if self.server.state == WebSocketState.CLOSING:
				pass
			else:
				self.server.send_message(b'', CLOSE)
			self.server.state = WebSocketState.CLOSED
			return
		self.on_message(json.loads(message.payload))

	def on_message(self, message: dict):
		if message["type"] == MessageType.Authentication:
			self.id = message["payload"]["id"]

	def try_close_connection(self):
		"""
		Try to notify server to close connection.
		Should be used in case of error.

		If this fails, server will close the connection anyway
		while trying to communicate with this client.
		"""
		try:
			# TODO: add payload with 1002? status code
			logging.info("Trying to close connection")
			self.server.send_message(b'', CLOSE)
		except Exception as e:
			logging.error("Error while trying to close connection: {}".format(e))

	def send_message(self, message: dict, opcode: int):
		self.send_queue.put((message, opcode))

	def respond_with_error(self, reason: str):
		error_message: dict = {
			"type": MessageType.Error,
			"payload": reason
		}
		self.send_message(error_message, TEXT)
