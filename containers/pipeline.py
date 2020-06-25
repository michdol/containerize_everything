import logging
import queue


class Pipeline(queue.Queue):
	def __init__(self):
		super().__init__(maxsize=10)

	def get_message(self, name: str) -> str:
		logging.debug("{} Getting message".format(name))
		value: str = self.get()
		logging.debug("{} got {}".format(name, value))
		return value

	def set_message(self, name: str, value: str):
		logging.debug("{} setting {}".format(name, value))
		self.put(value)
