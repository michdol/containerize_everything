import logging
import sys
import socket
import argparse


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


def main():
  parser = argparse.ArgumentParser(description="Socket error examples")
  parser.add_argument("--host", action="store", dest="host", required=False)
  parser.add_argument("--port", action="store", dest="port", required=False)
  parser.add_argument("--file", action="store", dest="file", required=False)
  given_args = parser.parse_args()
  host = given_args.host
  port = int(given_args.port)
  filename = given_args.file

  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  except socket.error as e:
    logger.error("Error creating socket: {}".format(e))
    sys.exit(1)

  try:
    s.connect((host, port))
  except socket.gaierror as e:
    logger.error("Address-related error connecting to server: {}".format(e))
    sys.exit(1)
  except socket.error as e:
    logger.error("Connection error: {}".format(e))
    sys.exit(1)

  try:
    s.sendall("GET {} HTTP/1.0\r\n\r\n".format(filename).encode("utf-8"))
  except socket.error as e:
    logger.error("Error sending data: %s" % e)
    sys.exit(1)

  while True:
    buf = None
    try:
      buf = s.recv(2048)
    except socket.error as e:
      logger.error("Error receiving data: {}".format(e))
      sys.exit(1)
    if not len(buf):
      break
    # Write the received data
    sys.stdout.write(str(buf))


if __name__ == "__main__":
  main()

# page 28