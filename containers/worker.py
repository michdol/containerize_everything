import errno
import json
import logging
import socket
import sys
import threading
import uuid
import queue
import time

from typing import Optional, Tuple, Dict

from constants import DestinationType
from constants import MessageType, WorkerStatus
from protocol import Address, Request, create_payload, parse_header
from settings import (
	CLIENTS,
	WORKERS,
	HEADER_LENGTH,
	SERVER_ADDRESS,
	DUMMY_UUID,
)
from test_job import JobCounter


class ClientBase(object):
	def __init__(self, server_address: Address, client_type: str=""):
		self.id: uuid.UUID = uuid.UUID(DUMMY_UUID)
		self.server_id: Optional[uuid.UUID] = None
		self.server_address: Address = server_address
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.is_connected: bool = False
		self.inbox: queue.Queue = queue.Queue()
		self.outbox: queue.Queue = queue.Queue()
		self.main_event = threading.Event()
		self.receive_message_thread = threading.Thread(target=self.receive_message, daemon=True)
		self.send_message_thread = threading.Thread(target=self.send_message, daemon=True)
		# TODO: something better than self.client_type
		self.client_type = client_type

	def run(self):
		try:
			logging.info("Connection to {}:{}".format(*self.server_address))
			self.socket.connect(self.server_address)
			self.socket.setblocking(False)
			self.receive_message_thread.start()
			self.send_message_thread.start()

			self.send_initial_request()
			while self.is_running():
				# Parse messages if any exist
				# Run jobs
				# Send messages back
				self.main_loop()
		except Exception as e:
			raise e
			logging.error("Exception occurred: {}".format(e))
		finally:
			self.socket.close()
			self.is_connected = False
			logging.info("Exiting")

	def is_running(self):
		return not self.main_event.is_set()

	def shutdown(self):
		self.main_event.set()

	def send_initial_request(self):
		initial_connection_payload: bytes = create_payload(
			source=DUMMY_UUID,  # This should be optional, in case of initial connection ommited
			destination=DUMMY_UUID,
			destination_type=DestinationType.SERVER,
			message="I'm a {}".format(self.client_type),
			message_type=MessageType.INITIAL_CONNECTION
		)
		logging.info("Sending initial payload: {!r}".format(initial_connection_payload))
		sent_bytes = self.socket.send(initial_connection_payload)
		if sent_bytes == 0:
			raise RuntimeError("Connection with server broken")

		while not self.is_connected:
			if not self.inbox.empty():
				message = self.inbox.get()
				if message.message != "connected, ok":
					logging.error("Failed to connect with server:\nmessage: {}".format(message.message))
					sys.exit()
				self.server_id = message.source
				self.id = message.destination
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
					return
				parsed_header = parse_header(header)
				message: bytes = self.socket.recv(parsed_header["message_length"])
				# TODO: this might be better as a Request
				incomming_message = Request(
					raw_header=header,
					raw_message=message,
					source=parsed_header["source"],
					destination=parsed_header["destination"],
					destination_type=parsed_header["destination_type"],
					time_sent=parsed_header["time_sent"],
					message_type=parsed_header["message_type"],
					message_length=parsed_header["message_length"],
					message=message.decode("utf-8")  # TODO: should this be json.loads(message)
				)
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
	def __init__(self, server_address: Address, client_type):
		super().__init__(server_address, client_type)
		self.sent = False

	def main_loop(self):
		if not self.inbox.empty():
			message: Request = self.inbox.get()
			logging.info("Read message {}: {}".format(message, message.message))
		if not self.sent:
			self.outbox.put({
				"destination": WORKERS,
				"destination_type": DestinationType.GROUP,
				"message": "start work: job_counter",
				"message_type": MessageType.COMMAND
			})
			self.sent = True


class Worker(ClientBase):
	def __init__(self, server_address: Address, client_type: str):
		super().__init__(server_address, client_type)
		self.job_results: queue.Queue = queue.Queue()
		self.job_event = threading.Event()
		self.job_thread: Optional[threading.Thread] = None

	def main_loop(self):
		"""
		1. Main thread
			 - await commands and act accordingly
			 - start / stop jobs
		2. Info thread
			 - every X seconds send MessageType.INFO
		3. Job thread
			 - execute work
			 - send results
		"""
		if not self.inbox.empty():
			message: Request = self.inbox.get()
			logging.info("Read message {}".format(message))
			if message.message_type == MessageType.COMMAND:
				self.process_command(message)
		if not self.job_results.empty():
			result = self.job_results.get()
			self.outbox.put({
				"destination": CLIENTS,
				"destination_type": DestinationType.GROUP,
				"message": json.dumps(result),
				"message_type": MessageType.JOB_RESULT,
			})
		if self.job_thread and self.job_thread.done:
			logging.info("Work finished")
			self.outbox.put({
				"destination": CLIENTS,
				"destination_type": DestinationType.GROUP,
				"message": "job done",
				"message_type": MessageType.JOB_RESULT,
			})
			self.job_thread = None
			self.job_event.clear()

	def process_command(self, message: Request):
		logging.info("Received command {}".format(message.message))
		if message.message == "start work: job_counter" and not self.job_thread:
			self.job_thread = JobCounter(self.job_results, self.job_event, daemon=True)
			self.job_thread.start()
		elif message.message == "stop work":
			self.job_event.set()


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	print(sys.argv)
	client: Optional[ClientBase] = None
	if sys.argv[1] == "client":
		client = Client(SERVER_ADDRESS, "client")
	else:
		client = Worker(SERVER_ADDRESS, "worker")
	client.run()
