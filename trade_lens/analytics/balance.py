from __future__ import annotations

import pandas as pd
from typing import List

from trade_lens.brokers.ibi import RawActionType


def _format_amount(value: float, currency: str) -> str:
    return f"{value:+,.2f} {currency}"


def balance_timeline_daily(ledger_df: pd.DataFrame) -> pd.DataFrame:
    df = ledger_df.copy()

    if "date" not in df.columns or "action_type" not in df.columns:
        return pd.DataFrame(columns=["day", "note", "usd_delta", "ils_delta", "usd_balance", "ils_balance"])

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=["day", "note", "usd_delta", "ils_delta", "usd_balance", "ils_balance"])

    for col in ("action_type", "symbol", "paper_name"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype("string")

    transfer_action = RawActionType.TRANSFER_CASH_SHEKEL.value
    conversion_action = RawActionType.PURCHASE_SHEKEL.value

    is_transfer = df["action_type"] == transfer_action
    is_conversion = (df["action_type"] == conversion_action) & (df["symbol"] == "99028")

    df = df[is_transfer | is_conversion].copy()
    if df.empty:
        return pd.DataFrame(columns=["day", "note", "usd_delta", "ils_delta", "usd_balance", "ils_balance"])

    df["day"] = df["date"].dt.normalize()

    usd_source = "net_usd" if "net_usd" in df.columns else "gross_usd"
    ils_source = "net_ils" if "net_ils" in df.columns else "gross_ils"

    df["usd_delta"] = pd.to_numeric(df[usd_source], errors="coerce").fillna(0.0)
    df["ils_delta"] = pd.to_numeric(df[ils_source], errors="coerce").fillna(0.0)

    # Aggregate daily totals and keep unique paper_name values for rate text.
    daily = (
        df.groupby("day", as_index=False)
        .agg(
            usd_delta=("usd_delta", "sum"),
            ils_delta=("ils_delta", "sum"),
            fx_info=(
                "paper_name",
                lambda s: "; ".join(dict.fromkeys([v for v in s if isinstance(v, str) and v.strip()])),
            ),
        )
        .fillna({"fx_info": ""})
    )

    transfer_daily = (
        df[is_transfer.loc[df.index]]
        .groupby("day", as_index=False)["ils_delta"]
        .sum()
        .rename(columns={"ils_delta": "ils_deposit_ils"})
    )

    conversion_daily = (
        df[is_conversion.loc[df.index]]
        .groupby("day", as_index=False)
        .agg(conv_usd=("usd_delta", "sum"), conv_ils=("ils_delta", "sum"))
    )

    out = daily.merge(transfer_daily, on="day", how="left").merge(conversion_daily, on="day", how="left")
    out[["ils_deposit_ils", "conv_usd", "conv_ils"]] = out[["ils_deposit_ils", "conv_usd", "conv_ils"]].fillna(0.0)

    def build_note(row: pd.Series) -> str:
        parts: List[str] = []

        if row["ils_deposit_ils"] != 0:
            parts.append(f"ILS deposit: {_format_amount(row['ils_deposit_ils'], 'ILS')}")

        has_conversion = (row["conv_usd"] != 0) or (row["conv_ils"] != 0)
        if has_conversion:
            conv_text = (
                f"ILS->USD conversion: {_format_amount(row['conv_ils'], 'ILS')}, "
                f"{_format_amount(row['conv_usd'], 'USD')}"
            )
            if row["fx_info"]:
                conv_text = f"{conv_text} (rate: {row['fx_info']})"
            parts.append(conv_text)

        return "; ".join(parts)

    out["note"] = out.apply(build_note, axis=1)

    out.sort_values(by="day", inplace=True, kind="mergesort")
    out.reset_index(drop=True, inplace=True)
    out["usd_balance"] = out["usd_delta"].cumsum()
    out["ils_balance"] = out["ils_delta"].cumsum()

    return out[["day", "note", "usd_delta", "ils_delta", "usd_balance", "ils_balance"]]


__all__ = ["balance_timeline_daily"]
