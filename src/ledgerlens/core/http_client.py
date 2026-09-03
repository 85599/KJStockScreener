"""
HTTP client built on `requests` + `BeautifulSoup`.

This is the primary fetch path. Screener.in is server-rendered, so a plain
GET + BeautifulSoup parse is enough for almost every page. It includes
retry-with-backoff and a polite delay so the tool is a good citizen.
"""

import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ledgerlens.config import (
    DEFAULT_DELAY, DEFAULT_TIMEOUT, DEFAULT_HEADERS,
    MAX_RETRIES, RETRY_BACKOFF,
)
from ledgerlens.logging_config import get_logger

log = get_logger("http_client")


class HttpClient:
    """Thin, resilient wrapper around requests.Session for HTML fetching."""

    def __init__(self, delay: float = DEFAULT_DELAY, timeout: int = DEFAULT_TIMEOUT):
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_BACKOFF,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL and return a parsed BeautifulSoup document, or None on failure."""
        try:
            time.sleep(self.delay)
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "lxml")
        except requests.RequestException as e:
            log.error(f"GET failed for {url}: {e}")
            return None

    def get_json(self, url: str, params: Optional[dict] = None) -> Optional[list]:
        """Fetch a JSON API endpoint (e.g. screener's search autocomplete)."""
        try:
            time.sleep(min(self.delay, 0.6))
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            log.error(f"JSON GET failed for {url}: {e}")
            return None

    def close(self):
        self.session.close()
