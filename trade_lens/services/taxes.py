from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trade_lens.analytics.dividends import build_dividend_tax_ledger, build_monthly_amount_series
from trade_lens.analytics.taxes import (
    build_capital_gains_monthly_chart_df,
    build_capital_gains_summary,
    build_tax_ledger,
    filter_tax_rows_by_year,
    tax_year_options,
)
from trade_lens.models.schemas import (
    CapitalGainsMonthlyRow,
    CapitalGainsRow,
    CapitalGainsSummary,
    DividendTaxRow,
    MonthlyAmount,
    TaxResponse,
    TickerAmount,
)


def _ticker_from_paper_name(series: pd.Series) -> pd.Series:
    """Extract a short ticker symbol from IBI paper_name strings.

    IBI formats paper_name as e.g. "SOME FUND NAME / AAPL USD" — the ticker
    is the first word after the last '/'.
    """
    return series.str.split("/").str[-1].str.strip().str.split().str[0]


@dataclass
class TaxSummary:
    """Result of the taxes service for a specific year."""

    year_options: list[int]
    selected_year: Optional[int]

    # Capital gains tax — full ledger and year-filtered (with state machine columns)
    capital_gains_ledger: pd.DataFrame
    capital_gains_by_year: pd.DataFrame

    # 12-month stacked bar chart data for the selected year
    monthly_chart: pd.DataFrame

    # Scalar summary for the selected year (keys: payable_sum, credit_sum,
    # payment_sum, annual_tax, remaining_shield)
    summary: dict[str, float]

    # Dividend tax — full ledger and year-filtered
    dividend_tax_ledger: pd.DataFrame
    dividend_tax_by_year: pd.DataFrame

    # 12-month series (month, dividend_tax_amount) for the selected year
    dividend_tax_monthly: pd.DataFrame

    # Per-ticker breakdown (columns: ticker, amount_currency, amount_value)
    dividend_tax_by_ticker: pd.DataFrame

    # Total dividend tax per currency (dict: currency_symbol -> total_value)
    dividend_tax_totals: dict[str, float]

    def to_response(self) -> TaxResponse:
        """Return a JSON-serializable response object."""
        _empty_summary = CapitalGainsSummary(
            payable_sum=0.0, credit_sum=0.0, payment_sum=0.0, annual_tax=0.0, remaining_shield=0.0
        )
        if self.selected_year is None:
            return TaxResponse(
                year_options=self.year_options,
                selected_year=0,
                capital_gains=[],
                capital_gains_summary=_empty_summary,
                capital_gains_monthly=[],
                dividend_tax=[],
                dividend_tax_monthly=[],
                dividend_tax_by_ticker=[],
                dividend_tax_totals={},
            )

        def _iso(val: object) -> str:
            return str(val.date()) if hasattr(val, "date") else str(val)

        cap_rows = [
            CapitalGainsRow(
                date=_iso(r.get("date")),
                action_type=str(r.get("action_type", "") or ""),
                paper_name=str(r.get("paper_name", "") or ""),
                amount_value=float(r.get("amount_value") or 0.0),
                tax_shield_state=float(r.get("tax_shield_state") or 0.0),
                tax_payable_state=float(r.get("tax_payable_state") or 0.0),
                total_annual_tax=float(r.get("total_annual_tax") or 0.0),
            )
            for r in self.capital_gains_by_year.to_dict(orient="records")
        ] if not self.capital_gains_by_year.empty else []

        raw_summary = self.summary
        cap_summary = CapitalGainsSummary(
            payable_sum=float(raw_summary.get("payable_sum", 0.0)),
            credit_sum=float(raw_summary.get("credit_sum", 0.0)),
            payment_sum=float(raw_summary.get("payment_sum", 0.0)),
            annual_tax=float(raw_summary.get("annual_tax", 0.0)),
            remaining_shield=float(raw_summary.get("remaining_shield", 0.0)),
        )

        cap_monthly = [
            CapitalGainsMonthlyRow(
                month=str(r["month"])[:7],
                month_label=pd.Timestamp(r["month"]).strftime("%b"),
                payable_amount=float(r.get("payable_amount") or 0.0),
                payment_amount=float(r.get("payment_amount") or 0.0),
                credit_amount=float(r.get("credit_amount") or 0.0),
                shield_used=float(r.get("shield_used_bar") or 0.0),
                shield_balance=float(r.get("shield_balance_bar") or 0.0),
                rolling_shield=float(r.get("rolling_shield") or 0.0),
            )
            for r in self.monthly_chart.to_dict(orient="records")
        ] if not self.monthly_chart.empty else []

        div_tax_rows = [
            DividendTaxRow(
                date=_iso(r.get("date")),
                paper_name=str(r.get("paper_name", "") or ""),
                ticker=str(r.get("ticker", "") or ""),
                amount_value=float(r.get("amount_value") or 0.0),
                amount_currency=str(r.get("amount_currency", "") or ""),
            )
            for r in self.dividend_tax_by_year.to_dict(orient="records")
        ] if not self.dividend_tax_by_year.empty else []

        div_tax_monthly = [
            MonthlyAmount(
                month=str(r["month"])[:7],
                month_label=pd.Timestamp(r["month"]).strftime("%b"),
                amount=float(r.get("dividend_tax_amount") or 0.0),
            )
            for r in self.dividend_tax_monthly.to_dict(orient="records")
        ] if not self.dividend_tax_monthly.empty else []

        div_tax_by_ticker = [
            TickerAmount(
                ticker=str(r.get("ticker", "") or ""),
                amount=float(r.get("amount_value") or 0.0),
                currency=str(r.get("amount_currency", "") or ""),
            )
            for r in self.dividend_tax_by_ticker.to_dict(orient="records")
        ] if not self.dividend_tax_by_ticker.empty else []

        return TaxResponse(
            year_options=[int(y) for y in self.year_options],
            selected_year=int(self.selected_year),
            capital_gains=cap_rows,
            capital_gains_summary=cap_summary,
            capital_gains_monthly=cap_monthly,
            dividend_tax=div_tax_rows,
            dividend_tax_monthly=div_tax_monthly,
            dividend_tax_by_ticker=div_tax_by_ticker,
            dividend_tax_totals={str(k): float(v) for k, v in self.dividend_tax_totals.items()},
        )


