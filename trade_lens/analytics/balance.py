from __future__ import annotations

import re
from typing import List

import pandas as pd

from trade_lens.brokers.ibi import RawActionType


EMPTY_COLUMNS = [
    "date",
    "action_type",
    "action_description",
    "fees_usd",
    "usd_delta",
    "ils_delta",
    "usd_balance",
    "ils_balance",
    "expected_ils_balance",
]


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(columns=EMPTY_COLUMNS)


def balance_timeline_actions(ledger_df: pd.DataFrame) -> pd.DataFrame:
    df = ledger_df.copy()

    if "date" not in df.columns:
        return _empty_result()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.loc[df["date"].notna()].copy()
    if df.empty:
        return _empty_result()

    # Preserve stable source order for rows on the same date.
    df["_seq"] = range(len(df))

    for col in ("action_type", "symbol", "paper_name"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype("string")

    for col in ("delta_usd", "delta_ils", "fees_usd", "quantity", "execution_price"):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Keep only actions that affect cash.
    cash_mask = (df["delta_usd"] != 0) | (df["delta_ils"] != 0) | (df["fees_usd"] != 0)
    out = df.loc[cash_mask].copy()
    if out.empty:
        return _empty_result()

    transfer_action = RawActionType.CASH_DEPOSIT.value
    conversion_action = RawActionType.FX_CONVERSION.value
    other_cash_actions = {RawActionType.OTHER_CASH.value}
    buy_action = RawActionType.BUY.value
    sell_action = RawActionType.SELL.value

    def build_note(row: pd.Series) -> str:
        action_type = str(row.get("action_type", "") or "")
        symbol = str(row.get("symbol", "") or "")
        quantity = float(row.get("quantity", 0.0) or 0.0)
        execution_price = float(row.get("execution_price", 0.0) or 0.0)
        usd_delta = float(row.get("delta_usd", 0.0) or 0.0)
        ils_delta = float(row.get("delta_ils", 0.0) or 0.0)
        paper_name = str(row.get("paper_name", "") or "")

        if action_type == transfer_action:
            if ils_delta != 0:
                return f"deposit of {abs(ils_delta):,.2f}₪"
            return f"deposit of {abs(usd_delta):,.2f}$"

        if action_type == conversion_action:
            _rate_match = re.search(r"[A-Z]+/[A-Z]+\s+[\d.]+", paper_name)
            rate_part = f" (rate: {_rate_match.group()})" if _rate_match else ""
            return f"converted {abs(ils_delta):,.2f}₪ to ${abs(usd_delta):,.2f}{rate_part}"

        if action_type in other_cash_actions:
            return paper_name or action_type

        if action_type in (buy_action, sell_action):
            total_cost = abs(execution_price * quantity)
            verb = "bought" if action_type == buy_action else "sold"
            ticker_part = f" {symbol}" if symbol else ""
            return f"{verb}{ticker_part} for ${total_cost:,.2f}"

        if action_type == RawActionType.DIVIDEND_TAX.value:
            return "dividend tax payment"

        if action_type == RawActionType.DIVIDEND_DEPOSIT.value:
            return "dividend deposit"

        if action_type == RawActionType.TAX_CREDIT.value:
            return "tax credit"

        if action_type == RawActionType.TAX_PAYMENT.value:
            return "gain tax payment"

        if action_type == RawActionType.ACCOUNT_MAINTENANCE_FEE.value:
            return "account maintenance fee"

        parts: List[str] = [action_type]
        if symbol:
            parts.append(symbol)
        return " ".join([p for p in parts if p]).strip()

    out["action_description"] = out.apply(build_note, axis=1).fillna("").astype("string")

    # Keep the original ledger index labels for traceability.
    out.sort_values(by=["date", "_seq"], inplace=True, kind="mergesort")

    out["usd_delta"] = out["delta_usd"]
    trade_mask = out["action_type"].isin([buy_action, sell_action])
    if trade_mask.any():
        total_cost_usd = out["execution_price"].abs() * out["quantity"].abs()
        fee_usd = out["fees_usd"].abs()
        buy_mask = out["action_type"] == buy_action
        sell_mask = out["action_type"] == sell_action

        out.loc[buy_mask, "usd_delta"] = -(total_cost_usd.loc[buy_mask] + fee_usd.loc[buy_mask])
        out.loc[sell_mask, "usd_delta"] = total_cost_usd.loc[sell_mask] - fee_usd.loc[sell_mask]

    out["ils_delta"] = out["delta_ils"]
    out["usd_balance"] = out["usd_delta"].cumsum()
    out["ils_balance"] = out["ils_delta"].cumsum()
    if "expected_ils_balance" in out.columns:
        out["expected_ils_balance"] = pd.to_numeric(out["expected_ils_balance"], errors="coerce")
    else:
        out["expected_ils_balance"] = pd.NA
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date

    return out[EMPTY_COLUMNS]


__all__ = ["balance_timeline_actions"]
