from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    format_signed_currency,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.services.ledger_view import LedgerFilters, get_ledger_view

st.set_page_config(page_title="Ledger — Trade Lens", layout="wide")
st.subheader("Ledger Preview")

if "ledger" not in st.session_state:
    st.info("Upload files on the Home page first.")
    st.stop()

ledger = st.session_state["ledger"]

# Unfiltered view — populates filter control options
full_view = get_ledger_view(ledger)
min_date, max_date = full_view.date_bounds

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    if st.button("Full range", key="ledger_filter_full_range") and all((min_date, max_date)):
        st.session_state["ledger_filter_date_range"] = (min_date, max_date)
        st.rerun()
    st.markdown("Date range")
    selected_date_range = st.date_input(
        "Date range",
        value=(min_date, max_date) if all((min_date, max_date)) else (),
        key="ledger_filter_date_range",
        label_visibility="collapsed",
    )

with filter_col2:
    if st.button("All types", key="ledger_filter_all_types"):
        for v in full_view.action_options:
            st.session_state[f"ledger_action_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"] = False
        st.rerun()
    st.markdown("Action type")
    selected_action_types: list[str] = []
    with st.expander("Select action types", expanded=False):
        for v in full_view.action_options:
            key = f"ledger_action_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"
            if st.checkbox(v, value=False, key=key):
                selected_action_types.append(v)

with filter_col3:
    if st.button("All symbols", key="ledger_filter_all_symbols"):
        for v in full_view.symbol_options:
            st.session_state[f"ledger_symbol_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"] = False
        st.rerun()
    st.markdown("Symbol")
    selected_symbols: list[str] = []
    with st.expander("Select symbols", expanded=False):
        for v in full_view.symbol_options:
            key = f"ledger_symbol_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"
            if st.checkbox(v, value=False, key=key):
                selected_symbols.append(v)

active_date_range = (
    (selected_date_range[0], selected_date_range[1])
    if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2 and all(selected_date_range)
    else None
)
filters = LedgerFilters(
    date_range=active_date_range,
    action_types=selected_action_types or None,
    symbols=selected_symbols or None,
)
view = (
    get_ledger_view(ledger, filters)
    if any([active_date_range, selected_action_types, selected_symbols])
    else full_view
)
filtered = view.filtered

f_dates = pd.to_datetime(filtered.get("date"), errors="coerce")
c1, c2, c3 = st.columns(3)
c1.metric("Rows (filtered)", f"{len(filtered):,}")
c2.metric("Date From", "N/A" if f_dates.empty or f_dates.isna().all() else str(f_dates.min().date()))
c3.metric("Date To",   "N/A" if f_dates.empty or f_dates.isna().all() else str(f_dates.max().date()))

display_df = df_dates_to_date_only(filtered)
for col in ("execution_price", "ledger_row_id", "_source_order", "_date_desc", "expected_ils_balance"):
    if col in display_df.columns:
        display_df = display_df.drop(columns=[col])
for col in ("delta_usd", "fees_usd"):
    if col in display_df.columns:
        display_df[col] = display_df[col].map(lambda v: format_signed_currency(v, "$"))
if "delta_ils" in display_df.columns:
    display_df["delta_ils"] = display_df["delta_ils"].map(lambda v: format_signed_currency(v, "₪"))
if "estimated_capital_gains_tax" in display_df.columns:
    display_df["estimated_capital_gains_tax"] = display_df["estimated_capital_gains_tax"].map(
        lambda v: format_signed_currency(v, "₪")
    )

csv = (
    filtered.drop(
        columns=["_source_order", "_date_desc", "_display_idx", "expected_ils_balance", "ledger_row_id"],
        errors="ignore",
    )
    .to_csv(index=False)
    .encode("utf-8")
)
st.download_button("Download filtered ledger (CSV)", data=csv, file_name="ledger_filtered.csv", mime="text/csv")

display_df = order_table_newest_first_with_chrono_index(display_df, "date")
if "_display_idx" in display_df.columns:
    display_df = display_df.drop(columns=["_display_idx"])
st.dataframe(display_df, width="stretch", hide_index=False)
