import logging
import socket

from settings import SERVER_ADDRESS
from websocket_protocol import WebSocket


def main():
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect(SERVER_ADDRESS)
	# This will require a separate thread waiting for the response
	# or setblock(False) to be called after handshake
	# s.setblocking(False)

	ws = WebSocket(s, ("", 0))

	ws.send_handshake()


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	main()
