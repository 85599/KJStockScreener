"""
Central configuration for LedgerLens.
Keeping all constants in one place makes the whole project easy to tune
without hunting through scraper/parser files.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# config.py lives at <repo_root>/src/ledgerlens/config.py, so three parents up
# gets back to the repo root (keeps LedgerLens's cache/output out of src/).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "ledgerlens_output"
CACHE_DIR = PROJECT_ROOT / ".ledgerlens_cache"

# ---------------------------------------------------------------------------
# Screener.in endpoints
# ---------------------------------------------------------------------------
BASE_URL = "https://www.screener.in"
COMPANY_PATH = "/company/{symbol}/"
COMPANY_CONSOLIDATED_PATH = "/company/{symbol}/consolidated/"
SEARCH_API_PATH = "/api/company/search/"

# HTML section ids on a company page -> internal key
SECTION_MAP = {
    "quarters": "quarters",
    "profit_loss": "profit-loss",
    "balance_sheet": "balance-sheet",
    "cash_flow": "cash-flow",
    "ratios": "ratios",
    "shareholding": "shareholding",
    "peers": "peers",
    "documents": "documents",
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
DEFAULT_DELAY = 1.2          # polite delay between requests (seconds)
DEFAULT_TIMEOUT = 25         # request timeout (seconds)
MAX_RETRIES = 3
RETRY_BACKOFF = 1.6

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE_URL,
}

# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS = 60 * 30  # 30 minutes - avoid hammering screener.in on repeat lookups

# ---------------------------------------------------------------------------
# Web server
# ---------------------------------------------------------------------------
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 7860

# All sections the scraper knows how to produce
ALL_SECTIONS = [
    "summary", "quarters", "profit_loss", "balance_sheet",
    "cash_flow", "ratios", "shareholding", "pros_cons",
    "peers", "documents",
]
