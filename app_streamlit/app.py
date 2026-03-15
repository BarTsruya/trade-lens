from __future__ import annotations

import re
from typing import Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    format_signed_currency,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.analytics.balance import balance_timeline_actions
from trade_lens.analytics.cashflow import monthly_fees_breakdown
from trade_lens.analytics.ledger import (
    filter_ledger,
    ledger_action_options,
    ledger_date_bounds,
    ledger_symbol_options,
)
from trade_lens.analytics.taxes import build_tax_ledger
from trade_lens.brokers.ibi import RawActionType
from trade_lens.pipeline.loader import count_unknown_action_rows, load_and_normalize_many


st.set_page_config(page_title="Trade Lens", layout="wide")
st.title("Trade Lens - IBI Actions Explorer")
st.caption("Upload an IBI actions .xlsx export to inspect ledger, cashflow, fees, and symbol activity.")


@st.cache_data(show_spinner=False)
def _cached_load(file_payloads: Tuple[Tuple[str, bytes], ...]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return load_and_normalize_many(file_payloads)


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

uploaded_files = st.file_uploader("Upload IBI actions export", type=["xlsx"], accept_multiple_files=True)

if not uploaded_files:
    st.info("Upload one or more .xlsx files to begin.")
    st.stop()

try:
    payloads = tuple((f.name, f.getvalue()) for f in uploaded_files)
    raw, ledger = _cached_load(payloads)
except Exception as exc:
    st.error("Could not load these files. Make sure each is a valid IBI actions .xlsx export.")
    st.exception(exc)
    st.stop()

unknown_action_rows = count_unknown_action_rows(raw)
if unknown_action_rows > 0:
    st.warning(
        f"Loaded {len(uploaded_files):,} file(s): {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows. "
        f"Detected {unknown_action_rows:,} row(s) with unrecognized action types."
    )
else:
    st.success(
        f"Loaded {len(uploaded_files):,} file(s): {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows."
    )

tab_ledger, tab_balance, tab_fees, tab_taxes = st.tabs(["Ledger", "Balance", "Fees", "Taxes"])

# ---------------------------------------------------------------------------
# Ledger tab
# ---------------------------------------------------------------------------

with tab_ledger:
    st.subheader("Ledger Preview")

    min_date, max_date = ledger_date_bounds(ledger)
    default_date_range = (min_date, max_date)
    action_options = ledger_action_options(ledger)
    symbol_options = ledger_symbol_options(ledger)

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        if st.button("Full range", key="ledger_filter_full_range") and all(default_date_range):
            st.session_state["ledger_filter_date_range"] = default_date_range
            st.rerun()
        st.markdown("Date range")
        selected_date_range = st.date_input(
            "Date range",
            value=default_date_range if all(default_date_range) else (),
            key="ledger_filter_date_range",
            label_visibility="collapsed",
        )
    with filter_col2:
        if st.button("All types", key="ledger_filter_all_types"):
            for v in action_options:
                st.session_state[f"ledger_filter_action_visible_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"] = False
            st.rerun()
        st.markdown("Action type")
        selected_action_types: list[str] = []
        with st.expander("Select action types", expanded=False):
            for v in action_options:
                key = f"ledger_filter_action_visible_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"
                if st.checkbox(v, value=False, key=key):
                    selected_action_types.append(v)
    with filter_col3:
        if st.button("All symbols", key="ledger_filter_all_symbols"):
            for v in symbol_options:
                st.session_state[f"ledger_filter_symbol_visible_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"] = False
            st.rerun()
        st.markdown("Symbol")
        selected_symbols: list[str] = []
        with st.expander("Select symbols", expanded=False):
            for v in symbol_options:
                key = f"ledger_filter_symbol_visible_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"
                if st.checkbox(v, value=False, key=key):
                    selected_symbols.append(v)

    active_date_range = (
        (selected_date_range[0], selected_date_range[1])
        if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2 and all(selected_date_range)
        else None
    )
    filtered_ledger = filter_ledger(
        ledger,
        date_range=active_date_range,
        action_types=selected_action_types or None,
        symbols=selected_symbols or None,
    )

    f_dates = pd.to_datetime(filtered_ledger.get("date"), errors="coerce")
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    stat_col1.metric("Rows (filtered)", f"{len(filtered_ledger):,}")
    stat_col2.metric("Date From", "N/A" if f_dates.empty or f_dates.isna().all() else str(f_dates.min().date()))
    stat_col3.metric("Date To", "N/A" if f_dates.empty or f_dates.isna().all() else str(f_dates.max().date()))

    ledger_display_df = df_dates_to_date_only(filtered_ledger)
    for drop_col in ("execution_price", "ledger_row_id", "_source_order", "_date_desc", "expected_ils_balance"):
        if drop_col in ledger_display_df.columns:
            ledger_display_df = ledger_display_df.drop(columns=[drop_col])
    for usd_col in ("delta_usd", "fees_usd"):
        if usd_col in ledger_display_df.columns:
            ledger_display_df[usd_col] = ledger_display_df[usd_col].map(lambda v: format_signed_currency(v, "$"))
    if "delta_ils" in ledger_display_df.columns:
        ledger_display_df["delta_ils"] = ledger_display_df["delta_ils"].map(lambda v: format_signed_currency(v, "₪"))
    if "estimated_capital_gains_tax" in ledger_display_df.columns:
        ledger_display_df["estimated_capital_gains_tax"] = ledger_display_df["estimated_capital_gains_tax"].map(
            lambda v: format_signed_currency(v, "₪")
        )

    filtered_csv = (
        filtered_ledger.drop(
            columns=["_source_order", "_date_desc", "_display_idx", "expected_ils_balance", "ledger_row_id"],
            errors="ignore",
        )
        .to_csv(index=False)
        .encode("utf-8")
    )
    st.download_button("Download filtered ledger (CSV)", data=filtered_csv, file_name="ledger_filtered.csv", mime="text/csv")

    ledger_display_df = order_table_newest_first_with_chrono_index(ledger_display_df, "date")
    if "_display_idx" in ledger_display_df.columns:
        ledger_display_df = ledger_display_df.drop(columns=["_display_idx"])
    st.dataframe(ledger_display_df, width="stretch", hide_index=False)

# ---------------------------------------------------------------------------
# Balance tab
# ---------------------------------------------------------------------------

with tab_balance:
    st.subheader("Balance")
    st.caption("Action-level cash timeline with running balances based on cash-affecting rows.")
    st.caption("Rows are displayed newest first. Index labels are chronological (1 = oldest).")

    balance_df = balance_timeline_actions(ledger)
    if not balance_df.empty:
        balance_df["_display_idx"] = pd.to_numeric(ledger.get("_display_idx"), errors="coerce").reindex(balance_df.index)

    if balance_df.empty:
        st.warning("No balance actions found for these action types.")
    else:
        balance_display_df = df_dates_to_date_only(balance_df)
        balance_table_df = balance_display_df.drop(columns=["expected_ils_balance"], errors="ignore").copy()
        for usd_col in ("usd_delta", "fees_usd", "usd_balance"):
            if usd_col in balance_table_df.columns:
                balance_table_df[usd_col] = balance_table_df[usd_col].map(lambda v: format_signed_currency(v, "$"))
        for ils_col in ("ils_delta", "ils_balance"):
            if ils_col in balance_table_df.columns:
                balance_table_df[ils_col] = balance_table_df[ils_col].map(lambda v: format_signed_currency(v, "₪"))
        balance_table_df = order_table_newest_first_with_chrono_index(balance_table_df, "date")
        if "_display_idx" in balance_table_df.columns:
            balance_table_df = balance_table_df.drop(columns=["_display_idx"])
        st.dataframe(balance_table_df, width="stretch", hide_index=False)

        balance_long = balance_display_df.melt(
            id_vars=["date"], value_vars=["usd_balance", "ils_balance"],
            var_name="balance_type", value_name="balance",
        )
        st.plotly_chart(
            px.line(balance_long, x="date", y="balance", color="balance_type",
                    title="Running USD and ILS Balances",
                    labels={"date": "Day", "balance": "Balance", "balance_type": "Series"}),
            width="stretch",
        )

# ---------------------------------------------------------------------------
# Fees tab
# ---------------------------------------------------------------------------

with tab_fees:
    st.subheader("Monthly Fees Breakdown")

    fees_df = monthly_fees_breakdown(ledger)
    if fees_df.empty:
        st.warning("No fees data available.")
    else:
        fees_display_df = df_dates_to_date_only(fees_df)
        fees_long = fees_display_df.melt(
            id_vars=["month"], value_vars=["embedded_fees_usd", "cash_handling_delta_ils"],
            var_name="fee_type", value_name="amount",
        )
        st.plotly_chart(
            px.bar(fees_long, x="month", y="amount", color="fee_type", barmode="group",
                   title="Monthly Fees Breakdown",
                   labels={"month": "Month", "amount": "Amount", "fee_type": "Fee Type"}),
            width="stretch",
        )
        fees_display_df = order_table_newest_first_with_chrono_index(fees_display_df, "month")
        st.dataframe(fees_display_df, width="stretch", hide_index=False)

# ---------------------------------------------------------------------------
# Taxes tab
# ---------------------------------------------------------------------------

with tab_taxes:
    st.subheader("Taxes")

    required_cols = {"action_type", "date", "delta_ils", "delta_usd", "paper_name", "quantity"}
    missing_cols = sorted(required_cols - set(ledger.columns))
    if missing_cols:
        st.warning("Cannot build taxes table because required columns are missing: " + ", ".join(missing_cols))
    else:
        taxes_table_df = build_tax_ledger(ledger)
        if taxes_table_df.empty:
            st.info("No tax-related actions found.")
        else:
            taxes_table_df["date"] = pd.to_datetime(taxes_table_df["date"], errors="coerce")

            # --- Year filter ---
            _available_years = sorted(taxes_table_df["date"].dt.year.dropna().unique().astype(int), reverse=True)
            selected_year = st.selectbox("Year", options=_available_years, index=0, key="taxes_year_filter")

            # --- Filter to selected year and sort chronologically ---
            taxes_y = taxes_table_df[taxes_table_df["date"].dt.year == selected_year].copy()
            _sort_cols = ["date", "_display_idx"] if "_display_idx" in taxes_y.columns else ["date"]
            taxes_y = taxes_y.sort_values(_sort_cols, ascending=True, kind="mergesort").reset_index(drop=True)

            # --- Pre-event snapshot columns (shift(1) gives state before each row) ---
            taxes_y["pre_tax_payable_state"] = taxes_y["tax_payable_state"].shift(1).fillna(0.0)
            taxes_y["pre_tax_shield_state"]  = taxes_y["tax_shield_state"].shift(1).fillna(0.0)
            taxes_y["month"] = taxes_y["date"].dt.to_period("M").dt.to_timestamp()

            # --- Canonical 12-month axis ---
            months_df = pd.DataFrame({
                "month": pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS")
            })

            _pay_val  = RawActionType.TAX_PAYMENT.value
            _cred_val = RawActionType.TAX_CREDIT.value
            _pay_rows  = taxes_y[taxes_y["action_type"].astype("string") == _pay_val]
            _cred_rows = taxes_y[taxes_y["action_type"].astype("string") == _cred_val]

            # Snapshot: first payment event per month -> pre-event payable/shield
            _pay_snap = (
                _pay_rows.groupby("month", sort=True)
                .first()[["pre_tax_payable_state", "pre_tax_shield_state"]]
                .reset_index()
            )
            # Summed amounts per month
            _pay_amt = (
                _pay_rows.groupby("month", sort=True)["amount_value"]
                .sum().reset_index()
                .rename(columns={"amount_value": "payment_amount"})
            )
            _cred_amt = (
                _cred_rows.groupby("month", sort=True)["amount_value"]
                .sum().reset_index()
                .rename(columns={"amount_value": "credit_amount"})
            )

            _chart = (
                months_df
                .merge(_pay_snap, on="month", how="left")
                .merge(_pay_amt,  on="month", how="left")
                .merge(_cred_amt, on="month", how="left")
                .fillna(0.0)
            )
            _month_labels = _chart["month"].dt.strftime("%b")

            _fig = go.Figure()
            _fig.add_trace(go.Bar(
                name="Payable (before payment)",
                x=_month_labels,
                y=_chart["pre_tax_payable_state"],
                marker_color="gray",
                offsetgroup="payable",
            ))
            _fig.add_trace(go.Bar(
                name="Shield (before payment)",
                x=_month_labels,
                y=_chart["pre_tax_shield_state"],
                marker_color="goldenrod",
                offsetgroup="settlement",
            ))
            _fig.add_trace(go.Bar(
                name="Payment Amount",
                x=_month_labels,
                y=_chart["payment_amount"],
                marker_color="crimson",
                offsetgroup="settlement",
            ))
            _fig.add_trace(go.Bar(
                name="Credit Amount",
                x=_month_labels,
                y=_chart["credit_amount"],
                marker_color="seagreen",
                offsetgroup="credit",
            ))
            _fig.update_layout(
                barmode="relative",
                title=f"Taxes — Payable/Shield snapshot + Payments/Credits (Monthly) [{selected_year}]",
                xaxis_title="Month",
                yaxis_title="ILS (₪)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(_fig, width="stretch")

            # --- Summary ---
            st.subheader("Summary")
            _payable_rows = taxes_y[taxes_y["action_type"].astype("string") == RawActionType.TAX_PAYABLE.value]
            _payable_sum  = float(_payable_rows["amount_value"].sum())
            _payment_sum  = float(_pay_rows["amount_value"].sum())
            _credit_sum   = float(_cred_rows["amount_value"].sum())
            _annual_tax   = _payment_sum - _credit_sum
            _remaining_shield = (
                float(taxes_y["tax_shield_state"].dropna().iloc[-1])
                if not taxes_y.empty and taxes_y["tax_shield_state"].notna().any()
                else 0.0
            )
            _sum_col1, _sum_col2, _sum_col3, _sum_col4 = st.columns(4)
            _sum_col1.metric("Total Tax Payables", f"₪{_payable_sum:,.2f}")
            _sum_col2.metric("Total Tax Credits",  f"₪{_credit_sum:,.2f}")
            _sum_col3.metric("Annual Tax (payments − credits)", f"₪{_annual_tax:,.2f}")
            _sum_col4.metric("Remaining Tax Shield", f"₪{_remaining_shield:,.2f}")

            # --- Table (year-filtered, formatted) ---
            taxes_display_df = taxes_y.drop(
                columns=["pre_tax_payable_state", "pre_tax_shield_state", "month"],
                errors="ignore",
            ).copy()

            for col in ("tax_shield_state", "tax_payable_state", "total_annual_tax"):
                taxes_display_df[col] = taxes_display_df[col].map(lambda v: format_signed_currency(v, "₪"))

            taxes_display_df = order_table_newest_first_with_chrono_index(taxes_display_df, "date")
            if "_display_idx" in taxes_display_df.columns:
                taxes_display_df = taxes_display_df.drop(columns=["_display_idx"])
            annual_year_end_index = set(
                taxes_display_df.index[taxes_display_df["_annual_year_end"].fillna(False)].tolist()
            )
            taxes_display_df = taxes_display_df.drop(columns=["_annual_year_end", "amount_value"], errors="ignore")
            taxes_display_df = df_dates_to_date_only(taxes_display_df)

            def _style_tax_amount(row: pd.Series) -> list[str]:
                styles = [""] * len(row)
                amount_idx = list(row.index).index("amount") if "amount" in row.index else -1
                annual_idx = list(row.index).index("total_annual_tax") if "total_annual_tax" in row.index else -1
                if amount_idx >= 0:
                    action_type = str(row.get("action_type", "") or "")
                    if action_type == RawActionType.TAX_CREDIT.value:
                        styles[amount_idx] = "color: #2e7d32; font-weight: 600;"
                    elif action_type == RawActionType.TAX_PAYMENT.value:
                        styles[amount_idx] = "color: #c62828; font-weight: 600;"
                if annual_idx >= 0 and row.name in annual_year_end_index:
                    styles[annual_idx] = "font-weight: 700;"
                return styles

            st.dataframe(taxes_display_df.style.apply(_style_tax_amount, axis=1), width="stretch", hide_index=False)
