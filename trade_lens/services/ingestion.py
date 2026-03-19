from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import pandas as pd

from trade_lens.brokers.base import BrokerLoader
from trade_lens.models.schemas import IngestionResponse
from trade_lens.pipeline.loader import (
    count_unknown_action_rows,
    get_unknown_action_details,
    load_and_normalize_many,
)


@dataclass
class IngestionResult:
    """Result of loading and normalizing one or more broker export files."""

    raw: pd.DataFrame
    ledger: pd.DataFrame
    unknown_action_count: int
    unknown_action_details: pd.DataFrame
    file_count: int

    def to_response(self) -> IngestionResponse:
        """Return a JSON-serializable response object."""
        return IngestionResponse(
            file_count=self.file_count,
            raw_row_count=len(self.raw),
            ledger_row_count=len(self.ledger),
            unknown_action_count=self.unknown_action_count,
        )


def ingest_files(
    file_payloads: Sequence[tuple[str, bytes]],
    broker: Optional[BrokerLoader] = None,
) -> IngestionResult:
    """Load broker export files and return normalized ledger plus diagnostics.

    Args:
        file_payloads: Sequence of (filename, file_bytes) tuples.
        broker: BrokerLoader to use. Defaults to IBILoader.

    Returns:
        IngestionResult with raw DataFrame, canonical ledger, and diagnostics
        about any unrecognized action types.
    """
    raw, ledger = load_and_normalize_many(file_payloads, broker=broker)
    unknown_count = count_unknown_action_rows(ledger)
    unknown_details = get_unknown_action_details(raw, ledger) if unknown_count > 0 else pd.DataFrame()

    return IngestionResult(
        raw=raw,
        ledger=ledger,
        unknown_action_count=unknown_count,
        unknown_action_details=unknown_details,
        file_count=len(file_payloads),
    )


__all__ = ["IngestionResult", "ingest_files"]
