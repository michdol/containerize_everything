import json
import logging
import threading
import queue

from typing import Optional, Union

from client_base import ClientBase
from constants import (
	MessageType,
	WorkerStatus,
	Command,
)
from job_base import TestJob
from websocket_protocol import TEXT


class WorkerError(Exception):
	pass


class Worker(ClientBase):
	__command_handlers = {
		TestJob.Name: TestJob
	}

	def __init__(self):
		super().__init__()
		self.job_thread: Optional[threading.Thread] = None
		self.status: WorkerStatus = WorkerStatus.Waiting

		self.job_event: threading.Event = threading.Event()
		self.client_type: str = 'worker'

	def __str__(self) -> str:
		return "Worker(Python)"

	def on_message(self, message: dict):
		try:
			message_type = message["type"]
			if message_type == MessageType.Command:
				self.handle_command(message)
			else:
				logging.info("Message: {}".format(message))
		except WorkerError as e:
			self.respond_with_error(e.args[0])
		except Exception as e:
			logging.error("Exception handling command: {}".format(e))
		finally:
			# TODO: clean job if running
			if not self.job_event.is_set():
				self.job_event.set()
			if self.job_thread:
				self.job_thread = None

	def handle_command(self, message: dict):
		error_reason: str = ""
		command = message["command"]
		logging.debug("Handling command: %s" % command)

		if command == Command.StartJob:
			job_name = message["name"]
			if self.status != WorkerStatus.Waiting:
				error_reason = "Worker status busy; cannot start '%s'" % job_name
				raise WorkerError(error_reason)

			handler = self.__command_handlers[job_name]
			job_kwargs = {
				"event": self.job_event,
				"results_queue": self.send_queue,
				"send_message": self.send_message
			}
			job_kwargs.update(message["args"])
			self.job_thread = handler(kwargs=job_kwargs)
			self.status = WorkerStatus.Busy
			self.job_thread.start()

		elif command == Command.StopJob:
			if self.status != WorkerStatus.Busy and not self.job_thread:
				raise WorkerError("No job currently running")
			if not self.job_event.is_set():
				self.job_event.set()

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
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	w = Worker()
	w.run()
	logging.info("Worker exiting")
