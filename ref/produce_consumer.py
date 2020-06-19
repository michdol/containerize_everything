import logging
import random
import concurrent.futures
import threading
import time


SENTINEL = object()


def producer(pipeline):
  for index in range(10):
    message = random.randint(1, 101)
    logging.info("Producer got message: %s", message)
    pipeline.set_message(message, "Producer")


def consumer(pipeline):
  message = 0
  while message is not SENTINEL:
    message = pipeline.get_message("Consumer")
    if message is not SENTINEL:
      logging.info("Consumer storing message: %s", message)


class Pipeline:
  def __init__(self):
    self.message = 0
    self.producer_lock = threading.Lock()
    self.consumer_lock = threading.Lock()
    self.consumer_lock.acquire()

  def get_message(self, name):
    logging.debug("%s:about to acquire getlock", name)
    self.consumer_lock.acquire()
    logging.debug("%s:has getlock", name)
    message = self.message
    logging.debug("%s:about to release setlock", name)
    self.producer_lock.release()
    logging.debug("%s:setlock released", name)
    return message

  def set_message(self, message, name):
    logging.debug("%s:about to acquire setlock", name)
    self.producer_lock.acquire()
    logging.debug("%s:has setlock", name)
    self.message = message
    logging.debug("%s:about to release getlock", name)
    self.consumer_lock.release()
    logging.debug("%s:getlock released", name)


if __name__ == "__main__":
  format_ = "%(asctime)s: %(message)s"
  logging.basicConfig(format=format_, level=logging.DEBUG,
                      datefmt="%H:%M:%S")

  pipeline = Pipeline()
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    executor.submit(producer, pipeline)
    executor.submit(consumer, pipeline)

# https://realpython.com/intro-to-python-threading/