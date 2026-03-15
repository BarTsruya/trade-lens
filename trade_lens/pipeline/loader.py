from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Sequence

import pandas as pd

from trade_lens.brokers.ibi import load_single, RawDataAttribute
from trade_lens.pipeline.normalize import to_ledger


def load_and_normalize_many(
    file_payloads: Sequence[tuple[str, bytes]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load multiple (filename, bytes) payloads and return (raw, ledger) DataFrames.

    The returned ledger is stably sorted by date with same-day ordering preserved
    from the source file row order, and has a ``_display_idx`` column assigned
    (1 = oldest row, N = newest row).
    """
    raw_frames: list[pd.DataFrame] = []
    ledger_frames: list[pd.DataFrame] = []

    for file_name, file_bytes in file_payloads:
        suffix = Path(file_name).suffix or ".xlsx"
        temp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                temp_path = tmp.name

            raw_df_i = load_single(temp_path).copy()
            raw_df_i["source_file"] = file_name
            raw_df_i["_source_order"] = range(len(raw_df_i))

            date_col = RawDataAttribute.ACTION_DATE.value
            if date_col in raw_df_i.columns:
                raw_dates = pd.to_datetime(raw_df_i[date_col], dayfirst=True, errors="coerce")
                valid_dates = raw_dates.dropna()
                is_desc = bool(len(valid_dates) >= 2 and valid_dates.iloc[0] > valid_dates.iloc[-1])
                raw_df_i[date_col] = raw_dates
            else:
                is_desc = False
            raw_df_i["_date_desc"] = is_desc

            ledger_df_i = to_ledger(raw_df_i).copy()
            ledger_df_i["source_file"] = file_name
            ledger_df_i["ledger_row_id"] = [f"{file_name}:{idx}" for idx in ledger_df_i.index]

            raw_frames.append(raw_df_i)
            ledger_frames.append(ledger_df_i)
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    if not raw_frames or not ledger_frames:
        return pd.DataFrame(), pd.DataFrame()

    raw_all = pd.concat(raw_frames, ignore_index=True)
    ledger_all = pd.concat(ledger_frames, ignore_index=True)

    for col in ("symbol", "action_type", "paper_name", "source_file", "ledger_row_id"):
        if col in ledger_all.columns:
            ledger_all[col] = ledger_all[col].fillna("").astype("string")

    ledger_all = sort_ledger(ledger_all)
    return raw_all, ledger_all


def sort_ledger(ledger: pd.DataFrame) -> pd.DataFrame:
    """Sort a ledger DataFrame chronologically with stable same-day ordering.

    Rows on the same date are ordered using ``_source_order`` / ``_date_desc``
    metadata columns when present. Assigns ``_display_idx`` (1 = oldest).
    Returns a new DataFrame; does not mutate the input.
    """
    df = ledger.copy()

    if "date" not in df.columns:
        df["_display_idx"] = range(1, len(df) + 1)
        return df

    date_sort = pd.to_datetime(df["date"], errors="coerce")
    df = df.loc[date_sort.notna()].copy()
    if df.empty:
        df["_display_idx"] = pd.Series(dtype=int)
        return df

    df["_date_sort"] = pd.to_datetime(df["date"], errors="coerce")

    if "_source_order" in df.columns and "_date_desc" in df.columns:
        source_order = pd.to_numeric(df["_source_order"], errors="coerce").fillna(0.0)
        date_desc = df["_date_desc"].fillna(False).astype(bool)
        df["_within_day_sort"] = source_order.where(~date_desc, -source_order)
        df.sort_values(by=["_date_sort", "_within_day_sort"], inplace=True, kind="mergesort")
        df.drop(columns=["_within_day_sort"], inplace=True)
    else:
        secondary = ["source_file"] if "source_file" in df.columns else []
        df.sort_values(by=["_date_sort"] + secondary, inplace=True, kind="mergesort")

    df.drop(columns=["_date_sort"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["_display_idx"] = range(1, len(df) + 1)
    return df


def count_unknown_action_rows(raw: pd.DataFrame) -> int:
    """Return the number of rows with unrecognized (null or empty) action types."""
    if "action_type" not in raw.columns:
        return 0
    series = raw["action_type"].astype("string")
    return int((series.isna() | series.str.strip().eq("")).sum())


__all__ = ["load_and_normalize_many", "sort_ledger", "count_unknown_action_rows"]
