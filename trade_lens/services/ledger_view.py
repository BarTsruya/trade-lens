from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

import pandas as pd

from trade_lens.analytics.ledger import (
    filter_ledger,
    ledger_action_options,
    ledger_date_bounds,
    ledger_symbol_options,
)


@dataclass
class LedgerFilters:
    """User-supplied filter criteria for the ledger view."""

    date_range: Optional[tuple[date, date]] = None
    action_types: Optional[Sequence[str]] = None
    symbols: Optional[Sequence[str]] = None


@dataclass
class LedgerViewResult:
    """Result of applying filters to the ledger and extracting UI metadata."""

    filtered: pd.DataFrame
    date_bounds: tuple[Optional[date], Optional[date]]
    action_options: list[str]
    symbol_options: list[str]


def get_ledger_view(
    ledger: pd.DataFrame,
    filters: Optional[LedgerFilters] = None,
) -> LedgerViewResult:
    """Apply filters to the ledger and return the view result.

    Metadata (date_bounds, action_options, symbol_options) is always derived
    from the *full* unfiltered ledger so filter controls reflect all available
    options regardless of current selection.

    Args:
        ledger: Full canonical ledger DataFrame.
        filters: Optional filter criteria. Pass None for an unfiltered view.

    Returns:
        LedgerViewResult with filtered DataFrame and full-ledger metadata.
    """
    date_bounds = ledger_date_bounds(ledger)
    action_options = ledger_action_options(ledger)
    symbol_options = ledger_symbol_options(ledger)

    if filters is None:
        filtered = ledger.copy()
    else:
        filtered = filter_ledger(
            ledger,
            date_range=filters.date_range,
            action_types=filters.action_types,
            symbols=filters.symbols,
        )

    return LedgerViewResult(
        filtered=filtered,
        date_bounds=date_bounds,
        action_options=action_options,
        symbol_options=symbol_options,
    )


__all__ = ["LedgerFilters", "LedgerViewResult", "get_ledger_view"]
