import json
import logging
import threading

from constants import MessageType
from websocket_protocol import TEXT


class JobBase(threading.Thread):
	def __init__(self, args=(), kwargs=None):
		threading.Thread.__init__(self, group=None, target=None, name=None)
		self.event = kwargs["event"]
		self.send_message = kwargs["send_message"]
		del kwargs["event"]
		self.daemon = True
		self.args = args
		self.kwargs = kwargs

	def run(self):
		logging.info("Starting job with: {} and {}".format(self.args, self.kwargs))
		self.work()
		logging.info("Job done")
		self.event.set()

	def work(self):
		pass


class TestJob(JobBase):
	def work(self):
		payload = json.dumps({
			"type": MessageType.JobResults,
			"payload": "mock results"
		}).encode('utf-8')
		self.send_message(payload, TEXT)
