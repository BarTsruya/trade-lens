from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trade_lens.analytics.balance import balance_timeline_actions
from trade_lens.brokers.ibi import RawActionType


def _extract_fx_rate_label(paper_name: str) -> str:
    """Extract 'CCY1/CCY2 <rate>' from an IBI paper_name string, or '' if absent."""
    m = re.search(r"[A-Z]+/[A-Z]+\s+[\d.]+", str(paper_name) if paper_name else "")
    return m.group() if m else ""


def _extract_fx_rate_value(rate_label: str) -> Optional[float]:
    """Parse the numeric rate from a label such as 'USD/ILS 3.6812'."""
    m = re.search(r"([\d.]+)$", rate_label)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


@dataclass
class FxSummary:
    """Aggregate statistics for all FX conversion rows."""

    avg_rate: float
    total_ils_converted: float
    total_usd_produced: float


@dataclass
class BalanceResult:
    """Result of the balance / cashflow service."""

    # Running balance timeline (cash-affecting ledger rows with cumulative totals).
    # Columns: date, action_type, action_description, fees_usd, usd_delta,
    #          ils_delta, usd_balance, ils_balance, expected_ils_balance,
    #          _display_idx (aligned from ledger).
    timeline: pd.DataFrame

    # FX conversion rows with computed columns:
    # date, delta_ils (raw float), delta_usd (raw float),
    # rate_label (str), rate_value (float | NaN).
    fx_transactions: pd.DataFrame

    # Aggregate FX statistics. None when there are no FX rows.
    fx_summary: Optional[FxSummary]


def get_balance_summary(ledger: pd.DataFrame) -> BalanceResult:
    """Compute the balance timeline and FX conversion analytics.

    Business logic extracted from the Streamlit balance tab:
    - Builds a running balance timeline via balance_timeline_actions.
    - Aligns _display_idx from the ledger for stable display ordering.
    - Extracts FX conversion rows, parses the rate from paper_name, and
      computes aggregate FX statistics.

    Args:
        ledger: Full canonical ledger DataFrame.

    Returns:
        BalanceResult with timeline, FX transactions, and FX summary.
    """
    # --- Balance timeline ---
    timeline = balance_timeline_actions(ledger)
    if not timeline.empty and "_display_idx" in ledger.columns:
        timeline = timeline.copy()
        timeline["_display_idx"] = (
            pd.to_numeric(ledger.get("_display_idx"), errors="coerce")
            .reindex(timeline.index)
        )

    # --- FX conversions ---
    fx_mask = ledger["action_type"] == RawActionType.FX_CONVERSION.value
    fx_raw = ledger.loc[fx_mask].copy()

    if fx_raw.empty:
        return BalanceResult(
            timeline=timeline,
            fx_transactions=pd.DataFrame(),
            fx_summary=None,
        )

    fx_raw["date"] = pd.to_datetime(fx_raw["date"], errors="coerce").dt.date
    fx_raw["rate_label"] = fx_raw["paper_name"].apply(
        lambda pn: _extract_fx_rate_label(str(pn) if pd.notna(pn) else "")
    )
    fx_raw["rate_value"] = fx_raw["rate_label"].apply(_extract_fx_rate_value)

    fx_transactions = fx_raw[["date", "delta_ils", "delta_usd", "rate_label", "rate_value"]].copy()
    fx_transactions["delta_ils"] = pd.to_numeric(fx_transactions["delta_ils"], errors="coerce")
    fx_transactions["delta_usd"] = pd.to_numeric(fx_transactions["delta_usd"], errors="coerce")

    chart_ready = fx_transactions.dropna(subset=["rate_value", "delta_ils"]).sort_values("date")

    if chart_ready.empty:
        fx_summary = None
    else:
        fx_summary = FxSummary(
            avg_rate=float(chart_ready["rate_value"].mean()),
            total_ils_converted=float(chart_ready["delta_ils"].abs().sum()),
            total_usd_produced=float(chart_ready["delta_usd"].abs().sum()),
        )

    return BalanceResult(
        timeline=timeline,
        fx_transactions=fx_transactions,
        fx_summary=fx_summary,
    )


__all__ = ["FxSummary", "BalanceResult", "get_balance_summary"]
