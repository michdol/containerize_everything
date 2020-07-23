from typing import Union

from client_base import ClientBase


class Client(ClientBase):
	# Client is not allowed to send any messages
	def on_message(self, message: Union[str, bytes], opcode: int):
		pass
