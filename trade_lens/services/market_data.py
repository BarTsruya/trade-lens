from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import requests
import yfinance as yf


def fetch_live_prices(symbols: list[str]) -> dict[str, dict]:
    """Return {symbol: {price, prev_close, day_change, day_change_pct}} for each symbol.

    price       — fast_info.last_price (real-time during market hours; last official
                  close outside hours). Used for Mkt Value / Unrealized P&L.
    day_change  — hist[-1].Close - hist[-2].Close (last session vs. the one before).
                  Computed purely from history so it is never zero due to timezone
                  differences between the caller's locale and the US market.
    Values are None for any symbol that yfinance cannot resolve.
    """
    _empty = {"price": None, "prev_close": None, "day_change": None, "day_change_pct": None}
    result: dict[str, dict] = {}

    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)

            # Real-time / most-recent price for display
            price = ticker.fast_info.last_price
            if price is None:
                result[sym] = dict(_empty)
                continue
            price = float(price)

            # Fetch last 5 trading days (unadjusted) to guarantee >= 2 rows
            hist = ticker.history(period="5d", auto_adjust=False)
            if hist.empty or len(hist) < 2:
                result[sym] = dict(_empty)
                continue

            # last_close  = most recent completed session
            # prev_close  = the session before that
            # Using positional indexing avoids any timezone / "today" comparison.
            last_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])
            day_change = last_close - prev_close
            day_change_pct = day_change / prev_close * 100 if prev_close != 0 else None

            result[sym] = {
                "price": price,
                "prev_close": prev_close,
                "day_change": day_change,
                "day_change_pct": day_change_pct,
            }
        except Exception:
            result[sym] = dict(_empty)

    return result


def fetch_historical_prices(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    """Return daily adjusted close prices.

    Wide DataFrame: index=date (DatetimeIndex), columns=symbol names.
    Missing data forward-filled then back-filled.
    """
    if not symbols:
        return pd.DataFrame()
    try:
        raw = yf.download(
            symbols,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            multi_level_col=True,
        )
        if raw.empty:
            return pd.DataFrame(index=pd.DatetimeIndex([]), columns=symbols)

        # When a single ticker is downloaded yfinance returns flat columns
        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            closes = raw[["Close"]]
            closes.columns = symbols

        closes = closes.ffill().bfill()
        return closes
    except Exception:
        return pd.DataFrame(index=pd.DatetimeIndex([]), columns=symbols)


def fetch_usdils_history(start: str, end: str) -> pd.Series:
    """Daily USD/ILS exchange rate (USD per 1 ILS = 1/rate).

    Returns a Series indexed by date. If unavailable, returns empty Series.
    Note: "USDILS=X" gives ILS per 1 USD, so to convert ILS→USD divide by rate.
    """
    try:
        raw = yf.download("USDILS=X", start=start, end=end, auto_adjust=True, progress=False)
        if raw.empty:
            return pd.Series(dtype=float)
        if isinstance(raw.columns, pd.MultiIndex):
            series = raw["Close"].iloc[:, 0]
        else:
            series = raw["Close"]
        series = series.ffill().bfill()
        series.name = "usdils"
        return series
    except Exception:
        return pd.Series(dtype=float, name="usdils")


def fetch_us_cpi(start: str) -> pd.Series:
    """Monthly US CPI (CPIAUCSL) from FRED public CSV, resampled to daily.

    No API key required. Returns empty Series on failure.
    """
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), parse_dates=["DATE"], index_col="DATE")
        df.columns = ["cpi"]
        df = df[df.index >= pd.to_datetime(start)]
        # Resample to daily, forward-fill within each month
        daily = df["cpi"].resample("D").interpolate(method="pad")
        daily.name = "cpi"
        return daily
    except Exception:
        return pd.Series(dtype=float, name="cpi")


__all__ = [
    "fetch_live_prices",
    "fetch_historical_prices",
    "fetch_usdils_history",
    "fetch_us_cpi",
]
