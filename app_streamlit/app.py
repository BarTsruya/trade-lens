from __future__ import annotations

from pathlib import Path
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
def load_and_normalize(file_bytes: bytes, file_name: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load uploaded xlsx with IbiRawLoader, then normalize into ledger schema."""
    suffix = Path(file_name).suffix or ".xlsx"
    temp_path: Optional[str] = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            temp_path = tmp.name

        raw_df = IbiRawLoader(temp_path).load()
        ledger_df = to_ledger(raw_df)
        # Ensure Arrow-friendly dtypes for Streamlit dataframe serialization.
        if "symbol" in ledger_df.columns:
            ledger_df["symbol"] = ledger_df["symbol"].fillna("").astype("string")
        if "action_type" in ledger_df.columns:
            ledger_df["action_type"] = ledger_df["action_type"].fillna("").astype("string")
        if "paper_name" in ledger_df.columns:
            ledger_df["paper_name"] = ledger_df["paper_name"].fillna("").astype("string")
        return raw_df, ledger_df
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


uploaded_file = st.file_uploader("Upload IBI actions export", type=["xlsx"])

if uploaded_file is None:
    st.info("Upload an .xlsx file to begin.")
    st.stop()

try:
    raw, ledger = load_and_normalize(uploaded_file.getvalue(), uploaded_file.name)
except Exception as exc:
    st.error("Could not load this file. Make sure it is a valid IBI actions .xlsx export.")
    st.exception(exc)
    st.stop()

st.success(f"Loaded {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows.")

tab_ledger, tab_balance, tab_fees = st.tabs(["Ledger", "Balance", "Fees"])

with tab_ledger:
    st.subheader("Ledger Preview")

    date_series = pd.to_datetime(ledger.get("date"), errors="coerce")
    min_date = date_series.min()
    max_date = date_series.max()

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    stat_col1.metric("Rows", f"{len(ledger):,}")
    stat_col2.metric("Date From", "N/A" if pd.isna(min_date) else str(min_date.date()))
    stat_col3.metric("Date To", "N/A" if pd.isna(max_date) else str(max_date.date()))

    ledger_display_df = df_dates_to_date_only(ledger)
    if "execution_price" in ledger_display_df.columns:
        ledger_display_df = ledger_display_df.drop(columns=["execution_price"])
    for usd_col in ("execution_price", "delta_usd", "fees_usd", "estimated_capital_gains_tax"):
        if usd_col in ledger_display_df.columns:
            ledger_display_df[usd_col] = ledger_display_df[usd_col].map(lambda v: _format_signed_currency(v, "$"))
    if "delta_ils" in ledger_display_df.columns:
        ledger_display_df["delta_ils"] = ledger_display_df["delta_ils"].map(
            lambda v: _format_signed_currency(v, "₪")
        )

    st.dataframe(ledger_display_df, width="stretch", hide_index=False)

with tab_balance:
    st.subheader("Balance")
    st.caption(
        "Action-level cash timeline with running balances based on cash-affecting rows."
    )
    st.caption("Index matches Ledger row index for traceability.")

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
