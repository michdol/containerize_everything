import socket
import logging
import sys
import errno

from time import sleep

from constants import WORKER_HEADER_LENGTH, HEADER_LENGTH, SERVER_ADDRESS
from custom_types.custom_types import WorkerHeader


def parse_worker_header(header: bytes) -> WorkerHeader:
    message_length, message_type, worker_status = header.decode("utf-8").strip().split(":")
    return WorkerHeader(int(message_length), int(message_type), int(worker_status))


def main():
    format_ = "%(asctime)s %(levelname)s: %(message)s"
    logging.basicConfig(format=format_, level=logging.DEBUG, datefmt="%H:%M:%S")

    # Create a socket
    # socket.AF_INET - address family, IPv4, some otehr possible are AF_INET6, AF_BLUETOOTH, AF_UNIX
    # socket.SOCK_STREAM - TCP, conection-based, socket.SOCK_DGRAM - UDP, connectionless, datagrams, socket.SOCK_RAW - raw IP packets
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Connect to a given ip and port
    client_socket.connect(SERVER_ADDRESS)

    # Set connection to non-blocking state, so .recv() call won;t block, just return some exception we'll handle
    client_socket.setblocking(False)

    host_name = socket.gethostname()
    client_addr = socket.gethostbyname(host_name)
    logging.info("hostname: {}, addr: {}".format(host_name, client_addr))
    my_username = "containers_client_1"
    # Prepare username and header and send them
    # We need to encode username to bytes, then count number of bytes and prepare header of fixed size, that we encode to bytes as well
    username_b = my_username.encode('utf-8')
    username_header = f"{len(username_b):<{HEADER_LENGTH}}".encode('utf-8')
    logging.info("USERNAME HEADER: {}".format(str(username_header)))
    client_socket.send(username_header + username_b)


    while True:
        # Wait for user to input a message
        message = get_data()
        sleep(1)
        # If message is not empty - send it
        if message:
            # Encode message to bytes, prepare header and convert to bytes, like for username above, then send
            message_header = f"{len(message):<{HEADER_LENGTH}}".encode('utf-8')
            logging.info("SENDING MESSAGE:\n{}\n{}".format(str(message_header), message))
            client_socket.send(message_header + message.encode("utf-8"))
        try:
            while True:
                header = client_socket.recv(WORKER_HEADER_LENGTH)
                if len(header) == 0:
                    loggier.error("Connection closed by server")
                    sys.exit()
                parsed_header: WorkerHeader = parse_worker_header(header)
                message: bytes = client_socket.recv(parsed_header.message_length)
                logging.info("HEADER: {}\nMESSAGE: {}".format(parsed_header, message))
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
            logging.error("RECEIVE ERROR: {}".format(e))
            sys.exit()
