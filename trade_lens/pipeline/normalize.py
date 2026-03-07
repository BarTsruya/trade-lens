from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType, RawDataAttribute

BUY_SELL_ACTIONS = {RawActionType.BUY.value, RawActionType.SELL.value}


def to_ledger(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Canonical output columns:
      - date
      - action_type
      - symbol
      - gross_usd (signed, from total_value_foreign)
      - fees_usd (>= 0, from commission_fee + additional_fees; IBI export uses USD fees)
      - net_usd (signed)
      - gross_ils (signed, from total_value_shekel; may be 0 for trade rows)
      - net_ils (signed; v1: equals gross_ils, no FX conversion and no fee subtraction)
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

    df["gross_usd"] = df[gross_usd_col].fillna(0.0) if gross_usd_col in df.columns else 0.0
    df["gross_ils"] = df[gross_ils_col].fillna(0.0) if gross_ils_col in df.columns else 0.0

    # Fees are ALWAYS in USD in your IBI export
    df["fees_usd"] = 0.0
    if commission_col in df.columns:
        df["fees_usd"] = df["fees_usd"] + df[commission_col].fillna(0.0)
    if add_fees_col in df.columns:
        df["fees_usd"] = df["fees_usd"] + df[add_fees_col].fillna(0.0)

    df[action_col] = df[action_col].astype("string")
    is_trade = df[action_col].isin(BUY_SELL_ACTIONS)

    df["net_usd"] = df["gross_usd"]
    df.loc[is_trade, "net_usd"] = df.loc[is_trade, "gross_usd"] - df.loc[is_trade, "fees_usd"]

    # v1: do not convert and do not subtract USD fees from ILS amounts
    df["net_ils"] = df["gross_ils"]

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce"),
            "action_type": df[action_col],
            "symbol": df[symbol_col] if symbol_col in df.columns else None,
            "gross_usd": df["gross_usd"],
            "fees_usd": df["fees_usd"],
            "net_usd": df["net_usd"],
            "gross_ils": df["gross_ils"],
            "net_ils": df["net_ils"],
        }
    )

    out.sort_values(by="date", inplace=True, kind="mergesort", na_position="last")
    out.reset_index(drop=True, inplace=True)
    return out


__all__ = ["to_ledger"]