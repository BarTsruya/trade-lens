from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    inject_global_css,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.services.ledger_view import LedgerFilters, get_ledger_view

st.set_page_config(page_title="Ledger — Trade Lens", layout="wide")
inject_global_css()
st.subheader("Ledger")
st.caption("All your transactions in one place. Filter by date, type, or stock.")

if "ledger" not in st.session_state:
    st.info("Upload files on the Home page first.")
    st.stop()

ledger = st.session_state["ledger"]

# Unfiltered view — populates filter control options
full_view = get_ledger_view(ledger)
min_date, max_date = full_view.date_bounds

filter_col1, filter_col2, filter_col3 = st.columns(3)

if "ledger_filter_date_range" not in st.session_state:
    st.session_state["ledger_filter_date_range"] = (min_date, max_date) if all((min_date, max_date)) else ()

def _reset_date_range():
    if all((min_date, max_date)):
        st.session_state["ledger_filter_date_range"] = (min_date, max_date)

def _reset_action_types():
    for v in full_view.action_options:
        st.session_state[f"ledger_action_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"] = False

def _reset_symbols():
    for v in full_view.symbol_options:
        st.session_state[f"ledger_symbol_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"] = False

with filter_col1:
    st.button("Full range", key="ledger_filter_full_range", on_click=_reset_date_range)
    st.markdown("Date range")
    selected_date_range = st.date_input(
        "Date range",
        key="ledger_filter_date_range",
        label_visibility="collapsed",
    )

with filter_col2:
    st.button("All types", key="ledger_filter_all_types", on_click=_reset_action_types)
    st.markdown("Action type")
    selected_action_types: list[str] = []
    with st.expander("Select action types", expanded=False):
        for v in full_view.action_options:
            key = f"ledger_action_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"
            if st.checkbox(v, value=False, key=key):
                selected_action_types.append(v)

with filter_col3:
    st.button("All symbols", key="ledger_filter_all_symbols", on_click=_reset_symbols)
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

_label = "<p style='font-size:0.85rem;opacity:0.6;margin:0'>{}</p>"
c1, c2, c3 = st.columns(3)
c1.markdown(_label.format("Filtered rows amount") + f"{len(filtered):,}", unsafe_allow_html=True)
c2.markdown(_label.format("Chosen types") + (", ".join(selected_action_types) if selected_action_types else "All"), unsafe_allow_html=True)
c3.markdown(_label.format("Chosen symbols") + (", ".join(selected_symbols) if selected_symbols else "All"), unsafe_allow_html=True)

st.markdown("<div style='margin-bottom:1.5rem'></div>", unsafe_allow_html=True)

display_df = df_dates_to_date_only(filtered)
for col in ("execution_price", "ledger_row_id", "_source_order", "_date_desc", "expected_ils_balance"):
    if col in display_df.columns:
        display_df = display_df.drop(columns=[col])

display_df = order_table_newest_first_with_chrono_index(display_df, "date")
if "_display_idx" in display_df.columns:
    display_df = display_df.drop(columns=["_display_idx"])
st.dataframe(
    display_df,
    column_config={
        "delta_usd": st.column_config.NumberColumn("delta_usd", format="$%.2f"),
        "fees_usd": st.column_config.NumberColumn("fees_usd", format="$%.2f"),
        "delta_ils": st.column_config.NumberColumn("delta_ils", format="₪%.2f"),
        "estimated_capital_gains_tax": st.column_config.NumberColumn("estimated_capital_gains_tax", format="₪%.2f"),
    },
    width="stretch",
    hide_index=False,
)
