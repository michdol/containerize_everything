import errno
import logging
import os
import socket
import sys

from time import sleep

from constants import HEADER_LENGTH, SERVER_ADDRESS


def main():
  format_ = "%(asctime)s %(levelname)s: %(message)s"
  logging.basicConfig(format=format_, level=logging.DEBUG,
                      datefmt="%H:%M:%S")

  client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  client_socket.connect(SERVER_ADDRESS)
  client_socket.setblocking(False)
  client_username: str = socket.gethostname()
  logging.debug("Client username: {}".format(client_username))
  username_header: bytes = get_message_header(client_username)
  client_socket.send(username_header + client_username.encode('utf-8'))
  while True:
    message = get_data()
    sleep(1)
    if message:
      message_header: bytes = get_message_header(message)
      logging.info("Sending message {message}".format(message=message))
      client_socket.send(message_header + message.encode("utf-8"))

    try:
      while True:
        username_header: bytes = client_socket.recv(HEADER_LENGTH)
        if not len(username_header):
          logging.error("Connection closed by server")
          sys.exit()
        d = username_header.decode("utf-8")
        username_length = int(d[2:].strip())
        username = client_socket.recv(username_length).decode("utf-8")

        message_header: bytes = client_socket.recv(HEADER_LENGTH)
        message_length = int(message_header.decode("utf-8").strip())
        message = client_socket.recv(message_length).decode("utf-8")
        logging.info(f"Received message <{username}> {message}")
    except IOError as e:
      # This is normal on non blocking connections - when there are no incoming data error is going to be raised
      # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
      # We are going to check for both - if one of them - that's expected, means no incoming data, continue as normal
      # If we got different error code - something happened
      if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
        logging.error(f"Error while receiving message\n{e}")
        sys.exit()
      # No message received
      continue


def get_message_header(message: str) -> bytes:
  return f"{len(message):<{HEADER_LENGTH}}".encode('utf-8')


def get_data():
  return "dummy client message" + str(os.getpid())


if __name__ == "__main__":
  main()
