from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trade_lens.analytics.dividends import build_monthly_amount_series, dividend_deposit_year_options
from trade_lens.analytics.fees import build_maintenance_fees_ledger, build_trading_fees_ledger
from trade_lens.analytics.taxes import filter_tax_rows_by_year


@dataclass
class FeesSummary:
    """Result of the fees service for a specific year."""

    year_options: list[int]
    selected_year: Optional[int]

    # Year-filtered transaction ledgers
    trading_by_year: pd.DataFrame
    maintenance_by_year: pd.DataFrame

    # 12-month series (month, fee_amount) for the selected year
    trading_monthly: pd.DataFrame
    maintenance_monthly: pd.DataFrame

    # Aggregates for the selected year
    trading_total: float          # USD
    maintenance_total: float      # ILS

    # Per-ticker breakdown for trading fees (columns: symbol, amount_value)
    trading_by_ticker: pd.DataFrame


def _empty_monthly(year: int, output_column: str) -> pd.DataFrame:
    months = pd.date_range(start=f"{year}-01-01", periods=12, freq="MS")
    return pd.DataFrame({"month": months, output_column: 0.0})


def get_fees_summary(
    ledger: pd.DataFrame,
    selected_year: Optional[int] = None,
) -> FeesSummary:
    """Compute trading and account maintenance fees for a given year.

    Business logic extracted from the Streamlit fees tab:
    - Derives available years from union of trading and maintenance fee dates.
    - Falls back to the most recent year when selected_year is None or absent.
    - Computes 12-month series and per-ticker breakdown for trading fees.

    Args:
        ledger: Full canonical ledger DataFrame.
        selected_year: Year to compute details for. Defaults to most recent.

    Returns:
        FeesSummary with year-filtered data and aggregates.
    """
    trading_all = build_trading_fees_ledger(ledger)
    maintenance_all = build_maintenance_fees_ledger(ledger)

    year_options = sorted(
        set(dividend_deposit_year_options(trading_all))
        | set(dividend_deposit_year_options(maintenance_all)),
        reverse=True,
    )

    _empty = pd.DataFrame()
    if not year_options:
        return FeesSummary(
            year_options=[],
            selected_year=None,
            trading_by_year=_empty,
            maintenance_by_year=_empty,
            trading_monthly=_empty,
            maintenance_monthly=_empty,
            trading_total=0.0,
            maintenance_total=0.0,
            trading_by_ticker=_empty,
        )

    if selected_year is None or selected_year not in year_options:
        selected_year = year_options[0]

    trading_y = filter_tax_rows_by_year(trading_all, selected_year)
    maintenance_y = filter_tax_rows_by_year(maintenance_all, selected_year)

    trading_monthly = (
        build_monthly_amount_series(
            trading_y, selected_year=selected_year, amount_column="amount_value", output_column="fee_amount"
        )
        if not trading_y.empty
        else _empty_monthly(selected_year, "fee_amount")
    )
    maintenance_monthly = (
        build_monthly_amount_series(
            maintenance_y, selected_year=selected_year, amount_column="amount_value", output_column="fee_amount"
        )
        if not maintenance_y.empty
        else _empty_monthly(selected_year, "fee_amount")
    )

    trading_total = float(trading_y["amount_value"].sum()) if not trading_y.empty else 0.0
    maintenance_total = float(maintenance_y["amount_value"].sum()) if not maintenance_y.empty else 0.0

    if not trading_y.empty and "symbol" in trading_y.columns:
        trading_by_ticker = (
            trading_y.groupby("symbol")["amount_value"]
            .sum()
            .reset_index()
            .sort_values("amount_value", ascending=False)
        )
    else:
        trading_by_ticker = pd.DataFrame(columns=["symbol", "amount_value"])

    return FeesSummary(
        year_options=year_options,
        selected_year=selected_year,
        trading_by_year=trading_y,
        maintenance_by_year=maintenance_y,
        trading_monthly=trading_monthly,
        maintenance_monthly=maintenance_monthly,
        trading_total=trading_total,
        maintenance_total=maintenance_total,
        trading_by_ticker=trading_by_ticker,
    )


__all__ = ["FeesSummary", "get_fees_summary"]
