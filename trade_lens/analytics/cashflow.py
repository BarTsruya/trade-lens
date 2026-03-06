from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType


def monthly_net_cashflow(
    ledger_df: pd.DataFrame,
    *,
    currency: str = "USD",
    include_deposits: bool = True,
) -> pd.DataFrame:
    """
    Returns monthly sums for net cashflow.

    currency: "USD" -> uses net_usd, "ILS" -> uses net_ils
    """
    df = ledger_df.copy()
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()

    value_col = "net_usd" if currency.upper() == "USD" else "net_ils"

    if not include_deposits:
        allowed = {RawActionType.BUY.value, RawActionType.SELL.value, RawActionType.CASH_HANDLING_FEE_SHEKEL.value}
        df = df[df["action_type"].isin(allowed)]

    out = df.groupby("month", dropna=True, as_index=False)[value_col].sum()
    out.rename(columns={value_col: f"{value_col}_sum"}, inplace=True)
    return out


def monthly_fees_breakdown(ledger_df: pd.DataFrame) -> pd.DataFrame:
    df = ledger_df.copy()
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()

    embedded = (
        df[df["action_type"].isin([RawActionType.BUY.value, RawActionType.SELL.value])]
        .groupby("month", dropna=True, as_index=False)["fees_ils"]
        .sum()
        .rename(columns={"fees_ils": "embedded_fees_ils"})
    )

    cash = (
        df[df["action_type"] == RawActionType.CASH_HANDLING_FEE_SHEKEL.value]
        .groupby("month", dropna=True, as_index=False)["gross_ils"]
        .sum()
        .rename(columns={"gross_ils": "cash_handling_gross_ils"})
    )

    return embedded.merge(cash, on="month", how="outer").fillna(0.0)


__all__ = ["monthly_net_cashflow", "monthly_fees_breakdown"]