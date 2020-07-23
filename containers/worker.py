import json
import logging
import threading
import queue

from typing import Optional, Union

from client_base import ClientBase
from constants import MessageType, WorkerStatus, JobName, Command
from job_base import TestJob
from websocket_protocol import TEXT


class Worker(ClientBase):
	__command_handlers = {
		"test_job": TestJob
	}

	def __init__(self):
		super().__init__()
		self.job_thread: Optional[threading.Thread] = None
		self.status: WorkerStatus = WorkerStatus.Waiting

		self.job_event: threading.Event = threading.Event()
		self.client_type: str = 'worker'

	def __str__(self) -> str:
		return "Worker(here will be an ID)"

	def send_message(self, message: bytes, opcode: int):
		self.send_queue.put((message, opcode))

	def on_message(self, message: Union[str, bytes], opcode: int):
		if opcode == TEXT:
			message_json = json.loads(message)
			if message_json["type"] == MessageType.Command:
				self.handle_command(message_json)
			else:
				logging.info("Message: {}".format(message_json))

	def handle_command(self, message_json: dict):
		error_reason: str = ""
		try:
				command = message_json["command"]
				logging.debug("Handling command: %s" % command)

				if command == Command.StartJob:
					job_name = message_json["payload"]
					if self.status != WorkerStatus.Waiting:
						error_reason = "Worker status busy; cannot start '%s'" % job_name
						raise Exception(error_reason)

					handler = self.__command_handlers[job_name]
					job_kwargs = {
						"event": self.job_event,
						"results_queue": self.send_queue,
						"send_message": self.send_message
					}
					job_kwargs.update(message_json["args"])
					self.job_thread = handler(kwargs=job_kwargs)
					self.status = WorkerStatus.Busy
					self.job_thread.start()

				elif command == Command.StopJob:
					if self.status != WorkerStatus.Busy and not self.job_thread:
						raise Exception("No job currently running")
					if not self.job_event.is_set():
						self.job_event.set()
		except Exception as e:
			logging.error("Exception handling command: {}".format(e))
			if error_reason:
				self.respond_with_error(error_reason)
		finally:
			# TODO: clean job if running
			if not self.job_event.is_set():
				self.job_event.set()
			if self.job_thread:
				self.job_thread = None

	def respond_with_error(self, reason: str):
		errror_message: bytes = json.dumps({
			"type": MessageType.Error,
			"payload": reason,
		}).encode('utf-8')
		self.send_message(errror_message, TEXT)

	def main_loop(self):
		# TODO: check cleaning after job
		if self.job_event.is_set():
			if self.job_thread:
				self.job_thread = None
			self.status = WorkerStatus.Waiting
			self.job_event.clear()


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.INFO, datefmt="%H:%M:%S")

	w = Worker()
	w.run()
	logging.info("Worker exiting")
