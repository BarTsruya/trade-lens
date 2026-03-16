from __future__ import annotations

import pandas as pd

from trade_lens.brokers.ibi import RawActionType
from trade_lens.analytics.dividends import DIVIDEND_TAX_ACTION_TYPES


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
      amount_value (float, ILS), tax_shield_state (float), tax_payable_state (float),
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
    taxes_df["amount_value"] = amount_value

    year_series = taxes_df["date"].dt.year
    taxes_df["_annual_year_end"] = (year_series != year_series.shift(-1)).fillna(True)

    result_cols = [
        "date",
        "action_type",
        "paper_name",
        "amount",
        "amount_value",
        "tax_shield_state",
        "tax_payable_state",
        "total_annual_tax",
        "_annual_year_end",
    ]
    out = taxes_df[result_cols].copy()
    if "_display_idx" in taxes_df.columns:
        out["_display_idx"] = taxes_df["_display_idx"]
    return out


def filter_tax_rows_by_year(df: pd.DataFrame, selected_year: int) -> pd.DataFrame:
    """Return rows from ``df`` whose date belongs to ``selected_year``."""
    if df.empty or "date" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.loc[out["date"].dt.year == selected_year].copy()
    return out


def tax_year_options(ledger_df: pd.DataFrame, capital_tax_df: pd.DataFrame) -> list[int]:
    """Return sorted years available across capital-gain and dividend-tax actions."""
    cap_years: list[int] = []
    if not capital_tax_df.empty and "date" in capital_tax_df.columns:
        cap_dates = pd.to_datetime(capital_tax_df["date"], errors="coerce")
        cap_years = sorted(cap_dates.dt.year.dropna().unique().astype(int), reverse=True)

    div_years: list[int] = []
    if "action_type" in ledger_df.columns and "date" in ledger_df.columns:
        div_rows = ledger_df.loc[
            ledger_df["action_type"].astype("string").isin(DIVIDEND_TAX_ACTION_TYPES),
            "date",
        ]
        div_dates = pd.to_datetime(div_rows, errors="coerce")
        div_years = sorted(div_dates.dt.year.dropna().unique().astype(int), reverse=True)

    return sorted(set(cap_years) | set(div_years), reverse=True)


