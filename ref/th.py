import logging
# import threading
import time
import concurrent.futures


def thread_func(name):
  logging.info("Thread %s: starting", name)
  time.sleep(2)
  logging.info("Thread %s: finishing", name)


if __name__ == "__main__":
  format_ = "%(asctime)s: %(message)s"
  logging.basicConfig(format=format_, level=logging.INFO,
                      datefmt="%H:%M:%S")

  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    executor.map(thread_func, range(3))
  """
  # Running and joining threads manually
  threads = list()
  for index in range(3):
    logging.info("Main    : create and strat thread %d.", index)
    x = threading.Thread(target=thread_func, args=(1,))
    threads.append(x)
    x.start()

  for index, thread in enumerate(threads):
    logging.info("Main    : before joining thread %d.", index)
    thread.join()
    logging.info("Main    : thread %d done.", index)

  """
