import queue
import threading

from time import sleep


class JobCounter(threading.Thread):
	def __init__(self, results_pipeline: queue.Queue, event: threading.Event, daemon: bool=False):
		super().__init__()
		self.results_pipeline = results_pipeline
		self.event = event
		self.daemon = daemon
		self.done = False

	def run(self):
		count = 0
		print("Started job_counter")
		while count <= 5:
			if self.event.is_set():
				break
			self.results_pipeline.put({"job_name": "Counter", "work result": count})
			sleep(1)
			count += 1
		print("Finished job_counter")
		self.done = True
