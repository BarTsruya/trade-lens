from __future__ import annotations

from typing import List

import pandas as pd

from trade_lens.brokers.ibi import RawActionType


EMPTY_COLUMNS = ["date", "note", "usd_delta", "ils_delta", "usd_balance", "ils_balance"]


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(columns=EMPTY_COLUMNS)


def _format_amount(value: float, currency: str) -> str:
    return f"{value:+,.2f} {currency}"


def balance_timeline_daily(ledger_df: pd.DataFrame) -> pd.DataFrame:
    df = ledger_df.copy()

    if "date" not in df.columns or "action_type" not in df.columns:
        return _empty_result()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    if df.empty:
        return _empty_result()

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
        return _empty_result()

    if "delta_ils" not in df.columns or "delta_usd" not in df.columns:
        return _empty_result()

    df["day"] = df["date"].dt.normalize()

    df["ils_delta_row"] = pd.to_numeric(df["delta_ils"], errors="coerce").fillna(0.0)

    conversion_mask = (df["action_type"] == conversion_action) & (df["symbol"] == "99028")
    has_conversion_rows = bool(conversion_mask.any())
    if has_conversion_rows and "quantity" not in df.columns:
        raise ValueError(
            "Ledger is missing 'quantity' column required to compute USD delta for conversions. "
            "Update to_ledger() to include quantity."
        )

    if "quantity" not in df.columns:
        df["quantity"] = 0.0
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
    if has_conversion_rows:
        conversion_qty = df.loc[conversion_mask, "quantity"]
        if (abs(conversion_qty.sum()) < 1e-12) or conversion_qty.eq(0).all():
            raise ValueError(
                "Conversion rows detected but 'quantity' sums to 0 (or all values are 0). "
                "The raw export or normalization is likely missing Quantity."
            )

    # Conversion USD delta should come from canonical delta_usd (which normalization maps from quantity).
    df["usd_delta_row"] = 0.0
    df.loc[conversion_mask, "usd_delta_row"] = pd.to_numeric(
        df.loc[conversion_mask, "delta_usd"], errors="coerce"
    ).fillna(0.0)

    daily = (
        df.groupby("day", as_index=False)
        .agg(
            usd_delta=("usd_delta_row", "sum"),
            ils_delta=("ils_delta_row", "sum"),
            fx_info=(
                "paper_name",
                lambda s: "; ".join(dict.fromkeys([v for v in s.tolist() if isinstance(v, str) and v.strip()])),
            ),
        )
        .fillna({"fx_info": ""})
    )

    transfer_daily = (
        df[df["action_type"] == transfer_action]
        .groupby("day", as_index=False)["ils_delta_row"]
        .sum()
        .rename(columns={"ils_delta_row": "ils_deposit_ils"})
    )

    conversion_daily = (
        df[(df["action_type"] == conversion_action) & (df["symbol"] == "99028")]
        .groupby("day", as_index=False)
        .agg(conv_usd=("usd_delta_row", "sum"), conv_ils=("ils_delta_row", "sum"))
    )

    out = daily.merge(transfer_daily, on="day", how="left").merge(conversion_daily, on="day", how="left")
    out[["ils_deposit_ils", "conv_usd", "conv_ils"]] = out[["ils_deposit_ils", "conv_usd", "conv_ils"]].fillna(0.0)

    def build_note(row: pd.Series) -> str:
        parts: List[str] = []

        if row["ils_deposit_ils"] != 0:
            parts.append(f"ILS deposit: {_format_amount(row['ils_deposit_ils'], 'ILS')}")

        has_conversion = (row["conv_usd"] != 0) or (row["conv_ils"] != 0)
        if has_conversion:
            conversion_text = (
                f"ILS->USD conversion: {abs(row['conv_ils']):,.2f} ILS -> "
                f"{abs(row['conv_usd']):,.2f} USD"
            )
            if row["fx_info"]:
                conversion_text = f"{conversion_text} (rate: {row['fx_info']})"
            parts.append(conversion_text)

        return "; ".join(parts)

    out["note"] = out.apply(build_note, axis=1).fillna("").astype("string")

    out.sort_values(by="day", inplace=True, kind="mergesort")
    out.reset_index(drop=True, inplace=True)
    out["usd_balance"] = out["usd_delta"].cumsum()
    out["ils_balance"] = out["ils_delta"].cumsum()
    out["date"] = pd.to_datetime(out["day"], errors="coerce").dt.date

    return out[EMPTY_COLUMNS]


__all__ = ["balance_timeline_daily"]
