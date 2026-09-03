"""Shared base class for all LedgerLens scrapers."""

from typing import Optional

from bs4 import BeautifulSoup

from ledgerlens.config import DEFAULT_DELAY, DEFAULT_TIMEOUT, BASE_URL
from ledgerlens.core.http_client import HttpClient
from ledgerlens.logging_config import get_logger

log = get_logger("base_scraper")


class BaseScraper:
    """
    Wraps HttpClient and offers an optional Selenium fallback. Subclasses
    only need to implement the page-specific parsing logic.
    """

    BASE_URL = BASE_URL

    def __init__(self, delay: float = DEFAULT_DELAY, timeout: int = DEFAULT_TIMEOUT,
                 use_selenium_fallback: bool = False):
        self.client = HttpClient(delay=delay, timeout=timeout)
        self.use_selenium_fallback = use_selenium_fallback
        self._selenium_client = None

    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        soup = self.client.get_soup(url)
        if soup is not None:
            return soup

        if not self.use_selenium_fallback:
            return None

        log.info(f"Falling back to Selenium for {url}")
        try:
            from src.core.selenium_client import SeleniumClient
            if self._selenium_client is None:
                self._selenium_client = SeleniumClient(headless=True)
            return self._selenium_client.get_soup(url)
        except Exception as e:
            log.error(f"Selenium fallback failed: {e}")
            return None

    def close(self):
        self.client.close()
        if self._selenium_client is not None:
            self._selenium_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
