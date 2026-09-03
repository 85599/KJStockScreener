"""
NEW: SearchScraper - hits screener.in's own autocomplete API so the UI can
offer a live "did you mean" symbol search instead of making the user guess
the exact NSE/BSE ticker.
"""

from typing import Any, Dict, List

from ledgerlens.config import BASE_URL, SEARCH_API_PATH
from ledgerlens.core.http_client import HttpClient
from ledgerlens.logging_config import get_logger

log = get_logger("search_scraper")


class SearchScraper:
    def __init__(self, timeout: int = 15):
        self.client = HttpClient(delay=0.15, timeout=timeout)

    def search(self, query: str) -> List[Dict[str, Any]]:
        query = query.strip()
        if not query:
            return []

        url = BASE_URL + SEARCH_API_PATH
        raw = self.client.get_json(url, params={"q": query})
        if not raw:
            return []

        results = []
        for item in raw:
            item_url = item.get("url", "")
            symbol = ""
            if item_url:
                parts = [p for p in item_url.strip("/").split("/") if p]
                # screener.in company URLs look like /company/TCS/ or
                # /company/TCS/consolidated/ — the symbol is always the
                # segment right after "company", NOT the last segment
                # (which is "consolidated" for large-cap companies whose
                # default view is consolidated financials).
                if "company" in parts:
                    idx = parts.index("company")
                    if idx + 1 < len(parts):
                        symbol = parts[idx + 1]
                if not symbol and parts:
                    symbol = parts[-1]
            if not symbol:
                symbol = item.get("id", "")

            results.append({
                "name": item.get("name", ""),
                "symbol": symbol,
                "url": (BASE_URL + item_url) if item_url else None,
            })
        return results

    def close(self):
        self.client.close()
