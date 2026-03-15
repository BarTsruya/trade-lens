from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType


TAX_ACTION_TYPES = {
    RawActionType.TAX_SHIELD_ACCRUAL.value,
    RawActionType.TAX_SHIELD_RESET.value,
    RawActionType.TAX_PAYABLE.value,
    RawActionType.TAX_PAYMENT.value,
    RawActionType.TAX_CREDIT.value,
}


def build_tax_ledger(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """Filter ledger to tax-related rows and compute running tax state.

    Returns a DataFrame with columns:
      date, action_type, paper_name, amount (formatted str),
      tax_shield_state (float), tax_payable_state (float),
      total_annual_tax (float), _annual_year_end (bool),
      _display_idx (passed through if present in input).

    State columns are raw floats; the caller is responsible for display formatting.
    Returns an empty DataFrame if no tax rows are found.
    """
    taxes_df = ledger_df.loc[
        ledger_df["action_type"].astype("string").isin(TAX_ACTION_TYPES)
    ].copy()
    if taxes_df.empty:
        return pd.DataFrame()

    taxes_df["date"] = pd.to_datetime(taxes_df["date"], errors="coerce")
    taxes_df = taxes_df.loc[taxes_df["date"].notna()].copy()
    if taxes_df.empty:
        return pd.DataFrame()

    taxes_df.sort_values(by="date", ascending=True, inplace=True, kind="mergesort")

    ils_abs = pd.to_numeric(taxes_df["delta_ils"], errors="coerce").fillna(0.0).abs()
    usd_abs = pd.to_numeric(taxes_df["delta_usd"], errors="coerce").fillna(0.0).abs()
    quantity_abs = pd.to_numeric(taxes_df.get("quantity"), errors="coerce").fillna(0.0).abs()

    amount_symbol = pd.Series("", index=taxes_df.index, dtype="string")
    amount_value = pd.Series(0.0, index=taxes_df.index, dtype="float64")

    action_series = taxes_df["action_type"].astype("string")
    accrual_mask = action_series == RawActionType.TAX_SHIELD_ACCRUAL.value
    payable_mask = action_series == RawActionType.TAX_PAYABLE.value
    ils_mask = ils_abs > 0
    usd_mask = (~ils_mask) & (usd_abs > 0)

    amount_symbol.loc[ils_mask] = "₪"
    amount_symbol.loc[usd_mask] = "$"
    amount_value.loc[ils_mask] = ils_abs.loc[ils_mask]
    amount_value.loc[usd_mask] = usd_abs.loc[usd_mask]

    # Tax shield accrual and payable amounts come from quantity, always in ILS.
    amount_value.loc[accrual_mask] = quantity_abs.loc[accrual_mask]
    amount_symbol.loc[accrual_mask] = "₪"
    amount_value.loc[payable_mask] = quantity_abs.loc[payable_mask]
    amount_symbol.loc[payable_mask] = "₪"

    taxes_df["amount"] = amount_symbol.astype(str) + amount_value.map(lambda v: f"{float(v):,.2f}")
    empty_amount_mask = amount_value == 0
    if empty_amount_mask.any():
        taxes_df.loc[empty_amount_mask, "amount"] = "0.00"

    # --- State machine (chronological order) ---
    # tax_shield_state: accumulates TAX_SHIELD_ACCRUAL; zeroed by TAX_PAYMENT;
    #                   reduced by tax_payable_state value on TAX_CREDIT.
    # tax_payable_state: accumulates TAX_PAYABLE; zeroed by TAX_PAYMENT or TAX_CREDIT.
    shield_state = 0.0
    payable_state = 0.0
    annual_tax_total = 0.0
    current_year: int | None = None
    shield_state_values: list[float] = []
    payable_state_values: list[float] = []
    annual_tax_values: list[float] = []

    for idx, action_type in action_series.items():
        amount = float(amount_value.loc[idx])
        row_year = int(taxes_df.loc[idx, "date"].year)
        if current_year is None or row_year != current_year:
            annual_tax_total = 0.0
            current_year = row_year

        if action_type == RawActionType.TAX_SHIELD_ACCRUAL.value:
            shield_state += amount
        elif action_type == RawActionType.TAX_SHIELD_RESET.value:
            shield_state = 0.0
        elif action_type == RawActionType.TAX_PAYABLE.value:
            payable_state += amount
        elif action_type == RawActionType.TAX_PAYMENT.value:
            shield_state = 0.0
            payable_state = 0.0
            annual_tax_total += amount
        elif action_type == RawActionType.TAX_CREDIT.value:
            shield_state = max(0.0, shield_state - payable_state - amount)
            payable_state = 0.0
            annual_tax_total = max(0.0, annual_tax_total - amount)

        shield_state_values.append(shield_state)
        payable_state_values.append(payable_state)
        annual_tax_values.append(annual_tax_total)

    taxes_df["tax_shield_state"] = pd.Series(shield_state_values, index=taxes_df.index)
    taxes_df["tax_payable_state"] = pd.Series(payable_state_values, index=taxes_df.index)
    taxes_df["total_annual_tax"] = pd.Series(annual_tax_values, index=taxes_df.index)

    year_series = taxes_df["date"].dt.year
    taxes_df["_annual_year_end"] = (year_series != year_series.shift(-1)).fillna(True)

    result_cols = [
        "date",
        "action_type",
        "paper_name",
        "amount",
        "tax_shield_state",
        "tax_payable_state",
        "total_annual_tax",
        "_annual_year_end",
    ]
    out = taxes_df[result_cols].copy()
    if "_display_idx" in taxes_df.columns:
        out["_display_idx"] = taxes_df["_display_idx"]
    return out


__all__ = ["TAX_ACTION_TYPES", "build_tax_ledger"]
