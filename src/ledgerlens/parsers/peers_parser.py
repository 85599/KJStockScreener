"""
NEW section (not in the original scraper): parses screener.in's "Peer
comparison" table, e.g. for a company it lists competitors with CMP, P/E,
market cap, ROCE, etc. Very useful for relative valuation.
"""

from io import StringIO
from typing import Optional

import pandas as pd
from bs4 import BeautifulSoup

from ledgerlens.logging_config import get_logger

log = get_logger("peers_parser")


def parse_peers(soup: BeautifulSoup) -> Optional[pd.DataFrame]:
    section = soup.find("section", id="peers") or soup.select_one("#peers")
    if not section:
        return None

    table = section.find("table")
    if not table:
        return None

    try:
        dfs = pd.read_html(StringIO(str(table)))
        if not dfs:
            return None
        df = dfs[0]
        df.columns = [str(c).strip() for c in df.columns]

        # Screener embeds the peer's screener URL as a link on the name cell -
        # pull those out too since they're useful for chaining further lookups.
        peer_links = []
        rows = table.select("tbody tr") if table.find("tbody") else table.find_all("tr")[1:]
        for row in rows:
            link = row.find("a", href=True)
            if link and "/company/" in link["href"]:
                peer_links.append(link["href"])
        if peer_links and len(peer_links) == len(df):
            df["screener_url"] = peer_links

        # Drop a trailing all-NaN "Median" duplicate row if present twice
        df = df.dropna(how="all")
        return df
    except (ValueError, ImportError) as e:
        log.warning(f"Peers table parse failed: {e}")
        return None
