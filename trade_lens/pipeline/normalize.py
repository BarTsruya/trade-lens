from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType, RawDataAttribute

BUY_SELL_ACTIONS = {RawActionType.BUY.value, RawActionType.SELL.value}


def to_ledger(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert broker-mapped raw df into a canonical 'ledger' df for analytics.

    Canonical output columns:
      - date
      - action_type
      - symbol
      - gross_usd (signed, from total_value_foreign)
      - gross_ils (signed, from total_value_shekel)
      - fees_ils (>= 0, from commission_fee + additional_fees)
      - net_usd (signed)
      - net_ils (signed)

    Fee rules:
      - buy/sell: net_ils = gross_ils - fees_ils
      - all other action types: net_ils = gross_ils (avoid double-counting)
      - net_usd defaults to gross_usd (no FX conversion logic in v1)
    """
    df = raw_df.copy()

    date_col = RawDataAttribute.ACTION_DATE.value
    action_col = RawDataAttribute.ACTION_TYPE.value
    symbol_col = RawDataAttribute.PAPER_SYMBOL.value

    gross_usd_col = RawDataAttribute.TOTAL_VALUE_FOREIGN.value
    gross_ils_col = RawDataAttribute.TOTAL_VALUE_SHEKEL.value

    commission_col = RawDataAttribute.COMMISSION_FEE.value
    add_fees_col = RawDataAttribute.ADDITIONAL_FEES.value

    for col in (date_col, action_col):
        if col not in df.columns:
            raise ValueError(f"Missing required column {col!r} in raw_df")

    # numeric coercion
    for col in (gross_usd_col, gross_ils_col, commission_col, add_fees_col):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["fees_ils"] = 0.0
    if commission_col in df.columns:
        df["fees_ils"] = df["fees_ils"] + df[commission_col].fillna(0)
    if add_fees_col in df.columns:
        df["fees_ils"] = df["fees_ils"] + df[add_fees_col].fillna(0)

    df["gross_usd"] = df[gross_usd_col].fillna(0.0) if gross_usd_col in df.columns else 0.0
    df["gross_ils"] = df[gross_ils_col].fillna(0.0) if gross_ils_col in df.columns else 0.0

    df[action_col] = df[action_col].astype("string")
    is_trade = df[action_col].isin(BUY_SELL_ACTIONS)

    df["net_usd"] = df["gross_usd"]
    df["net_ils"] = df["gross_ils"]
    df.loc[is_trade, "net_ils"] = df.loc[is_trade, "gross_ils"] - df.loc[is_trade, "fees_ils"]

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce"),
            "action_type": df[action_col],
            "symbol": df[symbol_col] if symbol_col in df.columns else None,
            "gross_usd": df["gross_usd"],
            "gross_ils": df["gross_ils"],
            "fees_ils": df["fees_ils"],
            "net_usd": df["net_usd"],
            "net_ils": df["net_ils"],
        }
    )

    out.sort_values(by="date", inplace=True, kind="mergesort", na_position="last")
    out.reset_index(drop=True, inplace=True)
    return out


__all__ = ["to_ledger"]