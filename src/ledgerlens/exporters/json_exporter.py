"""Export scraped sections (dicts) to JSON bytes or files."""

import json
from pathlib import Path
from typing import Any

from ledgerlens.utils.clean import clean_for_json


def to_json_bytes(obj: Any, indent: int = 2) -> bytes:
    cleaned = clean_for_json(obj)
    return json.dumps(cleaned, indent=indent, ensure_ascii=False, default=str).encode("utf-8")


def save_json(obj: Any, path: Path, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(clean_for_json(obj), indent=indent, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
