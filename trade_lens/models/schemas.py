"""Typed response models — the stable data contract between backend and frontend.

All types are Pydantic ``BaseModel`` subclasses, which gives:
- Runtime validation on construction
- ``model_dump()`` / ``model_dump(mode='json')`` for serialization
- ``model_json_schema()`` for OpenAPI schema generation (used by FastAPI)
- Field aliases and validators when needed

Design rules
------------
- Dates are ISO 8601 strings (``"YYYY-MM-DD"``) so the contract is
  unambiguous to any client language.
- Nullable fields are typed ``Optional[X]`` with a ``None`` default.
- No pandas types appear here — the contract is DataFrame-free.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------


class MonthlyAmount(BaseModel):
    """One bar in a 12-month chart."""

    month: str          # "YYYY-MM" (first day of month, for ordering)
    month_label: str    # "Jan", "Feb", …  (display label)
    amount: float


class TickerAmount(BaseModel):
    """Fee or dividend total for one ticker symbol."""

    ticker: str
    amount: float
    currency: str   # "$" | "₪"


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


class IngestionResponse(BaseModel):
    file_count: int
    raw_row_count: int
    ledger_row_count: int
    unknown_action_count: int


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


class LedgerRow(BaseModel):
    date: str
    action_type: str
    symbol: str
    paper_name: str
    quantity: float
    delta_usd: float
    delta_ils: float
    fees_usd: float


class LedgerResponse(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    action_options: list[str]
    symbol_options: list[str]
    rows: list[LedgerRow]
    total_rows: int


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------


class BalanceRow(BaseModel):
    date: str
    action_description: str
    usd_delta: float
    ils_delta: float
    fees_usd: float
    usd_balance: float
    ils_balance: float


class FxRow(BaseModel):
    date: str
    delta_ils: float
    delta_usd: float
    rate_label: str
    rate_value: Optional[float] = None


class FxSummaryData(BaseModel):
    avg_rate: float
    total_ils_converted: float
    total_usd_produced: float


class BalanceResponse(BaseModel):
    timeline: list[BalanceRow]
    fx_transactions: list[FxRow]
    fx_summary: Optional[FxSummaryData] = None


# ---------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------


class TradingFeeRow(BaseModel):
    date: str
    action_type: str
    symbol: str
    amount_usd: float


class MaintenanceFeeRow(BaseModel):
    date: str
    amount_ils: float


class FeesResponse(BaseModel):
    year_options: list[int]
    selected_year: int
    trading_total_usd: float
    maintenance_total_ils: float
    trading_monthly: list[MonthlyAmount]
    maintenance_monthly: list[MonthlyAmount]
    trading_by_ticker: list[TickerAmount]
    trading_transactions: list[TradingFeeRow]
    maintenance_transactions: list[MaintenanceFeeRow]


# ---------------------------------------------------------------------------
# Taxes
# ---------------------------------------------------------------------------


class CapitalGainsRow(BaseModel):
    date: str
    action_type: str
    paper_name: str
    amount_value: float
    tax_shield_state: float
    tax_payable_state: float
    total_annual_tax: float


class CapitalGainsSummary(BaseModel):
    payable_sum: float
    credit_sum: float
    payment_sum: float
    annual_tax: float
    remaining_shield: float


class CapitalGainsMonthlyRow(BaseModel):
    """One month in the capital gains stacked bar chart."""

    month: str          # "YYYY-MM"
    month_label: str    # "Jan" …
    payable_amount: float
    payment_amount: float
    credit_amount: float
    shield_used: float
    shield_balance: float
    rolling_shield: float


class DividendTaxRow(BaseModel):
    date: str
    paper_name: str
    ticker: str
    amount_value: float
    amount_currency: str


class TaxResponse(BaseModel):
    year_options: list[int]
    selected_year: int
    capital_gains: list[CapitalGainsRow]
    capital_gains_summary: CapitalGainsSummary
    capital_gains_monthly: list[CapitalGainsMonthlyRow]
    dividend_tax: list[DividendTaxRow]
    dividend_tax_monthly: list[MonthlyAmount]
    dividend_tax_by_ticker: list[TickerAmount]
    dividend_tax_totals: dict[str, float]


# ---------------------------------------------------------------------------
# Dividends
# ---------------------------------------------------------------------------


class DividendDepositRow(BaseModel):
    date: str
    paper_name: str
    ticker: str
    amount_value: float
    amount_currency: str


class DividendResponse(BaseModel):
    year_options: list[int]
    selected_year: int
    totals: dict[str, float]
    monthly: list[MonthlyAmount]
    by_ticker: list[TickerAmount]
    transactions: list[DividendDepositRow]
