from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from display_utils import (
    CHART_COLORS,
    df_dates_to_date_only,
    format_signed_currency,
    inject_global_css,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.services.balance import get_balance_summary

st.set_page_config(page_title="Balance — Trade Lens", layout="wide")
inject_global_css()
st.subheader("Balance")
st.caption("Action-level cash timeline with running balances based on cash-affecting rows.")
st.caption("Rows are displayed newest first. Index labels are chronological (1 = oldest).")

if "ledger" not in st.session_state:
    st.info("Upload files on the Home page first.")
    st.stop()

balance = get_balance_summary(st.session_state["ledger"])

# ---------------------------------------------------------------------------
# Running balance table
# ---------------------------------------------------------------------------

if balance.timeline.empty:
    st.warning("No balance actions found.")
    st.stop()

table_df = df_dates_to_date_only(balance.timeline).drop(columns=["expected_ils_balance"], errors="ignore")
for col in ("usd_delta", "fees_usd", "usd_balance"):
    if col in table_df.columns:
        table_df[col] = table_df[col].map(lambda v: format_signed_currency(v, "$"))
for col in ("ils_delta", "ils_balance"):
    if col in table_df.columns:
        table_df[col] = table_df[col].map(lambda v: format_signed_currency(v, "₪"))
table_df = order_table_newest_first_with_chrono_index(table_df, "date")
table_df = table_df.drop(columns=["_display_idx", "action_type"], errors="ignore")
st.dataframe(table_df, width="stretch", hide_index=False)

# ---------------------------------------------------------------------------
# FX conversions
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Foreign Exchange Conversions")

if balance.fx_transactions.empty:
    st.info("No foreign exchange conversion rows found.")
    st.stop()

fx = balance.fx_transactions.copy()
chart_df = fx.dropna(subset=["rate_value", "delta_ils"]).sort_values("date").copy()
chart_df["delta_ils_abs"] = chart_df["delta_ils"].abs()
chart_df["delta_usd_abs"] = chart_df["delta_usd"].abs()

if not chart_df.empty:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=chart_df["date"], y=chart_df["delta_ils_abs"], name="ILS Converted", marker_color="#0369A1"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=chart_df["date"], y=chart_df["rate_value"], name="Rate (USD/ILS)", mode="lines+markers", marker_color=CHART_COLORS["warning"]),
        secondary_y=True,
    )
    fig.update_layout(title="ILS Converted & Conversion Rate Over Time", xaxis_title="Date", template="plotly_white")
    fig.update_yaxes(title_text="ILS Amount (₪)", secondary_y=False)
    fig.update_yaxes(title_text="Rate (USD/ILS)", secondary_y=True)
    st.plotly_chart(fig, width="stretch")

    if balance.fx_summary is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Average Rate (USD/ILS)", f"{balance.fx_summary.avg_rate:,.4f}")
        c2.metric("Total ILS Converted",    f"₪{balance.fx_summary.total_ils_converted:,.2f}")
        c3.metric("Total USD Produced",     f"${balance.fx_summary.total_usd_produced:,.2f}")

fx["ILS Amount"] = fx["delta_ils"].map(lambda v: format_signed_currency(v, "₪"))
fx["USD Amount"] = fx["delta_usd"].map(lambda v: format_signed_currency(v, "$"))
fx["Rate"] = fx["rate_label"]
fx_display = order_table_newest_first_with_chrono_index(fx[["date", "USD Amount", "ILS Amount", "Rate"]].copy(), "date")
st.dataframe(fx_display, width="stretch", hide_index=True)
