import sys
import logging

TESTING = "unittest" in sys.argv[0]
if TESTING:
	logging.disable(logging.CRITICAL)

CLIENT_CONTAINER_NAME = "containers_client_1"
