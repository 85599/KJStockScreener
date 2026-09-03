"""Parses the tabular financial sections (quarters, P&L, balance sheet, cash
flow, ratios, shareholding) that all share the same table markup on a
screener.in company page."""

from io import StringIO
from typing import Optional

import pandas as pd
from bs4 import BeautifulSoup

from ledgerlens.logging_config import get_logger

log = get_logger("table_parser")


def parse_table_section(soup: BeautifulSoup, section_id: str) -> Optional[pd.DataFrame]:
    section = soup.find("section", id=section_id)
    if not section:
        section = soup.select_one(f"#{section_id}")
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
        if str(df.columns[0]).startswith("Unnamed") or df.columns[0] == "":
            df = df.rename(columns={df.columns[0]: "Particulars"})
        return df
    except (ValueError, ImportError) as e:
        log.warning(f"Table parse failed ({section_id}): {e}")
        return None
