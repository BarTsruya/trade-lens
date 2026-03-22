from __future__ import annotations

import plotly.express as px
import streamlit as st

from display_utils import (
    get_plotly_template,
    inject_global_css,
)
from trade_lens.services.portfolio import get_holdings_summary

st.set_page_config(page_title="Portfolio — Trade Lens", layout="wide")
inject_global_css()
st.subheader("Portfolio")
st.caption("Your current holdings by cost basis.")

if "ledger" not in st.session_state:
    st.info("Upload files on the Home page first.")
    st.stop()

ledger = st.session_state["ledger"]
summary = get_holdings_summary(ledger)

# ---------------------------------------------------------------------------
# Current Holdings
# ---------------------------------------------------------------------------

st.subheader("Current Holdings")

if summary.holdings.empty:
    st.info("No open positions found.")
else:
    h = summary.holdings.copy()

    fig = px.pie(
        h,
        values="total_cost",
        names="symbol",
        hole=0.4,
        template=get_plotly_template(),
    )
    fig.update_traces(textinfo="label+percent", hovertemplate="%{label}<br>$%{value:,.2f}<extra></extra>")
    fig.update_layout(title="Cost Basis Allocation", showlegend=False, margin=dict(t=40, b=20, l=20, r=20))
    st.plotly_chart(fig, width="stretch")

    display_h = h[["symbol", "paper_name", "quantity", "avg_price", "total_cost"]].rename(columns={
        "symbol": "Ticker",
        "paper_name": "Name",
        "quantity": "Qty",
        "avg_price": "Avg Buy Price",
        "total_cost": "Cost Basis",
    })
    st.dataframe(
        display_h,
        column_config={
            "Qty": st.column_config.NumberColumn(format="%.4g"),
            "Avg Buy Price": st.column_config.NumberColumn(format="$%.2f"),
            "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
        },
        hide_index=True,
        width="stretch",
    )
