"""Service layer — one function per product feature, returning typed result objects.

Each service function composes one or more analytics calls, performs any
broker-specific data transformations (e.g. ticker extraction from paper_name),
and returns a typed dataclass.  The frontend (Streamlit, FastAPI, CLI, …)
calls a service function and only handles rendering/formatting of the result.

Available services
------------------
ingest_files        → IngestionResult
get_ledger_view     → LedgerViewResult
get_balance_summary → BalanceResult
get_fees_summary    → FeesSummary
get_tax_summary     → TaxSummary
get_dividend_summary→ DividendSummary
"""

from trade_lens.services.balance import BalanceResult, FxSummary, get_balance_summary
from trade_lens.services.dividends import DividendSummary, get_dividend_summary
from trade_lens.services.fees import FeesSummary, get_fees_summary
from trade_lens.services.ingestion import IngestionResult, ingest_files
from trade_lens.services.ledger_view import LedgerFilters, LedgerViewResult, get_ledger_view
from trade_lens.services.taxes import TaxSummary, get_tax_summary

__all__ = [
    # Ingestion
    "IngestionResult",
    "ingest_files",
    # Ledger
    "LedgerFilters",
    "LedgerViewResult",
    "get_ledger_view",
    # Balance
    "FxSummary",
    "BalanceResult",
    "get_balance_summary",
    # Fees
    "FeesSummary",
    "get_fees_summary",
    # Taxes
    "TaxSummary",
    "get_tax_summary",
    # Dividends
    "DividendSummary",
    "get_dividend_summary",
]
