import logging
import socket
import threading
import queue

from typing import Optional

import settings

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

			logging.info("Entering main loop")
			count = 1
			while self.is_running:
				if not self.send_queue.empty():
					message, opcode = self.send_queue.get()
					_info_message = message if opcode == TEXT else "%d bytes" % len(message)
					logging.info("Sending {} - {}".format(opcode, _info_message))
					self.server.send_message(message, opcode)
				if count % 2000000 == 0:
					self.send_queue.put((b'', CLOSE))
					self.server.state = WebSocketState.CLOSING
				count += 1
		except Exception as e:
			logging.error("Exception in main loop: {}".format(e))
		finally:
			self.is_running = False
			if self.server.state == WebSocketState.OPEN:
				self.try_close_connection()
			self.server.socket.close()

	def receive_message_subroutine(self):
		while self.is_running:
			frame: Frame = self.server.handle_data()
			if frame:
				self.on_message(frame)
		logging.info("Receive message thread stopping")

	def on_message(self, message: Frame):
		logging.info("Received message {} : {}".format(message, message.payload))
		if message.opcode == CLOSE:
			self.is_running = False
			if self.server.state == WebSocketState.CLOSING:
				pass
			else:
				self.server.send_message(b'', CLOSE)
			self.server.state = WebSocketState.CLOSED

	def try_close_connection(self):
		"""
		Try to notify server to close connection.
		Should be used in case of error.

		If this fails, server will close the connection anyway
		while trying to communicate with this client.
		"""
		try:
			# TODO: add payload with 1002? status code
			self.server.send_message(b'', CLOSE)
		except Exception as e:
			logging.error("Error while trying to close connection: {}".format(e))


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.INFO, datefmt="%H:%M:%S")

	client = ClientBase()
	client.run()
	logging.info("Exitting")
