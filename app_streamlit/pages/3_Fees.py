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
from trade_lens.services.fees import get_fees_summary

st.set_page_config(page_title="Fees — Trade Lens", layout="wide")
inject_global_css()
st.subheader("Fees")
st.caption("What you paid your broker — trading commissions and account maintenance charges.")

if "ledger" not in st.session_state:
    st.info("Upload files on the Home page first.")
    st.stop()

ledger = st.session_state["ledger"]

preview = get_fees_summary(ledger)
if not preview.year_options:
    st.info("No fees data available.")
    st.stop()

selected_year = st.selectbox("Year", options=preview.year_options, index=0, key="fees_year")
fees = get_fees_summary(ledger, selected_year) if selected_year != preview.selected_year else preview

# ---------------------------------------------------------------------------
# Trading Fees (USD)
# ---------------------------------------------------------------------------

st.subheader("Trading Fees")

months = fees.trading_monthly.copy()
months["month_label"] = months["month"].dt.strftime("%b")
month_order = pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS").strftime("%b").tolist()

fig = px.bar(
    months, x="month_label", y="fee_amount",
    title=f"Monthly Trading Fees [{selected_year}]",
    labels={"month_label": "Month", "fee_amount": "Amount"},
    category_orders={"month_label": month_order},
)
fig.update_traces(marker_color=CHART_COLORS["negative"], width=0.2)
fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)", template=get_plotly_template())
st.plotly_chart(fig, width="stretch")

if not fees.trading_by_year.empty:
    st.metric("Total Trading Fees", f"${fees.trading_total:,.2f}")

    if not fees.trading_by_ticker.empty:
        ticker_df = fees.trading_by_ticker.copy()
        if "symbol" in fees.trading_by_year.columns:
            action_counts = fees.trading_by_year.groupby("symbol").size().rename("Actions").reset_index()
            ticker_df = ticker_df.merge(action_counts, on="symbol", how="left")
        st.dataframe(
            ticker_df[["symbol", "Actions", "amount_value"]].rename(columns={"symbol": "Ticker", "amount_value": "Total"}),
            column_config={"Total": st.column_config.NumberColumn("Total", format="$%.2f")},
            hide_index=True,
        )

    st.markdown("**Transactions**")
    cols = [c for c in ("date", "action_type", "symbol", "amount") if c in fees.trading_by_year.columns]
    txn_df = order_table_newest_first_with_chrono_index(df_dates_to_date_only(fees.trading_by_year[cols].copy()), "date")
    st.dataframe(txn_df.rename(columns={"action_type": "Action", "symbol": "Ticker", "amount": "Amount"}), width="stretch", hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Account Maintenance Fees (ILS)
# ---------------------------------------------------------------------------

st.subheader("Account Maintenance Fees")

if fees.maintenance_by_year.empty:
    st.info("No account maintenance fee rows found for this year.")
else:
    maint_months = fees.maintenance_monthly.copy()
    maint_months["month_label"] = maint_months["month"].dt.strftime("%b")
    maint_month_order = pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS").strftime("%b").tolist()

    maint_fig = px.bar(
        maint_months, x="month_label", y="fee_amount",
        title=f"Monthly Account Maintenance Fees [{selected_year}]",
        labels={"month_label": "Month", "fee_amount": "Amount"},
        category_orders={"month_label": maint_month_order},
    )
    maint_fig.update_traces(marker_color=CHART_COLORS["warning"], width=0.2)
    maint_fig.update_layout(xaxis_title="Month", yaxis_title="Amount (₪)", template=get_plotly_template())
    st.plotly_chart(maint_fig, width="stretch")

    st.metric("Total Maintenance Fees", f"₪{fees.maintenance_total:,.2f}")

    st.markdown("**Transactions**")
    maint_df = order_table_newest_first_with_chrono_index(
        df_dates_to_date_only(fees.maintenance_by_year[["date", "amount"]].copy()), "date"
    )
    st.dataframe(maint_df.rename(columns={"amount": "Amount"}), width="stretch", hide_index=True)
