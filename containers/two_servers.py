import concurrent.futures
import logging
import threading

from server import ClientsServer
from server_workers import WorkersServer
from pipeline import Pipeline


def main():
	format_ = "%(asctime)s %(levelname)s: %(message)s"
	logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")
	pipeline = Pipeline()
	clients_server = ClientsServer("0.0.0.0", 8000, pipeline)
	workers_server = WorkersServer("0.0.0.0", 8001, pipeline)
	with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
		logging.info("Starting threads")
		executor.submit(clients_server.serve_forever)
		executor.submit(workers_server.serve_forever)

		logging.info("Threads finished")

	logging.info("Threads out")


if __name__ == "__main__":
	main()
