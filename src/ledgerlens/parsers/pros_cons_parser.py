"""Parses the analyst-style pros/cons bullet lists shown on a company page."""

from typing import Dict, List

from bs4 import BeautifulSoup


def parse_pros_cons(soup: BeautifulSoup) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {"pros": [], "cons": []}
    for sel, key in [("div.pros", "pros"), ("div.cons", "cons")]:
        block = soup.select_one(sel)
        if block:
            for li in block.find_all("li"):
                text = li.get_text(strip=True)
                if text:
                    result[key].append(text)
    return result
