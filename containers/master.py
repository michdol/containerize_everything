from typing import Union

from client_base import ClientBase


class Master(ClientBase):
	def send_message(self, message: bytes, opcode: int):
		self.send_queue.put((message, opcode))

	def on_message(self, message: Union[str, bytes], opcode: int):
		pass
