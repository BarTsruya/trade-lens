from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trade_lens.analytics.dividends import build_monthly_amount_series, dividend_deposit_year_options
from trade_lens.analytics.fees import build_maintenance_fees_ledger, build_trading_fees_ledger
from trade_lens.analytics.taxes import filter_tax_rows_by_year
from trade_lens.models.schemas import (
    FeesResponse,
    MaintenanceFeeRow,
    MonthlyAmount,
    TickerAmount,
    TradingFeeRow,
)


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

    def to_response(self) -> FeesResponse:
        """Return a JSON-serializable response object."""
        if self.selected_year is None:
            return FeesResponse(
                year_options=self.year_options,
                selected_year=0,
                trading_total_usd=0.0,
                maintenance_total_ils=0.0,
                trading_monthly=[],
                maintenance_monthly=[],
                trading_by_ticker=[],
                trading_transactions=[],
                maintenance_transactions=[],
            )

        def _monthly(df: pd.DataFrame, amount_col: str) -> list[MonthlyAmount]:
            return [
                MonthlyAmount(
                    month=str(r["month"])[:7],
                    month_label=pd.Timestamp(r["month"]).strftime("%b"),
                    amount=float(r.get(amount_col) or 0.0),
                )
                for r in df.to_dict(orient="records")
            ] if not df.empty else []

        trading_monthly = _monthly(self.trading_monthly, "fee_amount")
        maintenance_monthly = _monthly(self.maintenance_monthly, "fee_amount")

        trading_by_ticker = [
            TickerAmount(ticker=str(r.get("symbol", "")), amount=float(r.get("amount_value") or 0.0), currency="$")
            for r in self.trading_by_ticker.to_dict(orient="records")
        ] if not self.trading_by_ticker.empty else []

        trading_txns = [
            TradingFeeRow(
                date=str(pd.Timestamp(r["date"]).date()) if r.get("date") is not None else "",
                action_type=str(r.get("action_type", "") or ""),
                symbol=str(r.get("symbol", "") or ""),
                amount_usd=float(r.get("amount_value") or 0.0),
            )
            for r in self.trading_by_year.to_dict(orient="records")
        ] if not self.trading_by_year.empty else []

        maintenance_txns = [
            MaintenanceFeeRow(
                date=str(pd.Timestamp(r["date"]).date()) if r.get("date") is not None else "",
                amount_ils=float(r.get("amount_value") or 0.0),
            )
            for r in self.maintenance_by_year.to_dict(orient="records")
        ] if not self.maintenance_by_year.empty else []

        return FeesResponse(
            year_options=[int(y) for y in self.year_options],
            selected_year=int(self.selected_year),
            trading_total_usd=self.trading_total,
            maintenance_total_ils=self.maintenance_total,
            trading_monthly=trading_monthly,
            maintenance_monthly=maintenance_monthly,
            trading_by_ticker=trading_by_ticker,
            trading_transactions=trading_txns,
            maintenance_transactions=maintenance_txns,
        )


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
