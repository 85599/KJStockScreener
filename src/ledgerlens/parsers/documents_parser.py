"""
NEW section: parses screener.in's "Documents" panel, which links out to
Annual Reports, Credit Rating letters, and Concall transcripts/notes/PPTs.
This is genuinely useful data that the original scraper didn't touch.
"""

from typing import Any, Dict, List

from bs4 import BeautifulSoup


def _parse_link_list(container) -> List[Dict[str, str]]:
    items = []
    if not container:
        return items
    for a in container.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = a["href"]
        if title and href:
            items.append({"title": title, "url": href})
    return items


def parse_documents(soup: BeautifulSoup) -> Dict[str, Any]:
    section = soup.find("section", id="documents") or soup.select_one("#documents")
    result: Dict[str, List[Dict[str, str]]] = {
        "annual_reports": [],
        "credit_ratings": [],
        "concalls": [],
    }
    if not section:
        return result

    # screener groups documents into sub-panels, each usually with a heading
    for panel in section.select("div.documents, .flex-column, .sub-panel"):
        heading = panel.find(["h3", "h4"])
        label = heading.get_text(strip=True).lower() if heading else ""
        links = _parse_link_list(panel)
        if not links:
            continue
        if "annual" in label:
            result["annual_reports"].extend(links)
        elif "credit" in label or "rating" in label:
            result["credit_ratings"].extend(links)
        elif "concall" in label or "transcript" in label:
            result["concalls"].extend(links)

    # Fallback: if grouping by heading didn't work, just bucket by link text
    if not any(result.values()):
        for link in _parse_link_list(section):
            t = link["title"].lower()
            if "annual report" in t:
                result["annual_reports"].append(link)
            elif "credit rating" in t or "rating" in t:
                result["credit_ratings"].append(link)
            elif "transcript" in t or "ppt" in t or "notes" in t or "concall" in t:
                result["concalls"].append(link)

    return result
