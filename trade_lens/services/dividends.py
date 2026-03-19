from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trade_lens.analytics.dividends import (
    build_dividend_deposit_ledger,
    build_monthly_amount_series,
    dividend_deposit_year_options,
)
from trade_lens.analytics.taxes import filter_tax_rows_by_year


def _ticker_from_paper_name(series: pd.Series) -> pd.Series:
    """Extract a short ticker symbol from IBI paper_name strings.

    IBI formats paper_name as e.g. "SOME FUND NAME / AAPL USD" — the ticker
    is the first word after the last '/'.
    """
    return series.str.split("/").str[-1].str.strip().str.split().str[0]


@dataclass
class DividendSummary:
    """Result of the dividends service for a specific year."""

    year_options: list[int]
    selected_year: Optional[int]

    # Year-filtered dividend deposit rows
    deposit_by_year: pd.DataFrame

    # 12-month series (month, dividend_amount) for the selected year
    monthly: pd.DataFrame

    # Per-ticker breakdown (columns: ticker, amount_currency, amount_value)
    by_ticker: pd.DataFrame

    # Total dividends per currency (dict: currency_symbol -> total_value)
    totals: dict[str, float]


def get_dividend_summary(
    ledger: pd.DataFrame,
    selected_year: Optional[int] = None,
) -> DividendSummary:
    """Compute dividend deposit analytics for a given year.

    Business logic extracted from the Streamlit dividends tab:
    - Builds the dividend deposit ledger for all years.
    - Extracts tickers from IBI-formatted paper_name strings.
    - Computes per-ticker and per-currency aggregates.
    - Falls back to the most recent year when selected_year is None or absent.

    Args:
        ledger: Full canonical ledger DataFrame.
        selected_year: Year to compute details for. Defaults to most recent.

    Returns:
        DividendSummary with year-filtered data, monthly series, and aggregates.
    """
    deposit_all = build_dividend_deposit_ledger(ledger)
    year_options = dividend_deposit_year_options(deposit_all)

    _empty = pd.DataFrame()

    if not year_options:
        return DividendSummary(
            year_options=[],
            selected_year=None,
            deposit_by_year=_empty,
            monthly=_empty,
            by_ticker=_empty,
            totals={},
        )

    if selected_year is None or selected_year not in year_options:
        selected_year = year_options[0]

    deposit_y = filter_tax_rows_by_year(deposit_all, selected_year)

    monthly = (
        build_monthly_amount_series(
            deposit_y,
            selected_year=selected_year,
            amount_column="amount_value",
            output_column="dividend_amount",
        )
        if not deposit_y.empty
        else _empty
    )

    if not deposit_y.empty and "paper_name" in deposit_y.columns:
        enriched = deposit_y.copy()
        enriched["ticker"] = _ticker_from_paper_name(enriched["paper_name"].astype(str))

        if "amount_currency" in enriched.columns and "amount_value" in enriched.columns:
            by_ticker = (
                enriched.groupby(["ticker", "amount_currency"])["amount_value"]
                .sum()
                .reset_index()
                .sort_values("amount_value", ascending=False)
            )
            totals = enriched.groupby("amount_currency")["amount_value"].sum().to_dict()
        else:
            by_ticker = _empty
            totals = {}
    else:
        by_ticker = _empty
        totals = {}

    return DividendSummary(
        year_options=year_options,
        selected_year=selected_year,
        deposit_by_year=deposit_y,
        monthly=monthly,
        by_ticker=by_ticker,
        totals=totals,
    )


__all__ = ["DividendSummary", "get_dividend_summary"]
