import requests
import time

from bs4 import BeautifulSoup

from job_base import JobBase, JobError
from validators import is_valid_url


class WordCounterJob(JobBase):
	Name: str = "word_counter"

	def check_params(self):
		url = self.kwargs.get("url")
		if not url or not is_valid_url(url):
			raise JobError("Valid url is required")

		if not self.kwargs.get("word"):
			raise JobError("Target word is required")

	def work(self):
		url = self.kwargs["url"]
		target_word = self.kwargs["word"]

		try:
			start = time.time()
			page = requests.get(url)
			soup = BeautifulSoup(page.content, 'html.parser')
			counter = 0
			counter = len([word for word in soup.get_text().split(" ") if word == target_word])
			self.results_queue.put({
				"source": url,
				"target_word": target_word,
				"result": counter,
				"time_elapsed": round(time.time() - start, 4)
			})
		except Exception as e:
			raise JobError("Failed to finish job")
