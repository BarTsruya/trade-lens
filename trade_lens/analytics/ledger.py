from __future__ import annotations

import datetime
from typing import Sequence

import pandas as pd


def filter_ledger(
    ledger: pd.DataFrame,
    *,
    date_range: tuple[datetime.date, datetime.date] | None = None,
    action_types: Sequence[str] | None = None,
    symbols: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Return a filtered copy of the ledger matching all provided criteria.

    All filters are optional; omitting one means no restriction on that dimension.

    Parameters
    ----------
    ledger:       Full canonical ledger DataFrame.
    date_range:   (start, end) inclusive date filter, or None for no date filter.
    action_types: Whitelist of action_type string values, or None for all types.
    symbols:      Whitelist of symbol string values, or None for all symbols.
    """
    df = ledger.copy()

    date_series = pd.to_datetime(df.get("date"), errors="coerce")
    df = df.loc[date_series.notna()].copy()

    if date_range is not None:
        start_date, end_date = date_range
        if start_date and end_date:
            row_dates = pd.to_datetime(df["date"], errors="coerce").dt.date
            df = df.loc[(row_dates >= start_date) & (row_dates <= end_date)].copy()

    if action_types:
        df = df.loc[df["action_type"].astype("string").isin(action_types)].copy()

    if symbols:
        df = df.loc[df["symbol"].astype("string").isin(symbols)].copy()

    return df


def ledger_date_bounds(
    ledger: pd.DataFrame,
) -> tuple[datetime.date | None, datetime.date | None]:
    """Return (min_date, max_date) of the ledger's date column as Python date objects."""
    dates = pd.to_datetime(ledger.get("date"), errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min().date(), dates.max().date()


def ledger_action_options(ledger: pd.DataFrame) -> list[str]:
    """Return a sorted list of non-empty action_type values present in the ledger."""
    return sorted(
        v
        for v in ledger.get("action_type", pd.Series(dtype="string"))
        .astype("string")
        .dropna()
        .unique()
        .tolist()
        if str(v).strip()
    )


def ledger_symbol_options(ledger: pd.DataFrame) -> list[str]:
    """Return a sorted list of non-empty symbol values present in the ledger."""
    return sorted(
        v
        for v in ledger.get("symbol", pd.Series(dtype="string"))
        .astype("string")
        .dropna()
        .unique()
        .tolist()
        if str(v).strip()
    )


__all__ = [
    "filter_ledger",
    "ledger_date_bounds",
    "ledger_action_options",
    "ledger_symbol_options",
]
