import json
import logging
import socket

from typing import Tuple, Optional

from constants import (
	MessageType
)
from custom_types import (
	ServerResponse
)
from websocket_protocol import (
	Address,
	WebSocket,
	WebSocketState,
	Frame,
	CLOSE,
	PING,
	PONG,
	TEXT,
)


class ClientError(Exception):
	pass


class AuthenticationError(ClientError):
	pass


class ClientWebSocketBase(WebSocket):
	def __init__(self, socket: socket.socket, address: Address, is_client: bool, server: object):
		super().__init__(socket, address, is_client)
		self.server = server
		self.is_authenticated: bool = False

		self._handlers = {
			MessageType.Authentication: self.authentication_handler,
			MessageType.Info: self.info_handler,
			MessageType.Message: self.message_handler,
			MessageType.Command: self.command_handler,
			MessageType.JobResults: self.job_results_handler,
			MessageType.Error: self.error_handler,
		}

	@property
	def is_recipient(self) -> bool:
		return False

	def handle_message(self):
		frame: Optional[Frame] = self.handle_data()
		if not frame:
			return None
		logging.info("{} received {} : {}".format(self, frame, frame.payload))

		if frame.opcode == PING:
			return (b'', PONG)
		elif frame.opcode == CLOSE:
			self.server.handle_close(self)
			return None

		client_message: dict = json.loads(frame.payload)
		message_type = client_message["type"]
		if not self.is_authenticated and message_type != MessageType.Authentication:
			raise AuthenticationError("Authentication required")
		handler = None
		try:
			handler = self._handlers[MessageType(message_type)]
		except (KeyError, ValueError):
			raise ClientError("Unknown message type %d" % message_type)

		return handler(client_message)

	def authentication_handler(self, message: dict):
		payload = message["payload"]
		if payload == "worker":
			class_ = WorkerWebSocket
		elif payload == "master":
			class_ = MasterWebSocket
		elif payload == "client":
			class_ = ClientWebSocket
		else:
			raise ClientError("Authentication failed, consider closing connection")
		client = class_(self.socket, self.address, True, self.server)
		client.is_authenticated = True
		client.handshake_complete = True
		client.state = WebSocketState.OPEN	
		self.server.clients[client.socket] = client

		response = self.generate_response(MessageType.Authentication, "Authentication success")
		return (response, TEXT)

	def info_handler(self, info: dict) -> ServerResponse:
		logging.info("{} handling info {}".format(self, info))
		response = self.generate_response(MessageType.Message, "Ok")
		return response, TEXT

	def message_handler(self, message: dict) -> ServerResponse:
		logging.info("{} handling message {}".format(self, message))
		response = self.generate_response(MessageType.Message, "Ok")
		return response, TEXT

	def command_handler(self, command: dict) -> ServerResponse:
		logging.info("{} handling command {}".format(self, command))
		response = self.generate_response(MessageType.Message, "Ok")
		return response, TEXT

	def job_results_handler(self, results: dict) -> ServerResponse:
		logging.info("{} handling job results {}".format(self, results))
		response = self.generate_response(MessageType.Message, "Ok")
		return response, TEXT

	def error_handler(self, error: dict) -> ServerResponse:
		logging.warning("{} handling error {}".format(self, error))
		response = self.generate_response(MessageType.Message, "Ok")
		return response, TEXT

	def generate_response(self, type_: MessageType, payload: str) -> bytes:
		response = {
			"type": type_,
			"payload": payload,
		}
		return json.dumps(response).encode('utf-8')


class ClientWebSocket(ClientWebSocketBase):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._handlers[MessageType.Message] = self.message_handler

	def __str__(self) -> str:
		return "Client({address}:{state})".format(address=self.address, state=self.state)

	@property
	def is_recipient(self):
		return True
	
	def message_handler(self, message: dict):
		opcode: int = TEXT
		response: bytes = b''

		payload = message["payload"]
		if payload == "close":
			self.state = WebSocketState.CLOSING
			opcode = CLOSE
		else:
			response_message = "You have no power here"
			response = self.generate_response(MessageType.Error, response_message)
		return response, opcode


class MasterWebSocket(ClientWebSocketBase):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._handlers[MessageType.Command] = self.command_handler
		self._handlers[MessageType.Message] = self.message_handler

	def __str__(self) -> str:
		return "Master({address}:{state})".format(address=self.address, state=self.state)

	@property
	def is_recipient(self):
		return True

	def command_handler(self, message: dict):
		job_name = message.get("name")
		if not job_name:
			raise ClientError("Argument 'payload' should contains job's name")
		if job_name != "test_job":
			raise ClientError("Job '{}' doesn't exist".format(job_name))
		dummy_job = {"required_workers": 1}
		requested_workers = message.get("required_workers", 1)
		if requested_workers < dummy_job["required_workers"]:
			raise ClientError("Invalid parameter 'required_workers'")

		self.server.handle_command(json.dumps(message).encode('utf-8'))
		response: bytes = self.generate_response(MessageType.Message, "Starting job")
		return response, TEXT

	def message_handler(self, message: dict) -> ServerResponse:
		response: ServerResponse = super().message_handler(message)
		self.server.broadcast_message(json.dumps(message).encode('utf-8'))
		return response


class WorkerWebSocket(ClientWebSocketBase):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._handlers[MessageType.JobResults] = self.job_results_handler

	def __str__(self) -> str:
		return "Worker({address}:{state})".format(address=self.address, state=self.state)

	def job_results_handler(self, results: dict) -> ServerResponse:
		response: ServerResponse = super().job_results_handler(results)
		self.server.broadcast_message(json.dumps(results).encode('utf-8'))
		return response
