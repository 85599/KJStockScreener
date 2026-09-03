"""
Lightweight disk cache.

Screener.in is a shared, rate-limit-sensitive resource, so LedgerLens caches
the last fetch for a symbol for CACHE_TTL_SECONDS. This is a big part of
what makes the tool "large scale friendly" - repeated lookups from the UI
(switching consolidated/standalone, re-opening a tab) don't re-scrape.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

from ledgerlens.config import CACHE_DIR, CACHE_TTL_SECONDS
from ledgerlens.logging_config import get_logger
from ledgerlens.utils.clean import clean_for_json

log = get_logger("cache")


class DiskCache:
    def __init__(self, cache_dir: Path = CACHE_DIR, ttl: int = CACHE_TTL_SECONDS):
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe_key = "".join(c if c.isalnum() else "_" for c in key)
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[Any]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        if time.time() - payload.get("_cached_at", 0) > self.ttl:
            return None

        log.info(f"Cache hit for '{key}'")
        return payload.get("data")

    def set(self, key: str, data: Any) -> None:
        path = self._path(key)
        payload = {"_cached_at": time.time(), "data": clean_for_json(data)}
        try:
            path.write_text(json.dumps(payload, default=str, allow_nan=False), encoding="utf-8")
        except OSError as e:
            log.warning(f"Could not write cache for '{key}': {e}")

    def clear(self) -> int:
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
        return count