def build_capital_gains_monthly_chart_df(taxes_y: pd.DataFrame, selected_year: int) -> pd.DataFrame:
    """Build monthly chart data for the capital-gains taxes stacked bar chart.

    Columns returned (all 12 months always present):
      rolling_shield         – end-of-month tax shield state, forward-filled
      pre_settlement_shield  – shield value just before TAX_PAYMENT or TAX_CREDIT; falls back to rolling_shield
      shield_used_bar        – portion of shield consumed: min(pre_settlement_shield, payable + credit) (orange)
      shield_balance_bar     – portion of shield remaining: max(0, pre_settlement_shield - payable - credit) (yellow)
      payable_amount         – sum of TAX_PAYABLE actions per month (gray)
      shield_consumed        – portion of shield covering the payable at TAX_PAYMENT (used to derive shield_used)
      payment_amount         – sum of TAX_PAYMENT cash values per month (red)
      credit_amount          – sum of TAX_CREDIT values per month (green)
    """
    months_df = pd.DataFrame({"month": pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS")})
    if taxes_y.empty:
        return months_df.assign(
            rolling_shield=0.0,
            pre_settlement_shield=0.0,
            shield_used_bar=0.0,
            shield_balance_bar=0.0,
            payable_amount=0.0,
            shield_consumed=0.0,
            payment_amount=0.0,
            credit_amount=0.0,
        )

    df = taxes_y.copy()
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    # Snapshot values on the row before each event (used to capture state consumed at payment).
    df["pre_tax_shield_state"] = pd.to_numeric(df["tax_shield_state"], errors="coerce").shift(1).fillna(0.0)
    df["pre_tax_payable_state"] = pd.to_numeric(df["tax_payable_state"], errors="coerce").shift(1).fillna(0.0)

    action = df["action_type"].astype("string")
    payable_rows = df.loc[action == RawActionType.TAX_PAYABLE.value]
    pay_rows = df.loc[action == RawActionType.TAX_PAYMENT.value]
    cred_rows = df.loc[action == RawActionType.TAX_CREDIT.value]

    # rolling_shield: last known shield state per month, forward-filled up to the
    # last month with any event; zeroed afterwards so no phantom bars appear.
    last_event_month = df["month"].max()
    shield_monthly = (
        df.groupby("month", sort=True)["tax_shield_state"]
        .last()
        .reset_index()
        .rename(columns={"tax_shield_state": "rolling_shield"})
    )
    rolling = months_df.merge(shield_monthly, on="month", how="left")
    rolling["rolling_shield"] = rolling["rolling_shield"].ffill().fillna(0.0)
    rolling.loc[rolling["month"] > last_event_month, "rolling_shield"] = 0.0

    payable_amt = (
        payable_rows.groupby("month", sort=True)["amount_value"]
        .sum()
        .reset_index()
        .rename(columns={"amount_value": "payable_amount"})
    )

    # shield_consumed = portion of the shield that covered the payable at payment time.
    # Capped at pre_payable_state so that when the shield exceeds the payable (fully covered),
    # the orange bar matches the payable amount rather than the entire shield.
    shield_snap = (
        pay_rows.groupby("month", sort=True)["pre_tax_shield_state"]
        .first()
        .reset_index()
    )
    payable_snap = (
        pay_rows.groupby("month", sort=True)["pre_tax_payable_state"]
        .first()
        .reset_index()
    )
    shield_consumed = shield_snap.merge(payable_snap, on="month")
    shield_consumed["shield_consumed"] = shield_consumed[["pre_tax_shield_state", "pre_tax_payable_state"]].min(axis=1)
    shield_consumed = shield_consumed[["month", "shield_consumed"]]

    # Cumulative shield used: running total of shield consumed at payment events.
    _shield_used_tmp = months_df.merge(shield_consumed, on="month", how="left")
    _shield_used_tmp["shield_used"] = _shield_used_tmp["shield_consumed"].fillna(0.0).cumsum()
    shield_used = _shield_used_tmp[["month", "shield_used"]]

    pay_amt = (
        pay_rows.groupby("month", sort=True)["amount_value"]
        .sum()
        .reset_index()
        .rename(columns={"amount_value": "payment_amount"})
    )
    cred_amt = (
        cred_rows.groupby("month", sort=True)["amount_value"]
        .sum()
        .reset_index()
        .rename(columns={"amount_value": "credit_amount"})
    )

    # pre_settlement_shield: shield value just before a TAX_PAYMENT or TAX_CREDIT executes.
    # Falls back to rolling_shield for months without such events.
    _pre_pay_shield = (
        pay_rows.groupby("month", sort=True)["pre_tax_shield_state"]
        .first()
        .reset_index()
        .rename(columns={"pre_tax_shield_state": "_pre_shield"})
    )
    _pre_cred_shield = (
        cred_rows.groupby("month", sort=True)["pre_tax_shield_state"]
        .first()
        .reset_index()
        .rename(columns={"pre_tax_shield_state": "_pre_shield"})
    )
    _pre_both = (
        pd.concat([_pre_pay_shield, _pre_cred_shield], ignore_index=True)
        .groupby("month", sort=True)["_pre_shield"]
        .max()
        .reset_index()
        .rename(columns={"_pre_shield": "pre_settlement_shield"})
    )

    result = (
        rolling
        .merge(payable_amt, on="month", how="left")
        .merge(shield_consumed, on="month", how="left")
        .merge(shield_used, on="month", how="left")
        .merge(_pre_both, on="month", how="left")
        .merge(pay_amt, on="month", how="left")
        .merge(cred_amt, on="month", how="left")
    )
    result["pre_settlement_shield"] = result["pre_settlement_shield"].fillna(result["rolling_shield"])
    result = result.fillna(0.0)
    _consumed = result["payable_amount"] + result["credit_amount"]
    _excess = (result["pre_settlement_shield"] - _consumed).clip(lower=0.0)
    result["shield_balance_bar"] = _excess
    result["shield_used_bar"] = result["pre_settlement_shield"] - _excess
    return result


def build_capital_gains_summary(taxes_y: pd.DataFrame) -> dict[str, float]:
    """Return summary metrics for a selected-year capital-gains ledger."""
    if taxes_y.empty:
        return {
            "payable_sum": 0.0,
            "credit_sum": 0.0,
            "payment_sum": 0.0,
            "annual_tax": 0.0,
            "remaining_shield": 0.0,
        }

    payable_rows = taxes_y.loc[taxes_y["action_type"].astype("string") == RawActionType.TAX_PAYABLE.value]
    payment_rows = taxes_y.loc[taxes_y["action_type"].astype("string") == RawActionType.TAX_PAYMENT.value]
    credit_rows = taxes_y.loc[taxes_y["action_type"].astype("string") == RawActionType.TAX_CREDIT.value]

    payable_sum = float(pd.to_numeric(payable_rows["amount_value"], errors="coerce").fillna(0.0).sum())
    payment_sum = float(pd.to_numeric(payment_rows["amount_value"], errors="coerce").fillna(0.0).sum())
    credit_sum = float(pd.to_numeric(credit_rows["amount_value"], errors="coerce").fillna(0.0).sum())
    remaining_shield = (
        float(pd.to_numeric(taxes_y["tax_shield_state"], errors="coerce").dropna().iloc[-1])
        if taxes_y["tax_shield_state"].notna().any()
        else 0.0
    )

    return {
        "payable_sum": payable_sum,
        "credit_sum": credit_sum,
        "payment_sum": payment_sum,
        "annual_tax": payment_sum - credit_sum,
        "remaining_shield": remaining_shield,
    }


__all__ = [
    "TAX_ACTION_TYPES",
    "build_tax_ledger",
    "filter_tax_rows_by_year",
    "tax_year_options",
    "build_capital_gains_monthly_chart_df",
    "build_capital_gains_summary",
]
