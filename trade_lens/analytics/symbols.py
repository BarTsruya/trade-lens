from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType


def symbol_summary(ledger_df: pd.DataFrame, *, currency: str = "USD") -> pd.DataFrame:
    df = ledger_df.copy()
    df = df[df["action_type"].isin([RawActionType.BUY.value, RawActionType.SELL.value])]
    df["symbol"] = df["symbol"].fillna("UNKNOWN")

    delta_col = "delta_usd" if currency.upper() == "USD" else "delta_ils"

    out = df.groupby("symbol", as_index=False).agg(
        net_sum=(delta_col, "sum"),
        delta_abs_sum=(delta_col, lambda s: s.abs().sum()),
        trades=("symbol", "count"),
    )
    out.sort_values(by="delta_abs_sum", ascending=False, inplace=True)
    return out


__all__ = ["symbol_summary"]