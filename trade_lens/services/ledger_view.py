from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

import pandas as pd

from trade_lens.analytics.ledger import (
    filter_ledger,
    ledger_action_options,
    ledger_date_bounds,
    ledger_symbol_options,
)
from trade_lens.models.schemas import LedgerResponse, LedgerRow


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

    def to_response(self) -> LedgerResponse:
        """Return a JSON-serializable response object."""
        date_from, date_to = self.date_bounds
        rows = [
            LedgerRow(
                date=str(row.get("date").date()) if hasattr(row.get("date"), "date") else str(row.get("date", "")),
                action_type=str(row.get("action_type", "") or ""),
                symbol=str(row.get("symbol", "") or ""),
                paper_name=str(row.get("paper_name", "") or ""),
                quantity=float(row.get("quantity") or 0.0),
                delta_usd=float(row.get("delta_usd") or 0.0),
                delta_ils=float(row.get("delta_ils") or 0.0),
                fees_usd=float(row.get("fees_usd") or 0.0),
            )
            for row in self.filtered.to_dict(orient="records")
        ]
        return LedgerResponse(
            date_from=str(date_from) if date_from else None,
            date_to=str(date_to) if date_to else None,
            action_options=self.action_options,
            symbol_options=self.symbol_options,
            rows=rows,
            total_rows=len(rows),
        )


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
