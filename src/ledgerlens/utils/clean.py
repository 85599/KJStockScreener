"""
Helpers to make scraped data safe for JSON serialization
(NaN, NaT, pandas NA all break strict JSON encoders).
"""

import math
from typing import Any

import pandas as pd


def clean_for_json(obj: Any) -> Any:
    """Recursively replace NaN / NaT / pandas-NA with None."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_for_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def dataframe_to_records(df) -> list:
    """Convert a DataFrame to a list of JSON-safe dict records.

    Note: df.where(df.notna(), None) looks right but pandas silently
    re-coerces None back to NaN in numeric columns, so NaN leaks straight
    through into json.dumps() as a bare `NaN` token - which is invalid JSON
    and breaks JS's JSON.parse() on the frontend. Going through
    clean_for_json() after to_dict() avoids that re-coercion entirely.
    """
    if df is None or not hasattr(df, "to_dict"):
        return []
    records = df.to_dict(orient="records")
    return clean_for_json(records)
