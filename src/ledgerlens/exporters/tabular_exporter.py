"""Export DataFrame sections to CSV / Excel bytes or files."""

from io import BytesIO
from pathlib import Path

import pandas as pd


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def save_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".csv":
        df.to_csv(path, index=False)
    elif path.suffix in (".xlsx", ".xls"):
        df.to_excel(path, index=False, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported extension: {path.suffix}")
