"""Trade Lens: broker import + normalization + analytics (IBI v1)."""

from trade_lens.brokers.ibi import IbiRawLoader, RawActionType, RawDataAttribute
from trade_lens.pipeline.normalize import to_ledger
from trade_lens.analytics import monthly_net_cashflow, monthly_fees_breakdown, symbol_summary
from trade_lens.models import Currency, Action, Transaction, Deposit, Conversion

__all__ = [
    # Brokers
    "IbiRawLoader",
    "RawActionType",
    "RawDataAttribute",
    # Pipeline
    "to_ledger",
    # Analytics
    "monthly_net_cashflow",
    "monthly_fees_breakdown",
    "symbol_summary",
    # Models (kept for future expansion)
    "Currency",
    "Action",
    "Transaction",
    "Deposit",
    "Conversion",
]