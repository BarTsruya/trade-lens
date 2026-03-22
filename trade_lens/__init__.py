"""Trade Lens: broker import + normalization + analytics."""

__version__ = "0.2.5"

from trade_lens.brokers.base import BrokerLoader
from trade_lens.brokers.ibi import IBILoader, load_single, RawActionType, RawDataAttribute
from trade_lens.brokers.registry import BROKERS, get_broker
from trade_lens.pipeline.loader import load_and_normalize_many, sort_ledger, count_unknown_action_rows
from trade_lens.pipeline.normalize import to_ledger
from trade_lens.analytics import (
    monthly_fees_breakdown,
    filter_ledger,
    ledger_date_bounds,
    ledger_action_options,
    ledger_symbol_options,
    TAX_ACTION_TYPES,
    build_tax_ledger,
)
from trade_lens.models import Currency

__all__ = [
    # Brokers
    "BrokerLoader",
    "IBILoader",
    "BROKERS",
    "get_broker",
    "load_single",
    "RawActionType",
    "RawDataAttribute",
    # Pipeline
    "load_and_normalize_many",
    "sort_ledger",
    "count_unknown_action_rows",
    "to_ledger",
    # Analytics
    "monthly_fees_breakdown",
    "filter_ledger",
    "ledger_date_bounds",
    "ledger_action_options",
    "ledger_symbol_options",
    "TAX_ACTION_TYPES",
    "build_tax_ledger",
    # Models
    "Currency",
]