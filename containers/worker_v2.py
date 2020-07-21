import logging
import socket

from settings import SERVER_ADDRESS
from websocket_protocol import WebSocket, PING, TEXT, CLOSE


def main():
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect(SERVER_ADDRESS)
	# This will require a separate thread waiting for the response
	# or setblock(False) to be called after handshake
	# s.setblocking(False)

	try:
		ws = WebSocket(s, SERVER_ADDRESS, is_client=False)

		ws.handshake()
		logging.info("Handshake complete")

		while True:
			message = input("\nGive me input\n")
			if message == "ping":
				logging.info("Pinging server")
				ws.send_message(b'', PING)
			else:
				logging.info("{} Sending: {}".format(ws, message))
				ws.send_message(message.encode('utf-8'), TEXT)
			ws.handle_data()
	except Exception as e:
		logging.error("{} Exception: {}".format(ws, e))
		ws.send_message(b'', CLOSE)
	finally:
		s.close()


if __name__ == "__main__":
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

	main()
