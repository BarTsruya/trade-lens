from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from display_utils import (
    CHART_COLORS,
    df_dates_to_date_only,
    format_signed_currency,
    get_plotly_template,
    inject_global_css,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.services.balance import get_balance_summary

st.set_page_config(page_title="Balance — Trade Lens", layout="wide")
inject_global_css()
st.subheader("Balance")
st.caption("Your cash in and out over time, with a running total after each transaction.")

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

# Current balances from the most recent timeline row
_last = balance.timeline.iloc[-1]
_current_usd = float(pd.to_numeric(_last.get("usd_balance", 0), errors="coerce") or 0)
_current_ils = float(pd.to_numeric(_last.get("ils_balance", 0), errors="coerce") or 0)
bal_c1, bal_c2 = st.columns(2)
bal_c1.metric("Current USD Balance", f"${_current_usd:,.2f}")
bal_c2.metric("Current ILS Balance", f"₪{_current_ils:,.2f}")

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
st.caption("ILS converted to USD — amounts and the exchange rate at the time of each conversion.")

if balance.fx_transactions.empty:
    st.info("No foreign exchange conversion rows found.")
    st.stop()

fx = balance.fx_transactions.copy()

# ---------------------------------------------------------------------------
# Year filter
# ---------------------------------------------------------------------------

fx_dates = pd.to_datetime(fx["date"], errors="coerce")
fx_years = sorted(fx_dates.dt.year.dropna().unique().astype(int).tolist(), reverse=True)
fx_year_options = ["All time"] + fx_years

fx_year_filter = st.selectbox("Year", options=fx_year_options, key="fx_year_filter")

if fx_year_filter != "All time":
    fx = fx[pd.to_datetime(fx["date"], errors="coerce").dt.year == int(fx_year_filter)].copy()

chart_df = fx.dropna(subset=["rate_value", "delta_ils"]).sort_values("date").copy()
chart_df["delta_ils_abs"] = chart_df["delta_ils"].abs()
chart_df["delta_usd_abs"] = chart_df["delta_usd"].abs()

if not chart_df.empty:
    year_label = str(fx_year_filter) if fx_year_filter != "All time" else "All time"
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=chart_df["date"], y=chart_df["delta_ils_abs"], name="ILS Converted", marker_color="#0369A1"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=chart_df["date"], y=chart_df["rate_value"], name="Rate (USD/ILS)", mode="lines+markers", marker_color=CHART_COLORS["warning"]),
        secondary_y=True,
    )
    fig.update_layout(title=f"ILS Converted & Conversion Rate Over Time [{year_label}]", xaxis_title="Date", template=get_plotly_template())
    fig.update_yaxes(title_text="ILS Amount (₪)", secondary_y=False)
    fig.update_yaxes(title_text="Rate (USD/ILS)", secondary_y=True)
    st.plotly_chart(fig, width="stretch")

    c1, c2, c3 = st.columns(3)
    c1.metric("Average Rate (USD/ILS)", f"{chart_df['rate_value'].mean():,.4f}")
    c2.metric("Total ILS Converted",    f"₪{chart_df['delta_ils_abs'].sum():,.2f}")
    c3.metric("Total USD Produced",     f"${chart_df['delta_usd_abs'].sum():,.2f}")

fx["ILS Amount"] = fx["delta_ils"].map(lambda v: format_signed_currency(abs(float(v)) if pd.notna(pd.to_numeric(v, errors="coerce")) else v, "₪"))
fx["USD Amount"] = fx["delta_usd"].map(lambda v: format_signed_currency(v, "$"))
fx["Rate"] = fx["rate_label"]
fx_display = order_table_newest_first_with_chrono_index(fx[["date", "USD Amount", "ILS Amount", "Rate"]].copy(), "date")
st.dataframe(fx_display, width="stretch", hide_index=True)
