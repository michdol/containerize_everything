import socket
import logging
import sys
import errno

from time import sleep

from constants import (
  HEADER_LENGTH,
  SERVER_ADDRESS,
  DUMMY_UUID,
  MessageType,
  DestinationType,
)
from custom_types.custom_types import WorkerHeader
from protocol import create_payload, parse_header


def main():
  format_ = "%(asctime)s %(levelname)s: %(message)s"
  logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

  # Create a socket
  # socket.AF_INET - address family, IPv4, some otehr possible are AF_INET6, AF_BLUETOOTH, AF_UNIX
  # socket.SOCK_STREAM - TCP, conection-based, socket.SOCK_DGRAM - UDP, connectionless, datagrams, socket.SOCK_RAW - raw IP packets
  client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  # Connect to a given ip and port
  logging.info("Connecting to {}:{}".format(*SERVER_ADDRESS))
  client_socket.connect(SERVER_ADDRESS)
  client_socket.setblocking(False)

  # Set connection to non-blocking state, so .recv() call won;t block, just return some exception we'll handle
  # TODO: understand setblocking
  # client_socket.setblocking(False)

  host_name = socket.gethostname()
  client_addr = socket.gethostbyname(host_name)
  logging.info("hostname: {}, addr: {}".format(host_name, client_addr))

  initial_connection_payload: bytes = create_payload(
    source=DUMMY_UUID,  # This should be optional, in case of initial connection ommited
    destination=DUMMY_UUID,
    destination_type=DestinationType.SERVER,
    message="I'm a worker",
    message_type=MessageType.INFO
  )

  logging.info("Sending initial payload: {}".format(initial_connection_payload))
  client_socket.send(initial_connection_payload)
  server_id = None
  own_id = None
  while True:
    try:
      header: bytes = client_socket.recv(HEADER_LENGTH)
      if len(header) == 0:
          logging.error("Connection closed by server")
          sys.exit()
      logging.debug("HEADER BYTES {}".format(header))
      parsed_header = parse_header(header)
      if parsed_header["message_type"] == MessageType.INITIAL_CONNECTION:
        server_id = parsed_header["source"]
        own_id = parsed_header["destination"]
      message: bytes = client_socket.recv(parsed_header["message_length"])
      logging.info("MESSAGE: {}".format(message.decode('utf-8')))
    except IOError as e:
      # This is normal on non blocking connections - when there are no incoming data error is going to be raised
      # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
      # We are going to check for both - if one of them - that's expected, means no incoming data, continue as normal
      # If we got different error code - something happened
      if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
          logging.error("Reading error: {}".format(e))
          sys.exit()

      # We just did not receive anything
      continue
    except Exception as e:
      # Any other exception - something happened, exit
      raise e
      logging.error("RECEIVE ERROR: {}".format(e))
      sys.exit()
    message = input("Give me input ")
    if message:
      payload = create_payload(
        source=own_id,
        destination="b52d5fb7-9652-4c96-9793-0f73ac1ec031",
        destination_type=DestinationType.CLIENT,
        message=message,
        message_type=MessageType.MESSAGE
      )
      logging.info("Sending message {}".format(payload))
      client_socket.send(payload)


if __name__ == "__main__":
    main()
