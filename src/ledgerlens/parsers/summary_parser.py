"""Parses the top-of-page summary block on a screener.in company page."""

from typing import Any, Dict

from bs4 import BeautifulSoup


def parse_summary(soup: BeautifulSoup) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}

    h1 = soup.find("h1")
    if h1:
        summary["company_name"] = h1.get_text(strip=True)

    price_div = soup.select_one("div.font-size-18.strong, div[class*='font-size-18']")
    if price_div:
        span = price_div.find("span")
        if span:
            summary["current_price"] = span.get_text(strip=True)

    ratios = {}
    for li in soup.select("#top-ratios li, ul#top-ratios li, li[data-source]"):
        name_el = li.select_one("span.name, span:first-child")
        num_el = li.select_one("span.number, span:last-child")
        if name_el and num_el:
            key = name_el.get_text(strip=True).rstrip(":")
            val = num_el.get_text(strip=True)
            if key and val and key != val:
                ratios[key] = val

    if len(ratios) < 4:
        for item in soup.select("li.flex, div.company-ratios li, #top-ratios li"):
            spans = item.find_all("span")
            if len(spans) >= 2:
                key = spans[0].get_text(strip=True).rstrip(":")
                val = spans[-1].get_text(strip=True)
                if key and val and len(key) < 40:
                    ratios[key] = val

    summary["ratios"] = ratios

    about = soup.select_one("div.company-profile div.sub, div#company-profile, div.about")
    if about:
        summary["about"] = about.get_text(" ", strip=True)[:900]

    # Extra: BSE/NSE codes and website link, often shown near the header
    links = {}
    for a in soup.select("div.company-links a, a.ink-700"):
        text = a.get_text(strip=True)
        href = a.get("href", "")
        if text and href and "screener.in" not in href:
            links[text] = href
    if links:
        summary["links"] = links

    return summary
