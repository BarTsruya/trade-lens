from __future__ import annotations

import pandas as pd


def df_dates_to_date_only(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with date-like columns converted to Python date values."""
    out = df.copy()
    for col in out.columns:
        is_named_date = col == "date" or col.endswith("_date")
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype(out[col])
        if not (is_named_date or is_datetime_dtype):
            continue
        try:
            converted = pd.to_datetime(out[col], errors="coerce")
            if converted.notna().any():
                out[col] = converted.dt.date
        except Exception:
            continue
    return out


def order_table_newest_first_with_chrono_index(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """Display newest rows first while index labels start at 1 for the oldest row.

    If a ``_display_idx`` column is present it is used as the index label source,
    preserving alignment with the full unfiltered ledger.
    """
    if date_col not in df.columns:
        return df.copy()

    out = df.copy()
    out["_sort_date"] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.loc[out["_sort_date"].notna()].copy()
    if out.empty:
        return out.drop(columns=["_sort_date"], errors="ignore")

    if "_display_idx" in out.columns:
        out["_chrono_index"] = pd.to_numeric(out["_display_idx"], errors="coerce")
        if out["_chrono_index"].isna().any():
            out.sort_values(by="_sort_date", ascending=True, kind="mergesort", inplace=True)
            out["_chrono_index"] = range(1, len(out) + 1)
    else:
        out.sort_values(by="_sort_date", ascending=True, kind="mergesort", inplace=True)
        out["_chrono_index"] = range(1, len(out) + 1)

    out.sort_values(
        by=["_sort_date", "_chrono_index"], ascending=[False, False], kind="mergesort", inplace=True
    )
    out.index = out["_chrono_index"].astype(int)
    out.index.name = None
    out.drop(columns=["_sort_date", "_chrono_index"], inplace=True)
    return out


def format_signed_currency(value: object, symbol: str) -> str:
    """Format a numeric value as signed currency: e.g. ``-₪1,234.56`` or ``$0.00``."""
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return ""
    prefix = "-" if numeric < 0 else ""
    return f"{prefix}{symbol}{abs(float(numeric)):,.2f}"
