from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from display_utils import (
    CHART_COLORS,
    df_dates_to_date_only,
    get_plotly_template,
    inject_global_css,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.services.dividends import get_dividend_summary

st.set_page_config(page_title="Dividends — Trade Lens", layout="wide")
inject_global_css()
st.subheader("Dividends")
st.caption("Cash payments received from stocks you hold, broken down by month and ticker.")

if "ledger" not in st.session_state:
    st.info("Upload files on the Home page first.")
    st.stop()

ledger = st.session_state["ledger"]

preview = get_dividend_summary(ledger)
if not preview.year_options:
    st.info("No dividend deposit actions found.")
    st.stop()

selected_year = st.selectbox("Year", options=preview.year_options, index=0, key="dividend_year")
div = get_dividend_summary(ledger, selected_year) if selected_year != preview.selected_year else preview

# ---------------------------------------------------------------------------
# Monthly chart
# ---------------------------------------------------------------------------

months = div.monthly.copy()
months["month_label"] = months["month"].dt.strftime("%b")
month_order = pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS").strftime("%b").tolist()

fig = px.bar(
    months, x="month_label", y="dividend_amount",
    title=f"Monthly Dividends [{selected_year}]",
    labels={"month_label": "Month", "dividend_amount": "Amount"},
    category_orders={"month_label": month_order},
)
fig.update_traces(marker_color=CHART_COLORS["positive"], width=0.2)
fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)", template=get_plotly_template())
st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Summary by ticker
# ---------------------------------------------------------------------------

if div.deposit_by_year.empty:
    st.info("No dividend deposit rows found for this year.")
    st.stop()

if not div.by_ticker.empty:
    by_ticker = div.by_ticker.copy()
    by_ticker["total"] = by_ticker["amount_currency"] + by_ticker["amount_value"].map(lambda v: f"{v:,.2f}")
    ticker_summary = by_ticker[["ticker", "total"]].rename(columns={"ticker": "Ticker", "total": "Dividends Received"})

    metric_cols = st.columns(max(1, len(div.totals)))
    for col, (cur, val) in zip(metric_cols, div.totals.items()):
        col.metric(f"Total Dividends ({cur})", f"{cur}{val:,.2f}")
    st.dataframe(ticker_summary, hide_index=True)

# ---------------------------------------------------------------------------
# Transactions table
# ---------------------------------------------------------------------------

st.markdown("**Transactions**")
tx_cols = [c for c in ("date", "paper_name", "amount_value") if c in div.deposit_by_year.columns]
tx_df = df_dates_to_date_only(div.deposit_by_year[tx_cols].copy())
tx_df = order_table_newest_first_with_chrono_index(tx_df, "date")
if "paper_name" in tx_df.columns:
    tx_df["paper_name"] = tx_df["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
    tx_df = tx_df.rename(columns={"paper_name": "Ticker"})
tx_df = tx_df.rename(columns={"amount_value": "Amount"})
st.dataframe(tx_df, width="stretch", hide_index=True, column_config={
    "Amount": st.column_config.NumberColumn("Amount", format="$%,.2f"),
})
