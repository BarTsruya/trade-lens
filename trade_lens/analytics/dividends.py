from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType


DIVIDEND_TAX_ACTION_TYPES = {RawActionType.DIVIDEND_TAX.value}
DIVIDEND_DEPOSIT_ACTION_TYPES = {RawActionType.DIVIDEND_DEPOSIT.value}


def build_dividend_tax_ledger(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Return normalized dividend-tax rows with amount_value and amount formatting."""
    if "action_type" not in ledger_df.columns:
        return pd.DataFrame()

    df = ledger_df.loc[
        ledger_df["action_type"].astype("string").isin(DIVIDEND_TAX_ACTION_TYPES)
    ].copy()
    if df.empty:
        return pd.DataFrame()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.loc[df["date"].notna()].copy()
    if df.empty:
        return pd.DataFrame()

    usd_abs = pd.to_numeric(df.get("delta_usd"), errors="coerce").fillna(0.0).abs()
    ils_abs = pd.to_numeric(df.get("delta_ils"), errors="coerce").fillna(0.0).abs()
    is_usd = usd_abs > 0

    df["amount_value"] = usd_abs.where(is_usd, ils_abs)
    df["amount_currency"] = pd.Series("₪", index=df.index, dtype="string")
    df.loc[is_usd, "amount_currency"] = "$"
    df["amount"] = df["amount_currency"].astype(str) + df["amount_value"].map(lambda v: f"{float(v):,.2f}")

    result_cols = ["date", "action_type", "paper_name", "amount", "amount_value", "amount_currency"]
    for optional_col in ("symbol", "currency", "source_file", "_display_idx"):
        if optional_col in df.columns:
            result_cols.append(optional_col)

    return df[result_cols].copy()


def build_dividend_deposit_ledger(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Return normalized dividend-deposit rows with amount_value and amount formatting."""
    if "action_type" not in ledger_df.columns:
        return pd.DataFrame()

    df = ledger_df.loc[
        ledger_df["action_type"].astype("string").isin(DIVIDEND_DEPOSIT_ACTION_TYPES)
    ].copy()
    if df.empty:
        return pd.DataFrame()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.loc[df["date"].notna()].copy()
    if df.empty:
        return pd.DataFrame()

    usd_abs = pd.to_numeric(df.get("delta_usd"), errors="coerce").fillna(0.0).abs()
    ils_abs = pd.to_numeric(df.get("delta_ils"), errors="coerce").fillna(0.0).abs()
    is_usd = usd_abs > 0

    df["amount_value"] = usd_abs.where(is_usd, ils_abs)
    df["amount_currency"] = pd.Series("₪", index=df.index, dtype="string")
    df.loc[is_usd, "amount_currency"] = "$"
    df["amount"] = df["amount_currency"].astype(str) + df["amount_value"].map(lambda v: f"{float(v):,.2f}")

    result_cols = ["date", "paper_name", "amount", "amount_value", "amount_currency"]
    for optional_col in ("symbol", "currency", "source_file", "_display_idx"):
        if optional_col in df.columns:
            result_cols.append(optional_col)

    return df[result_cols].copy()


def dividend_deposit_year_options(df: pd.DataFrame) -> list[int]:
    """Return sorted years available in dividend deposit data, newest first."""
    if df.empty or "date" not in df.columns:
        return []
    dates = pd.to_datetime(df["date"], errors="coerce")
    return sorted(dates.dt.year.dropna().unique().astype(int), reverse=True)


def build_monthly_amount_series(
    df: pd.DataFrame,
    *,
    selected_year: int,
    amount_column: str,
    output_column: str,
) -> pd.DataFrame:
    """Return a canonical 12-month series for ``amount_column`` in ``selected_year``."""
    months_df = pd.DataFrame({"month": pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS")})
    if df.empty or "date" not in df.columns or amount_column not in df.columns:
        return months_df.assign(**{output_column: 0.0})

    grouped = df.copy()
    grouped["month"] = pd.to_datetime(grouped["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    monthly = (
        grouped.groupby("month")[amount_column]
        .sum()
        .reset_index(name=output_column)
    )
    return months_df.merge(monthly, on="month", how="left").fillna(0.0)


__all__ = [
    "DIVIDEND_TAX_ACTION_TYPES",
    "DIVIDEND_DEPOSIT_ACTION_TYPES",
    "build_dividend_tax_ledger",
    "build_dividend_deposit_ledger",
    "dividend_deposit_year_options",
    "build_monthly_amount_series",
]
