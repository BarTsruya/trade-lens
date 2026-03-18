from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType


def monthly_fees_breakdown(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """
    Monthly fees breakdown.

    Notes:
    - IBI commission_fee/additional_fees are USD in your export -> aggregated as `fees_usd`
    - Account maintenance fee is aggregated from `delta_ils`
    """
    df = ledger_df.copy()
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()

    embedded = (
        df[df["action_type"].isin([RawActionType.BUY.value, RawActionType.SELL.value])]
        .groupby("month", dropna=True, as_index=False)["fees_usd"]
        .sum()
        .rename(columns={"fees_usd": "embedded_fees_usd"})
    )

    cash = (
        df[df["action_type"] == RawActionType.ACCOUNT_MAINTENANCE_FEE.value]
        .groupby("month", dropna=True, as_index=False)["delta_ils"]
        .sum()
        .rename(columns={"delta_ils": "cash_handling_delta_ils"})
    )

    return embedded.merge(cash, on="month", how="outer").fillna(0.0)


def build_trading_fees_ledger(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Return BUY/SELL rows with non-zero fees_usd, normalized for display."""
    if "action_type" not in ledger_df.columns:
        return pd.DataFrame()

    df = ledger_df.loc[
        ledger_df["action_type"].isin([RawActionType.BUY.value, RawActionType.SELL.value])
    ].copy()
    if "fees_usd" in df.columns:
        df = df.loc[pd.to_numeric(df["fees_usd"], errors="coerce").fillna(0.0) > 0].copy()
    if df.empty:
        return pd.DataFrame()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.loc[df["date"].notna()].copy()
    if df.empty:
        return pd.DataFrame()

    df["amount_value"] = pd.to_numeric(df["fees_usd"], errors="coerce").fillna(0.0)
    df["amount"] = "$" + df["amount_value"].map(lambda v: f"{float(v):,.2f}")

    result_cols = ["date", "paper_name", "amount", "amount_value"]
    return df[[c for c in result_cols if c in df.columns]].copy()


def build_maintenance_fees_ledger(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Return ACCOUNT_MAINTENANCE_FEE rows normalized for display."""
    if "action_type" not in ledger_df.columns:
        return pd.DataFrame()

    df = ledger_df.loc[
        ledger_df["action_type"] == RawActionType.ACCOUNT_MAINTENANCE_FEE.value
    ].copy()
    if df.empty:
        return pd.DataFrame()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.loc[df["date"].notna()].copy()
    if df.empty:
        return pd.DataFrame()

    df["amount_value"] = pd.to_numeric(df.get("delta_ils"), errors="coerce").fillna(0.0).abs()
    df["amount"] = "₪" + df["amount_value"].map(lambda v: f"{float(v):,.2f}")

    result_cols = ["date", "amount", "amount_value"]
    return df[[c for c in result_cols if c in df.columns]].copy()


__all__ = ["monthly_fees_breakdown", "build_trading_fees_ledger", "build_maintenance_fees_ledger"]