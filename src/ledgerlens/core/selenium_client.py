"""
Selenium fallback client.

Screener.in's company pages are server-rendered so `HttpClient` (requests +
BeautifulSoup) is enough almost all the time. But some situations need a
real browser: pages that gate content behind JS execution, infinite-scroll
widgets, or a symbol that keeps failing plain requests. `SeleniumClient`
gives LedgerLens that escape hatch without making Selenium a hard
dependency - it degrades gracefully if selenium/webdriver isn't installed.

Usage:
    with SeleniumClient(headless=True) as client:
        soup = client.get_soup("https://www.screener.in/company/TCS/")
"""

from typing import Optional

from bs4 import BeautifulSoup

from ledgerlens.config import DEFAULT_HEADERS, DEFAULT_TIMEOUT
from ledgerlens.logging_config import get_logger

log = get_logger("selenium_client")

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class SeleniumClient:
    """
    Headless-Chrome-backed fetcher, used as a fallback when the plain HTTP
    client can't get a clean page (JS-gated content, anti-bot pages, etc).
    """

    def __init__(self, headless: bool = True, timeout: int = DEFAULT_TIMEOUT):
        if not SELENIUM_AVAILABLE:
            raise RuntimeError(
                "Selenium is not installed. Run: pip install selenium webdriver-manager"
            )
        self.timeout = timeout
        self.driver = self._build_driver(headless)

    def _build_driver(self, headless: bool):
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1400,1000")
        options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")

        try:
            # webdriver-manager auto-downloads a matching chromedriver build
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except Exception as e:
            log.warning(f"webdriver-manager unavailable ({e}); trying system chromedriver")
            return webdriver.Chrome(options=options)

    def get_soup(self, url: str, wait_for_selector: str = "body") -> Optional[BeautifulSoup]:
        """Load a URL in the real browser and return the rendered HTML as soup."""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
            )
            html = self.driver.page_source
            return BeautifulSoup(html, "lxml")
        except Exception as e:
            log.error(f"Selenium fetch failed for {url}: {e}")
            return None

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
