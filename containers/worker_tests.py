import uuid

from unittest import main, TestCase, mock

from constants import DestinationType, MessageType
from protocol import Request, create_payload, parse_header
from settings import HEADER_LENGTH
from worker import ClientBase


class ClientBaseTest(TestCase):
	def test_shutdown(self):
		client = ClientBase(("0.0.0.0", 9999))
		self.assertTrue(client.is_running())
		client.shutdown()
		self.assertFalse(client.is_running())
