from __future__ import annotations

from pathlib import Path
import re
import tempfile
from typing import Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

from trade_lens.analytics.balance import balance_timeline_actions
from trade_lens.analytics.cashflow import monthly_fees_breakdown
from trade_lens.brokers.ibi import IbiRawLoader
from trade_lens.pipeline.normalize import to_ledger


st.set_page_config(page_title="Trade Lens", layout="wide")
st.title("Trade Lens - IBI Actions Explorer")
st.caption("Upload an IBI actions .xlsx export to inspect ledger, cashflow, fees, and symbol activity.")


def df_dates_to_date_only(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with date-like columns converted to Python date values."""
    out = df.copy()
    for col in out.columns:
        is_named_date = col == "date" or col.endswith("_date")
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype(out[col])
        if not (is_named_date or is_datetime_dtype):
            continue
        try:
            converted = pd.to_datetime(out[col], errors="coerce")
            if converted.notna().any():
                out[col] = converted.dt.date
        except Exception:
            # Keep original column unchanged if conversion is not possible.
            continue
    return out


def _format_signed_currency(value: object, symbol: str) -> str:
    """Format numeric values as signed currency with sign before symbol."""
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return ""
    prefix = "-" if numeric < 0 else ""
    return f"{prefix}{symbol}{abs(float(numeric)):,.2f}"


@st.cache_data(show_spinner=False)
def load_and_normalize_many(file_payloads: Tuple[Tuple[str, bytes], ...]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load multiple uploaded xlsx files and return combined raw and normalized ledgers."""
    raw_frames: list[pd.DataFrame] = []
    ledger_frames: list[pd.DataFrame] = []

    for file_name, file_bytes in file_payloads:
        suffix = Path(file_name).suffix or ".xlsx"
        temp_path: Optional[str] = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                temp_path = tmp.name

            raw_df_i = IbiRawLoader(temp_path).load()
            raw_df_i = raw_df_i.copy()
            raw_df_i["source_file"] = file_name

            ledger_df_i = to_ledger(raw_df_i)
            ledger_df_i = ledger_df_i.copy()
            ledger_df_i["source_file"] = file_name
            ledger_df_i["ledger_row_id"] = [f"{file_name}:{idx}" for idx in ledger_df_i.index]

            raw_frames.append(raw_df_i)
            ledger_frames.append(ledger_df_i)
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    if not raw_frames or not ledger_frames:
        return pd.DataFrame(), pd.DataFrame()

    raw_all = pd.concat(raw_frames, ignore_index=True)
    ledger_all = pd.concat(ledger_frames, ignore_index=True)

    # Ensure Arrow-friendly dtypes for Streamlit dataframe serialization.
    for col in ("symbol", "action_type", "paper_name", "source_file", "ledger_row_id"):
        if col in ledger_all.columns:
            ledger_all[col] = ledger_all[col].fillna("").astype("string")

    ledger_dt = pd.to_datetime(ledger_all.get("date"), errors="coerce")
    ledger_all = ledger_all.loc[ledger_dt.notna()].copy()
    ledger_all["_date_sort"] = pd.to_datetime(ledger_all["date"], errors="coerce")
    ledger_all.sort_values(by=["_date_sort", "ledger_row_id"], inplace=True, kind="mergesort")
    ledger_all.drop(columns=["_date_sort"], inplace=True)
    ledger_all.reset_index(drop=True, inplace=True)

    return raw_all, ledger_all


uploaded_files = st.file_uploader("Upload IBI actions export", type=["xlsx"], accept_multiple_files=True)

if not uploaded_files:
    st.info("Upload one or more .xlsx files to begin.")
    st.stop()

try:
    payloads = tuple((uploaded_file.name, uploaded_file.getvalue()) for uploaded_file in uploaded_files)
    raw, ledger = load_and_normalize_many(payloads)
except Exception as exc:
    st.error("Could not load these files. Make sure each is a valid IBI actions .xlsx export.")
    st.exception(exc)
    st.stop()

# Re-apply stable date sorting on each rerun (including when files are added/removed).
if "date" in ledger.columns:
    ledger_date_sort = pd.to_datetime(ledger["date"], errors="coerce")
    ledger = ledger.loc[ledger_date_sort.notna()].copy()
    ledger["_date_sort"] = pd.to_datetime(ledger["date"], errors="coerce")
    secondary_sort_col = "source_file" if "source_file" in ledger.columns else None
    sort_cols = ["_date_sort"] + ([secondary_sort_col] if secondary_sort_col else [])
    ledger.sort_values(by=sort_cols, inplace=True, kind="mergesort")
    ledger.drop(columns=["_date_sort"], inplace=True)
    ledger.reset_index(drop=True, inplace=True)

unknown_action_rows = 0
if "action_type" in raw.columns:
    action_type_series = raw["action_type"].astype("string")
    unknown_action_rows = int((action_type_series.isna() | action_type_series.str.strip().eq("")).sum())

if unknown_action_rows > 0:
    st.warning(
        f"Loaded {len(uploaded_files):,} file(s): {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows. "
        f"Detected {unknown_action_rows:,} row(s) with unrecognized action types."
    )
else:
    st.success(
        f"Loaded {len(uploaded_files):,} file(s): {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows."
    )

tab_ledger, tab_balance, tab_fees = st.tabs(["Ledger", "Balance", "Fees"])

with tab_ledger:
    st.subheader("Ledger Preview")

    ledger_filter_df = ledger.copy()
    ledger_filter_df["_date_filter"] = pd.to_datetime(ledger_filter_df.get("date"), errors="coerce")
    ledger_filter_df = ledger_filter_df.loc[ledger_filter_df["_date_filter"].notna()].copy()

    min_date = ledger_filter_df["_date_filter"].min()
    max_date = ledger_filter_df["_date_filter"].max()
    default_date_range = (
        min_date.date() if pd.notna(min_date) else None,
        max_date.date() if pd.notna(max_date) else None,
    )

    action_options = sorted(
        v
        for v in ledger_filter_df.get("action_type", pd.Series(dtype="string")).astype("string").dropna().unique().tolist()
        if str(v).strip()
    )
    symbol_options = sorted(
        v
        for v in ledger_filter_df.get("symbol", pd.Series(dtype="string")).astype("string").dropna().unique().tolist()
        if str(v).strip()
    )

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        full_range_clicked = st.button("Full range", key="ledger_filter_full_range")
        if full_range_clicked and all(default_date_range):
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
            for action_value in action_options:
                action_key = re.sub(r"[^a-zA-Z0-9]+", "_", str(action_value)).strip("_").lower()
                checkbox_key = f"ledger_filter_action_visible_{action_key}"
                st.session_state[checkbox_key] = False
            st.rerun()

        st.markdown("Action type")
        selected_action_types: list[str] = []
        with st.expander("Select action types", expanded=False):
            for action_value in action_options:
                action_key = re.sub(r"[^a-zA-Z0-9]+", "_", str(action_value)).strip("_").lower()
                checkbox_key = f"ledger_filter_action_visible_{action_key}"
                is_visible = st.checkbox(str(action_value), value=False, key=checkbox_key)
                if is_visible:
                    selected_action_types.append(str(action_value))
    with filter_col3:
        if st.button("All symbols", key="ledger_filter_all_symbols"):
            for symbol_value in symbol_options:
                symbol_key = re.sub(r"[^a-zA-Z0-9]+", "_", str(symbol_value)).strip("_").lower()
                checkbox_key = f"ledger_filter_symbol_visible_{symbol_key}"
                st.session_state[checkbox_key] = False
            st.rerun()

        st.markdown("Symbol")
        selected_symbols: list[str] = []
        with st.expander("Select symbols", expanded=False):
            for symbol_value in symbol_options:
                symbol_key = re.sub(r"[^a-zA-Z0-9]+", "_", str(symbol_value)).strip("_").lower()
                checkbox_key = f"ledger_filter_symbol_visible_{symbol_key}"
                is_visible = st.checkbox(str(symbol_value), value=False, key=checkbox_key)
                if is_visible:
                    selected_symbols.append(str(symbol_value))

    mask = pd.Series(True, index=ledger_filter_df.index)

    if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
        if start_date and end_date:
            row_dates = ledger_filter_df["_date_filter"].dt.date
            mask &= (row_dates >= start_date) & (row_dates <= end_date)

    if selected_action_types:
        mask &= ledger_filter_df["action_type"].astype("string").isin(selected_action_types)

    if selected_symbols:
        mask &= ledger_filter_df["symbol"].astype("string").isin(selected_symbols)

    filtered_ledger = ledger_filter_df.loc[mask].copy()

    filtered_min_date = filtered_ledger["_date_filter"].min() if not filtered_ledger.empty else pd.NaT
    filtered_max_date = filtered_ledger["_date_filter"].max() if not filtered_ledger.empty else pd.NaT
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    stat_col1.metric("Rows (filtered)", f"{len(filtered_ledger):,}")
    stat_col2.metric("Date From", "N/A" if pd.isna(filtered_min_date) else str(filtered_min_date.date()))
    stat_col3.metric("Date To", "N/A" if pd.isna(filtered_max_date) else str(filtered_max_date.date()))

    ledger_display_df = df_dates_to_date_only(filtered_ledger.drop(columns=["_date_filter"], errors="ignore"))
    if "execution_price" in ledger_display_df.columns:
        ledger_display_df = ledger_display_df.drop(columns=["execution_price"])
    if "ledger_row_id" in ledger_display_df.columns:
        ledger_display_df = ledger_display_df.drop(columns=["ledger_row_id"])
    for usd_col in ("execution_price", "delta_usd", "fees_usd", "estimated_capital_gains_tax"):
        if usd_col in ledger_display_df.columns:
            ledger_display_df[usd_col] = ledger_display_df[usd_col].map(lambda v: _format_signed_currency(v, "$"))
    if "delta_ils" in ledger_display_df.columns:
        ledger_display_df["delta_ils"] = ledger_display_df["delta_ils"].map(
            lambda v: _format_signed_currency(v, "₪")
        )

    filtered_csv = filtered_ledger.drop(columns=["_date_filter"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered ledger (CSV)",
        data=filtered_csv,
        file_name="ledger_filtered.csv",
        mime="text/csv",
    )

    st.dataframe(ledger_display_df, width="stretch", hide_index=False)

with tab_balance:
    st.subheader("Balance")
    st.caption(
        "Action-level cash timeline with running balances based on cash-affecting rows."
    )
    st.caption("Index matches the Ledger table index for traceability.")

    balance_df = balance_timeline_actions(ledger)

    if balance_df.empty:
        st.warning("No balance actions found for these action types.")
    else:
        balance_display_df = df_dates_to_date_only(balance_df)
        balance_table_df = balance_display_df.copy()
        for usd_col in ("usd_delta", "fees_usd", "usd_balance"):
            if usd_col in balance_table_df.columns:
                balance_table_df[usd_col] = balance_table_df[usd_col].map(lambda v: _format_signed_currency(v, "$"))
        for ils_col in ("ils_delta", "ils_balance"):
            if ils_col in balance_table_df.columns:
                balance_table_df[ils_col] = balance_table_df[ils_col].map(lambda v: _format_signed_currency(v, "₪"))

        st.dataframe(balance_table_df, width="stretch", hide_index=False)
        balance_long = balance_display_df.melt(
            id_vars=["date"],
            value_vars=["usd_balance", "ils_balance"],
            var_name="balance_type",
            value_name="balance",
        )
        fig_balance = px.line(
            balance_long,
            x="date",
            y="balance",
            color="balance_type",
            title="Running USD and ILS Balances",
            labels={"date": "Day", "balance": "Balance", "balance_type": "Series"},
        )
        st.plotly_chart(fig_balance, width="stretch")

with tab_fees:
    st.subheader("Monthly Fees Breakdown")

    fees_df = monthly_fees_breakdown(ledger)

    if fees_df.empty:
        st.warning("No fees data available.")
    else:
        fees_display_df = df_dates_to_date_only(fees_df)
        fees_long = fees_display_df.melt(
            id_vars=["month"],
            value_vars=["embedded_fees_usd", "cash_handling_delta_ils"],
            var_name="fee_type",
            value_name="amount",
        )
        fig_fees = px.bar(
            fees_long,
            x="month",
            y="amount",
            color="fee_type",
            barmode="group",
            title="Monthly Fees Breakdown",
            labels={"month": "Month", "amount": "Amount", "fee_type": "Fee Type"},
        )
        st.plotly_chart(fig_fees, width="stretch")
        st.dataframe(fees_display_df, width="stretch", hide_index=True)
