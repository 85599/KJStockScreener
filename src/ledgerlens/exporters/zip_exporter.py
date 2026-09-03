"""
Bundles a full scrape result (summary, tables, pros/cons, peers, documents)
into a single ZIP - either written to disk or returned as in-memory bytes
(used by the web API's "Download All" button).
"""

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from ledgerlens.utils.clean import clean_for_json

_SECTION_FILE_NAMES = {
    "quarters": "03_quarterly_results",
    "profit_loss": "04_profit_loss",
    "balance_sheet": "05_balance_sheet",
    "cash_flow": "06_cash_flow",
    "ratios": "07_ratios",
    "shareholding": "08_shareholding",
    "peers": "09_peer_comparison",
}


def _dump_json(obj: Any) -> str:
    return json.dumps(clean_for_json(obj), indent=2, ensure_ascii=False, default=str)


def build_zip_bytes(data: Dict[str, Any]) -> bytes:
    buf = BytesIO()
    symbol = data.get("symbol", "STOCK")

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if data.get("summary"):
            zf.writestr(f"{symbol}/01_summary.json", _dump_json(data["summary"]))

        if data.get("pros_cons"):
            zf.writestr(f"{symbol}/02_pros_cons.json", _dump_json(data["pros_cons"]))

        if data.get("documents"):
            zf.writestr(f"{symbol}/10_documents.json", _dump_json(data["documents"]))

        for key, fname in _SECTION_FILE_NAMES.items():
            section = data.get(key)
            df = _as_dataframe(section)
            if df is not None and not df.empty:
                zf.writestr(f"{symbol}/{fname}.csv", df.to_csv(index=False))
                xbuf = BytesIO()
                df.to_excel(xbuf, index=False, engine="openpyxl")
                zf.writestr(f"{symbol}/{fname}.xlsx", xbuf.getvalue())

        zf.writestr(f"{symbol}/00_full_data.json", _dump_json(data))

    buf.seek(0)
    return buf.read()


def build_zip_file(data: Dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    symbol = data.get("symbol", "STOCK")
    zip_path = out_dir / f"{symbol}_ledgerlens.zip"
    zip_path.write_bytes(build_zip_bytes(data))
    return zip_path


def _as_dataframe(section) -> pd.DataFrame:
    if isinstance(section, pd.DataFrame):
        return section
    if isinstance(section, list):
        return pd.DataFrame(section)
    return None
