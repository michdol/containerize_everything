import json
import logging
import threading


class JobError(Exception):
	pass


class JobBase(threading.Thread):
	Name: str = ""

	def __init__(self, args=(), kwargs=None):
		threading.Thread.__init__(self, group=None, target=None, name=None)
		self.event = kwargs["event"]
		self.results_queue = kwargs["results_queue"]
		del kwargs["event"]
		del kwargs["results_queue"]
		self.daemon = True
		self.args = args
		self.kwargs = kwargs

	def __str__(self) -> str:
		return "Job({})".format(self.Name)

	def run(self):
		try:
			logging.info("Starting job '{}' with: {} and {}".format(self.Name, self.args, self.kwargs))
			self.check_params()
			self.work()
			logging.info("Job done")
		except JobError as e:
			self.results_queue.put({
				"error": True,
				"reason": e.args[0]
			})
		except Exception as e:
			logging.error("{} exception running job: {}".format(self, e))
		finally:
			self.event.set()

	def check_params(self):
		pass

	def work(self):
		pass


class TestJob(JobBase):
	Name: str = "test_job"

	def work(self):
		self.results_queue.put({
			"result": "mock results",
		})
