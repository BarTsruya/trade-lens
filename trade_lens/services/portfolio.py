from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

_TRADE_ACTIONS = {"buy", "sell"}


@dataclass
class ClosedTrade:
    """A sell action matched to its FIFO buy lots."""

    symbol: str
    paper_name: str
    date_from: pd.Timestamp   # earliest matched buy date
    date_to: pd.Timestamp     # sell date
    # Table rows: buy lots (with qty_used) + the sell row, sorted by date
    rows: pd.DataFrame        # columns: date, action, quantity, price, amount
    total_buy_cost: float
    total_proceeds: float
    realized_pnl: float
    total_fees_usd: float
    total_estimated_tax: float


@dataclass
class HoldingsSummary:
    """Current holdings and closed trade history from the full buy/sell ledger."""

    trades: pd.DataFrame       # all buy/sell rows, sorted by date ascending
    holdings: pd.DataFrame     # open positions: symbol, paper_name, quantity, avg_price, total_cost
    closed_trades: list[ClosedTrade]
    year_options: list[int]    # derived from trade dates, newest first


def _compute_holdings(trades: pd.DataFrame) -> pd.DataFrame:
    """Weighted-average cost basis over all buy/sell rows (sorted by date)."""
    state: dict[str, dict] = {}

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
            s["paper_name"] = name

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


def _compute_closed_trades(trades: pd.DataFrame) -> list[ClosedTrade]:
    """Match sell actions to buy lots using FIFO per symbol."""
    closed: list[ClosedTrade] = []

    for symbol, group in trades.groupby("symbol", sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        buy_queue: deque[dict] = deque()

        for _, row in group.iterrows():
            action = str(row.get("action_type", "") or "")
            qty = abs(float(row.get("quantity") or 0.0))
            price = float(row.get("execution_price") or 0.0)

            if action == "buy":
                fees = abs(float(row.get("fees_usd") or 0.0))
                buy_queue.append({
                    "date": row["date"],
                    "qty_total": qty,
                    "qty_remaining": qty,
                    "price": price,
                    "fees_usd": fees,
                })
            elif action == "sell" and buy_queue:
                qty_to_sell = qty
                matched_lots: list[dict] = []

                while qty_to_sell > 1e-6 and buy_queue:
                    lot = buy_queue[0]
                    used = min(lot["qty_remaining"], qty_to_sell)
                    proportion = used / lot["qty_total"] if lot["qty_total"] > 0 else 0.0
                    matched_lots.append({
                        "date": lot["date"],
                        "action": "Buy",
                        "quantity": used,
                        "price": lot["price"],
                        "amount": used * lot["price"],
                        "fees_usd": lot["fees_usd"] * proportion,
                    })
                    lot["qty_remaining"] -= used
                    qty_to_sell -= used
                    if lot["qty_remaining"] < 1e-6:
                        buy_queue.popleft()

                if not matched_lots:
                    continue

                proceeds = abs(float(row.get("delta_usd") or 0.0))
                sell_fees = abs(float(row.get("fees_usd") or 0.0))
                estimated_tax = abs(float(row.get("estimated_capital_gains_tax") or 0.0))
                total_buy_cost = sum(l["amount"] for l in matched_lots)
                total_fees = sum(l["fees_usd"] for l in matched_lots) + sell_fees

                sell_entry = {
                    "date": row["date"],
                    "action": "Sell",
                    "quantity": qty,
                    "price": price,
                    "amount": proceeds,
                }

                all_rows = pd.DataFrame(matched_lots + [sell_entry])
                all_rows["date"] = pd.to_datetime(all_rows["date"], errors="coerce")
                all_rows.sort_values("date", inplace=True)
                all_rows.reset_index(drop=True, inplace=True)

                closed.append(ClosedTrade(
                    symbol=str(symbol),
                    paper_name=str(row.get("paper_name", "") or ""),
                    date_from=pd.to_datetime(matched_lots[0]["date"]),
                    date_to=pd.to_datetime(row["date"]),
                    rows=all_rows,
                    total_buy_cost=total_buy_cost,
                    total_proceeds=proceeds,
                    realized_pnl=proceeds - total_buy_cost,
                    total_fees_usd=total_fees,
                    total_estimated_tax=estimated_tax,
                ))

    closed.sort(key=lambda x: x.date_to, reverse=True)
    return closed


def get_holdings_summary(ledger: pd.DataFrame) -> HoldingsSummary:
    """Compute current holdings and closed trades from the full ledger."""
    trades = ledger[ledger["action_type"].isin(_TRADE_ACTIONS)].copy()
    trades = trades.sort_values("date").reset_index(drop=True)

    dates = pd.to_datetime(trades["date"], errors="coerce")
    year_options = sorted(dates.dt.year.dropna().astype(int).unique().tolist(), reverse=True)

    holdings = _compute_holdings(trades)
    closed_trades = _compute_closed_trades(trades)

    return HoldingsSummary(
        trades=trades,
        holdings=holdings,
        closed_trades=closed_trades,
        year_options=year_options,
    )


__all__ = ["ClosedTrade", "HoldingsSummary", "get_holdings_summary"]
