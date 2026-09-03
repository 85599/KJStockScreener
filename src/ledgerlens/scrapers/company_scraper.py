"""
CompanyScraper - the core engine.

Fetches a screener.in company page and hands each section off to its
dedicated parser (summary, financial tables, pros/cons, peers, documents).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ledgerlens.config import BASE_URL, COMPANY_PATH, COMPANY_CONSOLIDATED_PATH, SECTION_MAP
from ledgerlens.parsers.summary_parser import parse_summary
from ledgerlens.parsers.table_parser import parse_table_section
from ledgerlens.parsers.pros_cons_parser import parse_pros_cons
from ledgerlens.parsers.peers_parser import parse_peers
from ledgerlens.parsers.documents_parser import parse_documents
from ledgerlens.scrapers.base_scraper import BaseScraper
from ledgerlens.logging_config import get_logger

log = get_logger("company_scraper")

# section keys that map straight onto SECTION_MAP table ids
_TABLE_SECTIONS = ("quarters", "profit_loss", "balance_sheet", "cash_flow",
                    "ratios", "shareholding")


class CompanyScraper(BaseScraper):

    def get_company(
        self,
        symbol: str,
        consolidated: bool = True,
        sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        symbol = symbol.strip().upper()
        path_template = COMPANY_CONSOLIDATED_PATH if consolidated else COMPANY_PATH
        url = BASE_URL + path_template.format(symbol=symbol)

        soup = self._fetch(url)
        if not soup:
            return {"error": f"Could not fetch data for '{symbol}'. Check the symbol or try again."}

        title = soup.find("title")
        if title and "Page Not Found" in title.get_text():
            return {"error": f"Symbol '{symbol}' not found on Screener.in"}

        if sections is None:
            sections = [
                "summary", "quarters", "profit_loss", "balance_sheet",
                "cash_flow", "ratios", "shareholding", "pros_cons",
                "peers", "documents",
            ]

        data: Dict[str, Any] = {
            "symbol": symbol,
            "url": url,
            "consolidated": consolidated,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
        }

        if "summary" in sections:
            data["summary"] = parse_summary(soup)

        for sec in _TABLE_SECTIONS:
            if sec in sections:
                html_id = SECTION_MAP[sec]
                data[sec] = parse_table_section(soup, html_id)

        if "pros_cons" in sections:
            data["pros_cons"] = parse_pros_cons(soup)

        if "peers" in sections:
            data["peers"] = parse_peers(soup)

        if "documents" in sections:
            data["documents"] = parse_documents(soup)

        return data
