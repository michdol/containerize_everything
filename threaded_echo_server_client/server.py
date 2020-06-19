import logging
import os
import socketserver


SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
BUF_SIZE = 1024


def get_logger():
  logger = logging.getLogger(__name__)
  handler = logging.StreamHandler()
  formatter = logging.Formatter(
      '%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  logger.setLevel(logging.DEBUG)
  return logger


logger = get_logger()


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
  def handle(self):
    logger.info("Handling request")
    data = self.request.recv(BUF_SIZE)
    pid = os.getpid()
    response = "%s >> %s" % (pid, data)
    logger.info("SENDING response: {}".format(response))
    self.request.send(response.encode("utf-8"))


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
  pass


def main():
  server = ThreadedTCPServer((SERVER_HOST, SERVER_PORT), ThreadedTCPRequestHandler)
  try:
    logger.info("Starting server")
    server.serve_forever()
  except Exception as e:
    logger.error("Error occurred {}".format(e))
  finally:
    logger.info("Shutting down")
    server.shutdown()


if __name__ == "__main__":
  main()
