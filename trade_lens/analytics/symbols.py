from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType


def symbol_summary(ledger_df: pd.DataFrame, *, currency: str = "USD") -> pd.DataFrame:
    df = ledger_df.copy()
    df = df[df["action_type"].isin([RawActionType.BUY.value, RawActionType.SELL.value])]
    df["symbol"] = df["symbol"].fillna("UNKNOWN")

    net_col = "net_usd" if currency.upper() == "USD" else "net_ils"
    gross_col = "gross_usd" if currency.upper() == "USD" else "gross_ils"

    out = df.groupby("symbol", as_index=False).agg(
        net_sum=(net_col, "sum"),
        gross_abs_sum=(gross_col, lambda s: s.abs().sum()),
        trades=("symbol", "count"),
    )
    out.sort_values(by="gross_abs_sum", ascending=False, inplace=True)
    return out


__all__ = ["symbol_summary"]