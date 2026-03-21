from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

_TRADE_ACTIONS = {"buy", "sell"}


@dataclass
class HoldingsSummary:
    """Current holdings computed from the full buy/sell history."""

    # All buy/sell rows across all time, sorted by date ascending
    trades: pd.DataFrame

    # Current open positions: one row per ticker with quantity > 0
    # Columns: symbol, paper_name, quantity, avg_price, total_cost
    holdings: pd.DataFrame

    # Year options derived from trade dates (for history filtering)
    year_options: list[int]


def _compute_holdings(trades: pd.DataFrame) -> pd.DataFrame:
    """Weighted-average cost basis over all buy/sell rows (sorted by date)."""
    state: dict[str, dict] = {}  # symbol -> {quantity, avg_price, total_cost, paper_name}

    for _, row in trades.sort_values("date").iterrows():
        symbol = str(row.get("symbol", "") or "").strip()
        if not symbol:
            continue

        qty = abs(float(row.get("quantity") or 0.0))
        price = float(row.get("execution_price") or 0.0)
        action = str(row.get("action_type", "") or "")
        name = str(row.get("paper_name", "") or "")

        if symbol not in state:
            state[symbol] = {"quantity": 0.0, "avg_price": 0.0, "total_cost": 0.0, "paper_name": name}

        s = state[symbol]
        if name:
            s["paper_name"] = name  # keep most recent name

        if action == "buy":
            new_qty = s["quantity"] + qty
            new_cost = s["total_cost"] + qty * price
            s["quantity"] = new_qty
            s["total_cost"] = new_cost
            s["avg_price"] = new_cost / new_qty if new_qty > 0 else 0.0
        elif action == "sell":
            new_qty = s["quantity"] - qty
            s["quantity"] = max(new_qty, 0.0)
            s["total_cost"] = s["avg_price"] * s["quantity"]

    rows = [
        {
            "symbol": sym,
            "paper_name": s["paper_name"],
            "quantity": s["quantity"],
            "avg_price": s["avg_price"],
            "total_cost": s["total_cost"],
        }
        for sym, s in state.items()
        if s["quantity"] > 0.0001
    ]

    if not rows:
        return pd.DataFrame(columns=["symbol", "paper_name", "quantity", "avg_price", "total_cost"])

    df = pd.DataFrame(rows)
    df.sort_values("total_cost", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def get_holdings_summary(ledger: pd.DataFrame) -> HoldingsSummary:
    """Compute current holdings from the full ledger's buy/sell history."""
    trades = ledger[ledger["action_type"].isin(_TRADE_ACTIONS)].copy()
    trades = trades.sort_values("date").reset_index(drop=True)

    dates = pd.to_datetime(trades["date"], errors="coerce")
    year_options = sorted(dates.dt.year.dropna().astype(int).unique().tolist(), reverse=True)

    holdings = _compute_holdings(trades)

    return HoldingsSummary(
        trades=trades,
        holdings=holdings,
        year_options=year_options,
    )


__all__ = ["HoldingsSummary", "get_holdings_summary"]