def get_tax_summary(
    ledger: pd.DataFrame,
    selected_year: Optional[int] = None,
) -> TaxSummary:
    """Compute capital gains and dividend tax analytics for a given year.

    Business logic extracted from the Streamlit taxes tab:
    - Builds the capital gains state-machine ledger and monthly chart.
    - Builds the dividend tax ledger and extracts tickers from paper_name.
    - Derives available years from the union of both data sources.
    - Falls back to the most recent year when selected_year is None or absent.

    Args:
        ledger: Full canonical ledger DataFrame.
        selected_year: Year to compute details for. Defaults to most recent.

    Returns:
        TaxSummary with year-filtered data, chart data, and aggregates.
    """
    capital_gains_all = build_tax_ledger(ledger)
    dividend_tax_all = build_dividend_tax_ledger(ledger)
    year_options = tax_year_options(ledger, capital_gains_all)

    _empty = pd.DataFrame()
    _empty_summary: dict[str, float] = {
        "payable_sum": 0.0,
        "credit_sum": 0.0,
        "payment_sum": 0.0,
        "annual_tax": 0.0,
        "remaining_shield": 0.0,
    }

    if not year_options:
        return TaxSummary(
            year_options=[],
            selected_year=None,
            capital_gains_ledger=capital_gains_all,
            capital_gains_by_year=_empty,
            monthly_chart=_empty,
            summary=_empty_summary,
            dividend_tax_ledger=dividend_tax_all,
            dividend_tax_by_year=_empty,
            dividend_tax_monthly=_empty,
            dividend_tax_by_ticker=_empty,
            dividend_tax_totals={},
        )

    if selected_year is None or selected_year not in year_options:
        selected_year = year_options[0]

    # --- Capital gains ---
    cap_gains_y = filter_tax_rows_by_year(capital_gains_all, selected_year)
    sort_cols = ["date", "_display_idx"] if "_display_idx" in cap_gains_y.columns else ["date"]
    cap_gains_y = cap_gains_y.sort_values(sort_cols, ascending=True, kind="mergesort").reset_index(drop=True)

    monthly_chart = (
        build_capital_gains_monthly_chart_df(cap_gains_y, selected_year)
        if not cap_gains_y.empty
        else _empty
    )
    summary = build_capital_gains_summary(cap_gains_y) if not cap_gains_y.empty else _empty_summary

    # --- Dividend tax ---
    div_tax_y = filter_tax_rows_by_year(dividend_tax_all, selected_year)

    if not div_tax_y.empty:
        div_tax_monthly = build_monthly_amount_series(
            div_tax_y,
            selected_year=selected_year,
            amount_column="amount_value",
            output_column="dividend_tax_amount",
        )

        enriched = div_tax_y.copy()
        if "paper_name" in enriched.columns:
            enriched["ticker"] = _ticker_from_paper_name(enriched["paper_name"].astype(str))
        else:
            enriched["ticker"] = ""

        if "amount_currency" in enriched.columns and "amount_value" in enriched.columns:
            div_tax_by_ticker = (
                enriched.groupby(["ticker", "amount_currency"])["amount_value"]
                .sum()
                .reset_index()
                .sort_values("amount_value", ascending=False)
            )
            div_tax_totals_series = enriched.groupby("amount_currency")["amount_value"].sum()
            div_tax_totals = div_tax_totals_series.to_dict()
        else:
            div_tax_by_ticker = _empty
            div_tax_totals = {}
    else:
        div_tax_monthly = _empty
        div_tax_by_ticker = _empty
        div_tax_totals = {}

    return TaxSummary(
        year_options=year_options,
        selected_year=selected_year,
        capital_gains_ledger=capital_gains_all,
        capital_gains_by_year=cap_gains_y,
        monthly_chart=monthly_chart,
        summary=summary,
        dividend_tax_ledger=dividend_tax_all,
        dividend_tax_by_year=div_tax_y,
        dividend_tax_monthly=div_tax_monthly,
        dividend_tax_by_ticker=div_tax_by_ticker,
        dividend_tax_totals=div_tax_totals,
    )


__all__ = ["TaxSummary", "get_tax_summary"]
