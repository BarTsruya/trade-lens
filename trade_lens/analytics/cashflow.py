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


__all__ = ["monthly_fees_breakdown"]