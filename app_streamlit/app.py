from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

from trade_lens.analytics.balance import balance_timeline_daily
from trade_lens.analytics.cashflow import monthly_fees_breakdown, monthly_net_cashflow
from trade_lens.analytics.symbols import symbol_summary
from trade_lens.brokers.ibi import IbiRawLoader
from trade_lens.pipeline.normalize import to_ledger


st.set_page_config(page_title="Trade Lens", layout="wide")
st.title("Trade Lens - IBI Actions Explorer")
st.caption("Upload an IBI actions .xlsx export to inspect ledger, cashflow, fees, and symbol activity.")


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

tab_ledger, tab_balance, tab_cashflow, tab_fees, tab_symbols = st.tabs(
    ["Ledger", "Balance", "Cashflow", "Fees", "Symbols"]
)

with tab_ledger:
    st.subheader("Ledger Preview")

    date_series = pd.to_datetime(ledger.get("date"), errors="coerce")
    min_date = date_series.min()
    max_date = date_series.max()

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    stat_col1.metric("Rows", f"{len(ledger):,}")
    stat_col2.metric("Date From", "N/A" if pd.isna(min_date) else str(min_date.date()))
    stat_col3.metric("Date To", "N/A" if pd.isna(max_date) else str(max_date.date()))

    st.dataframe(ledger, width="stretch", hide_index=True)

with tab_balance:
    st.subheader("Balance")
    st.caption(
        "Aggregated daily balance computed from ILS deposits (transfer_cash_shekel) and "
        "ILS->USD conversions (purchase_shekel symbol 99028). USD deposits are not included yet."
    )

    balance_df = balance_timeline_daily(ledger)

    if balance_df.empty:
        st.warning("No balance actions found for these action types.")
    else:
        st.dataframe(balance_df, width="stretch", hide_index=True)
        balance_long = balance_df.melt(
            id_vars=["day"],
            value_vars=["usd_balance", "ils_balance"],
            var_name="balance_type",
            value_name="balance",
        )
        fig_balance = px.line(
            balance_long,
            x="day",
            y="balance",
            color="balance_type",
            title="Running USD and ILS Balances",
            labels={"day": "Day", "balance": "Balance", "balance_type": "Series"},
        )
        st.plotly_chart(fig_balance, width="stretch")

with tab_cashflow:
    st.subheader("Monthly Net Cashflow (USD)")

    include_deposits = st.checkbox("Include deposits", value=True)
    cashflow_df = monthly_net_cashflow(ledger, currency="USD", include_deposits=include_deposits)

    if cashflow_df.empty:
        st.warning("No cashflow data available.")
    else:
        fig_cashflow = px.bar(
            cashflow_df,
            x="month",
            y="net_usd_sum",
            title="Monthly Net Cashflow (USD)",
            labels={"month": "Month", "net_usd_sum": "Net USD"},
        )
        fig_cashflow.update_layout(xaxis_title="Month", yaxis_title="Net USD")
        st.plotly_chart(fig_cashflow, width="stretch")
        st.dataframe(cashflow_df, width="stretch", hide_index=True)

with tab_fees:
    st.subheader("Monthly Fees Breakdown")

    fees_df = monthly_fees_breakdown(ledger)

    if fees_df.empty:
        st.warning("No fees data available.")
    else:
        fees_long = fees_df.melt(
            id_vars=["month"],
            value_vars=["embedded_fees_usd", "cash_handling_gross_ils"],
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
        st.dataframe(fees_df, width="stretch", hide_index=True)

with tab_symbols:
    st.subheader("Top Symbols (USD)")

    symbols_df = symbol_summary(ledger, currency="USD")
    top_n = st.slider("Top N symbols", min_value=5, max_value=100, value=20, step=5)

    if symbols_df.empty:
        st.warning("No symbol activity data available.")
    else:
        st.dataframe(symbols_df.head(top_n), width="stretch", hide_index=True)
