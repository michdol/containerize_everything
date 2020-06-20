import socket
import logging
import sys
import errno
import psutil

from time import sleep


def get_data():
    return str(psutil.net_io_counters()[0])


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

HEADER_LENGTH = 10

IP = "server"
PORT = 8000

# Create a socket
# socket.AF_INET - address family, IPv4, some otehr possible are AF_INET6, AF_BLUETOOTH, AF_UNIX
# socket.SOCK_STREAM - TCP, conection-based, socket.SOCK_DGRAM - UDP, connectionless, datagrams, socket.SOCK_RAW - raw IP packets
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to a given ip and port
client_socket.connect((IP, PORT))

# Set connection to non-blocking state, so .recv() call won;t block, just return some exception we'll handle
client_socket.setblocking(False)

host_name = socket.gethostname()
client_addr = socket.gethostbyname(host_name)
logger.info("hostname: {}, addr: {}".format(host_name, client_addr))
my_username = "containers_client_1"
# Prepare username and header and send them
# We need to encode username to bytes, then count number of bytes and prepare header of fixed size, that we encode to bytes as well
username_b = my_username.encode('utf-8')
username_header = f"{len(username_b):<{HEADER_LENGTH}}".encode('utf-8')
logger.info("USERNAME HEADER: {}".format(str(username_header)))
client_socket.send(username_header + username_b)


while True:
    # Wait for user to input a message
    message = get_data()
    sleep(1)
    # If message is not empty - send it
    if message:
        # Encode message to bytes, prepare header and convert to bytes, like for username above, then send
        message_header = f"{len(message):<{HEADER_LENGTH}}".encode('utf-8')
        logger.info("SENDING MESSAGE:\n{}\n{}".format(str(message_header), message))
        client_socket.send(message_header + message.encode("utf-8"))
    try:
        # Now we want to loop over received messages (there might be more than one) and print them
        while True:
            # Receive our "header" containing username length, it's size is defined and constant
            username_header = client_socket.recv(HEADER_LENGTH)
            # If we received no data, server gracefully closed a connection, for example using socket.close() or socket.shutdown(socket.SHUT_RDWR)
            if not len(username_header):
                logger.error("Connection closed by server")
                sys.exit()
            # Convert header to int value
            username_length = int(username_header.decode('utf-8').strip())
            # Receive and decode username
            username = client_socket.recv(username_length).decode("utf-8")

            # Now do the same for message (as we received username, we received whole message, there's no need to check if it has any length)
            message_header = client_socket.recv(HEADER_LENGTH)
            message_length = int(message_header.decode('utf-8').strip())
            message = client_socket.recv(message_length).decode('utf-8')
            logger.info("MESSAGE FROM SERVER {} > {}".format(username, message))
    except IOError as e:
        # This is normal on non blocking connections - when there are no incoming data error is going to be raised
        # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
        # We are going to check for both - if one of them - that's expected, means no incoming data, continue as normal
        # If we got different error code - something happened
        if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
            logger.error("Reading error: {}".format(e))
            sys.exit()

        # We just did not receive anything
        continue

    except Exception as e:
        # Any other exception - something happened, exit
        logger.error("RECEIVE ERROR: {}".format(e))
        sys.exit()
