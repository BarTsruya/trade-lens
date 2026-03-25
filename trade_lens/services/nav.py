from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np
import numpy_financial as npf
import pandas as pd


def build_daily_holdings_state(trades: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct the quantity held per symbol for every calendar day.

    Walks trades chronologically, carries the state forward between trade dates.
    Returns a wide DataFrame: index=DatetimeIndex (daily), columns=symbol names,
    values=float quantity.
    """
    if trades.empty:
        return pd.DataFrame()

    trades_sorted = trades.copy()
    trades_sorted["date"] = pd.to_datetime(trades_sorted["date"], errors="coerce")
    trades_sorted = trades_sorted.dropna(subset=["date"]).sort_values("date")

    symbols = [s for s in trades_sorted["symbol"].dropna().unique() if s]
    if not symbols:
        return pd.DataFrame()

    start_date = trades_sorted["date"].min()
    end_date = pd.Timestamp(date.today())
    all_dates = pd.date_range(start_date, end_date, freq="D")

    # Build per-symbol quantity series indexed by trade dates
    qty_state: dict[str, float] = {s: 0.0 for s in symbols}
    # Collect (date, symbol, cumulative_qty) snapshots
    snapshots: list[dict] = []

    for _, row in trades_sorted.iterrows():
        sym = str(row.get("symbol", "") or "")
        if sym not in qty_state:
            continue
        qty = abs(float(row.get("quantity") or 0.0))
        action = str(row.get("action_type", "") or "")
        if action == "buy":
            qty_state[sym] += qty
        elif action == "sell":
            qty_state[sym] = max(qty_state[sym] - qty, 0.0)
        snapshots.append({"date": row["date"], **{s: qty_state[s] for s in symbols}})

    if not snapshots:
        return pd.DataFrame(index=all_dates, columns=symbols, data=0.0)

    snap_df = pd.DataFrame(snapshots).set_index("date")
    # Keep only the last snapshot per date, then reindex to daily and forward-fill
    snap_df = snap_df[~snap_df.index.duplicated(keep="last")]
    daily = snap_df.reindex(all_dates).ffill().fillna(0.0)
    return daily


def compute_nav_timeline(
    trades: pd.DataFrame,
    balance_timeline: pd.DataFrame,
    price_history: pd.DataFrame,
    usdils_history: pd.Series,
) -> pd.DataFrame:
    """Compute a daily NAV series.

    NAV = usd_cash + ils_cash / usdils_rate + sum(qty[sym] * price[sym])

    Parameters
    ----------
    trades:           buy/sell rows from HoldingsSummary.trades
    balance_timeline: output of balance_timeline_actions (has date, usd_balance, ils_balance)
    price_history:    wide DataFrame of daily close prices (index=date, cols=symbols)
    usdils_history:   daily USDILS rate series (ILS per 1 USD)

    Returns DataFrame with columns: date, nav, usd_cash, ils_cash_usd, holdings_value
    """
    if balance_timeline.empty or trades.empty:
        return pd.DataFrame(columns=["date", "nav", "usd_cash", "ils_cash_usd", "holdings_value"])

    # --- Cash balances: daily, carry-forward ---
    bal = balance_timeline.copy()
    bal["date"] = pd.to_datetime(bal["date"], errors="coerce")
    bal = bal.dropna(subset=["date"]).sort_values("date")
    bal["usd_balance"] = pd.to_numeric(bal["usd_balance"], errors="coerce").ffill().fillna(0.0)
    bal["ils_balance"] = pd.to_numeric(bal["ils_balance"], errors="coerce").ffill().fillna(0.0)
    bal = bal.set_index("date")[["usd_balance", "ils_balance"]]
    bal = bal[~bal.index.duplicated(keep="last")]

    start_date = bal.index.min()
    end_date = pd.Timestamp(date.today())
    all_dates = pd.date_range(start_date, end_date, freq="D")

    bal_daily = bal.reindex(all_dates).ffill().fillna(0.0)

    # --- Holdings: daily qty per symbol ---
    holdings_daily = build_daily_holdings_state(trades)
    if holdings_daily.empty:
        holdings_val = pd.Series(0.0, index=all_dates)
    else:
        # Align price_history with dates
        ph = price_history.copy()
        ph.index = pd.to_datetime(ph.index)
        ph = ph.reindex(all_dates).astype(float).ffill().bfill().fillna(0.0)

        holdings_daily = holdings_daily.reindex(all_dates).ffill().fillna(0.0)

        # Only keep symbols present in both
        common_syms = [s for s in holdings_daily.columns if s in ph.columns]
        if common_syms:
            holdings_val = (holdings_daily[common_syms] * ph[common_syms]).sum(axis=1)
        else:
            holdings_val = pd.Series(0.0, index=all_dates)

    # --- USD/ILS conversion ---
    fx = usdils_history.copy()
    if fx.empty:
        ils_usd = pd.Series(0.0, index=all_dates)
    else:
        fx.index = pd.to_datetime(fx.index)
        fx = fx.reindex(all_dates).ffill().bfill()
        # usdils rate = ILS per USD → ILS / rate = USD
        ils_usd = bal_daily["ils_balance"] / fx.replace(0, np.nan).ffill()
        ils_usd = ils_usd.fillna(0.0)

    nav = bal_daily["usd_balance"] + ils_usd + holdings_val

    result = pd.DataFrame({
        "date": all_dates,
        "nav": nav.values,
        "usd_cash": bal_daily["usd_balance"].values,
        "ils_cash_usd": ils_usd.values,
        "holdings_value": holdings_val.values,
    })
    return result.reset_index(drop=True)


def compute_twr(nav_timeline: pd.DataFrame, cash_flows: pd.DataFrame) -> float:
    """Time-weighted return.

    Sub-periods are defined by external cash flow events (deposits).
    At each cash flow date: sub_return = (NAV_before_cf - NAV_start_of_period) / NAV_start_of_period
    Then TWR = product(1 + sub_return) - 1.

    Parameters
    ----------
    nav_timeline:  DataFrame with columns 'date' and 'nav'
    cash_flows:    DataFrame with columns 'date' and 'amount' (positive = deposit into portfolio)
    """
    if nav_timeline.empty or len(nav_timeline) < 2:
        return 0.0

    nav = nav_timeline.copy()
    nav["date"] = pd.to_datetime(nav["date"])
    nav = nav.set_index("date")["nav"].sort_index()

    def nav_on(d: pd.Timestamp) -> float:
        candidates = nav[nav.index <= d]
        return float(candidates.iloc[-1]) if not candidates.empty else float(nav.iloc[0])

    cf = cash_flows.copy()
    cf["date"] = pd.to_datetime(cf["date"])
    cf = cf.sort_values("date")

    period_start_nav = float(nav.iloc[0])
    twr_factor = 1.0

    for _, row in cf.iterrows():
        nav_before = nav_on(row["date"])
        if period_start_nav > 0:
            twr_factor *= nav_before / period_start_nav
        # After deposit, next period starts with NAV including the deposit
        period_start_nav = nav_before + float(row["amount"])

    # Final period: current NAV
    final_nav = float(nav.iloc[-1])
    if period_start_nav > 0:
        twr_factor *= final_nav / period_start_nav

    return twr_factor - 1.0


def compute_xirr(dated_cash_flows: list[tuple], final_value: float, final_date) -> Optional[float]:
    """Compute XIRR (annualized internal rate of return).

    Parameters
    ----------
    dated_cash_flows: list of (date, amount) — deposits are NEGATIVE (money leaving wallet),
                      withdrawals are POSITIVE (money returning to wallet)
    final_value:      current portfolio value (positive)
    final_date:       date for the terminal cash flow

    Returns annualized IRR as a decimal (e.g. 0.12 = 12%) or None on failure.
    """
    if not dated_cash_flows or final_value <= 0:
        return None

    all_flows = sorted(dated_cash_flows, key=lambda x: pd.to_datetime(x[0]))
    all_flows.append((final_date, final_value))

    base_date = pd.to_datetime(all_flows[0][0])
    amounts = []
    years = []
    for d, amt in all_flows:
        dt = pd.to_datetime(d)
        years.append((dt - base_date).days / 365.25)
        amounts.append(float(amt))

    # Newton-Raphson to find rate r such that sum(amt / (1+r)^t) = 0
    def npv(r: float) -> float:
        return sum(a / (1 + r) ** t for a, t in zip(amounts, years))

    def dnpv(r: float) -> float:
        return sum(-t * a / (1 + r) ** (t + 1) for a, t in zip(amounts, years))

    try:
        r = 0.1
        for _ in range(100):
            f = npv(r)
            df = dnpv(r)
            if abs(df) < 1e-12:
                break
            r -= f / df
            if r <= -1:
                r = -0.9999
        if abs(npv(r)) < 1.0:
            return r
        return None
    except Exception:
        return None


def compute_real_nav(nav_timeline: pd.DataFrame, cpi_series: pd.Series) -> pd.Series:
    """Deflate nominal NAV by CPI ratio to get inflation-adjusted NAV.

    Base = CPI on first NAV date.  Real NAV = nominal NAV * (base_cpi / current_cpi).

    Returns a Series aligned to nav_timeline's date column.
    """
    if cpi_series.empty or nav_timeline.empty:
        return pd.Series(dtype=float)

    nav = nav_timeline.copy()
    nav["date"] = pd.to_datetime(nav["date"])

    cpi = cpi_series.copy()
    cpi.index = pd.to_datetime(cpi.index)
    cpi = cpi.reindex(nav["date"]).ffill().bfill()

    base_cpi = cpi.iloc[0]
    if base_cpi == 0 or pd.isna(base_cpi):
        return pd.Series(dtype=float)

    real_nav = nav["nav"].values * (base_cpi / cpi.values)
    return pd.Series(real_nav, index=nav["date"], name="real_nav")


__all__ = [
    "build_daily_holdings_state",
    "compute_nav_timeline",
    "compute_twr",
    "compute_xirr",
    "compute_real_nav",
]
