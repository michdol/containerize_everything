import errno
import logging
import socket
import sys
import threading
import uuid
import queue
import time

from typing import Optional, Tuple, Dict

from constants import HEADER_LENGTH, SERVER_ADDRESS, DUMMY_UUID, DestinationType
from custom_types import Address
from constants import MessageType, WorkerStatus
from protocol import create_payload, parse_header


class ClientBase(object):
	def __init__(self, server_address: Address):
		self.id: uuid.UUID = uuid.UUID(DUMMY_UUID)
		self.server_id: Optional[uuid.UUID] = None
		self.server_address: Address = server_address
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.is_connected: bool = False
		self.inbox: queue.Queue = queue.Queue()
		self.outbox: queue.Qeueu = queue.Queue()
		self.main_event = threading.Event()
		self.receive_message_thread = threading.Thread(target=self.receive_message, daemon=True)
		self.send_message_thread = threading.Thread(target=self.send_message, daemon=True)

	def run(self):
		try:
			logging.info("Connection to {}:{}".format(*self.server_address))
			self.socket.connect(self.server_address)
			self.socket.setblocking(False)
			self.receive_message_thread.start()
			self.send_message_thread.start()

			self.connect_to_server()
			while self.is_running():
				# Parse messages if any exist
				# Run jobs
				# Send messages back
				logging.debug("Entered loop")
				self.main_loop()
		except Exception as e:
			logging.error("Exception occurred: {}".format(e))
		finally:
			self.socket.close()
			self.is_connected = False
			logging.info("Exiting")

	def is_running(self):
		return not self.main_event.is_set()

	def shutdown(self):
		self.main_event.set()

	def connect_to_server(self):
		initial_connection_payload: bytes = create_payload(
			source=DUMMY_UUID,  # This should be optional, in case of initial connection ommited
			destination=DUMMY_UUID,
			destination_type=DestinationType.SERVER,
			message="I'm a worker",
			message_type=MessageType.INITIAL_CONNECTION
		)
		logging.info("Sending initial payload: {!r}".format(initial_connection_payload))
		sent_bytes = self.socket.send(initial_connection_payload)
		if sent_bytes == 0:
			raise RuntimeError("Connection with server broken")

		while not self.is_connected:
			if not self.inbox.empty():
				header, message = self.inbox.get()
				if message != "connected, ok":
					logging.error("Failed to connect with server:\nheader: {}\nmessage: {}".format(header, message))
					sys.exit()
				self.server_id = header["source"]
				self.id = header["destination"]
				self.is_connected = True
				logging.info("Successfully connected to {}:{}".format(*self.server_address))
			time.sleep(1)

	def receive_message(self):
		while self.is_running():
			try:
				header: bytes = self.socket.recv(HEADER_LENGTH)
				if len(header) == 0:
					logging.error("Server has closed the connection")
					sys.exit()
				parsed_header = parse_header(header)
				message: bytes = self.socket.recv(parsed_header["message_length"])
				# TODO: this might be better as a Request
				incomming_message = (parsed_header, message.decode("utf-8"))
				logging.info("Received {}".format(incomming_message))
				self.inbox.put(incomming_message)
			except IOError as e:
				if e.errno != errno.EAGAIN and e.errno != errno.EQOULDBLOCK:
					logging.error("Reading error: {}".format(e))
					sys.exit()
				# Didn't receive any data
				continue
			except Exception as e:
				logging.error("Error while receiving a message {}".format(e))
				sys.exit()

	def send_message(self):
		error = None
		while self.is_running():
			try:
				if not self.outbox.empty():
					message = self.outbox.get()
					logging.info("Sending {}".format(message))
					payload = create_payload(
						source=self.id,
						destination=message["destination"],
						destination_type=message["destination_type"],
						message=message["message"],
						message_type=message["message_type"],
					)
					sent_bytes = self.socket.send(payload)
					if sent_bytes == 0:
						error = RuntimeError("Connection with server broken")
						break
			except Exception as e:
				logging.error("Exception while sending a message: {}".format(e))
		if error:
			raise error
		logging.debug("send_message thread finishing")

	def main_loop(self):
		pass


class Client(ClientBase):
	def main_loop(self):
		if not self.inbox.empty():
			message: Tuple[Dict, str] = self.inbox.get()
			logging.info("Read message {}".format(message[1]))
		message = input("Give me input\n")
		if message:
			self.outbox.put({
				"destination": self.server_id,
				"destination_type": DestinationType.SERVER,
				"message": message,
				"message_type": MessageType.MESSAGE
			})



if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	client = Client(SERVER_ADDRESS)
	client.run()
