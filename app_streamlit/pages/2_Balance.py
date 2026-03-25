from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from display_utils import (
    CHART_COLORS,
    df_dates_to_date_only,
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
table_df = order_table_newest_first_with_chrono_index(table_df, "date")
table_df = table_df.drop(columns=["_display_idx", "action_type"], errors="ignore")
st.dataframe(
    table_df,
    column_config={
        "usd_delta":  st.column_config.NumberColumn("usd_delta",  format="$%,.2f"),
        "fees_usd":   st.column_config.NumberColumn("fees_usd",   format="$%,.2f"),
        "usd_balance": st.column_config.NumberColumn("usd_balance", format="$%,.2f"),
        "ils_delta":  st.column_config.NumberColumn("ils_delta",  format="₪%,.2f"),
        "ils_balance": st.column_config.NumberColumn("ils_balance", format="₪%,.2f"),
    },
    width="stretch",
    hide_index=False,
)

# ---------------------------------------------------------------------------
# Cash Deposits
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Cash Deposits")
st.caption("External cash deposited into your account over time.")

deposits_df = balance.timeline[balance.timeline["action_type"] == "cash_deposit"].copy()
deposits_df["date"] = pd.to_datetime(deposits_df["date"], errors="coerce")
deposits_df["usd_delta"] = pd.to_numeric(deposits_df["usd_delta"], errors="coerce").fillna(0.0)
deposits_df["ils_delta"] = pd.to_numeric(deposits_df["ils_delta"], errors="coerce").fillna(0.0)

if deposits_df.empty:
    st.info("No cash deposits found.")
else:
    total_usd = deposits_df["usd_delta"].sum()
    total_ils = deposits_df["ils_delta"].sum()

    d1, d2, d3 = st.columns(3)
    d1.metric("Total USD Deposited", f"${total_usd:,.2f}")
    d2.metric("Total ILS Deposited", f"₪{total_ils:,.2f}")
    d3.metric("Number of Deposits",  str(len(deposits_df)))

    _usd = deposits_df[deposits_df["usd_delta"] != 0].sort_values("date")[["date", "usd_delta"]].copy()
    _usd["cumulative"] = _usd["usd_delta"].cumsum()
    _usd = _usd.rename(columns={"usd_delta": "amount"})
    _usd["currency"] = "USD"

    _ils = deposits_df[deposits_df["ils_delta"] != 0].sort_values("date")[["date", "ils_delta"]].copy()
    _ils["cumulative"] = _ils["ils_delta"].cumsum()
    _ils = _ils.rename(columns={"ils_delta": "amount"})
    _ils["currency"] = "ILS"

    cdf = pd.concat([_usd, _ils]).reset_index(drop=True)
    cdf["date"] = pd.to_datetime(cdf["date"])

    fig = go.Figure()
    if not _ils.empty:
        fig.add_trace(go.Scatter(
            x=_ils["date"], y=_ils["cumulative"],
            mode="lines+markers",
            name="ILS",
            line=dict(color="#fb923c"),
            marker=dict(color="#fb923c", size=8),
            customdata=_ils[["amount"]].values,
            hovertemplate="<b>ILS deposit</b><br>Date: %{x|%Y-%m-%d}<br>Amount: ₪%{customdata[0]:,.2f}<br>Cumulative: ₪%{y:,.2f}<extra></extra>",
        ))
    if not _usd.empty:
        fig.add_trace(go.Scatter(
            x=_usd["date"], y=_usd["cumulative"],
            mode="lines+markers",
            name="USD",
            line=dict(color="#60a5fa"),
            marker=dict(color="#60a5fa", size=8),
            customdata=_usd[["amount"]].values,
            hovertemplate="<b>USD deposit</b><br>Date: %{x|%Y-%m-%d}<br>Amount: $%{customdata[0]:,.2f}<br>Cumulative: $%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        template=get_plotly_template(),
        xaxis_title=None,
        yaxis_title="Cumulative Deposits",
        height=280,
        legend_title_text="Currency",
    )
    st.plotly_chart(fig, width="stretch")

    dep_display = deposits_df[["date", "usd_delta", "ils_delta"]].copy()
    dep_display["date"] = dep_display["date"].dt.date
    dep_display["Amount"] = dep_display.apply(
        lambda r: f"${abs(r['usd_delta']):,.2f}" if r["usd_delta"] != 0 else f"₪{abs(r['ils_delta']):,.2f}",
        axis=1,
    )
    dep_display = dep_display[["date", "Amount"]].sort_values("date", ascending=False).reset_index(drop=True)
    st.dataframe(dep_display, hide_index=True, width="stretch")

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

fx["ILS Amount"] = pd.to_numeric(fx["delta_ils"], errors="coerce").abs()
fx["USD Amount"] = pd.to_numeric(fx["delta_usd"], errors="coerce")
fx["Rate"] = fx["rate_label"]
fx_display = order_table_newest_first_with_chrono_index(fx[["date", "USD Amount", "ILS Amount", "Rate"]].copy(), "date")
st.dataframe(
    fx_display,
    column_config={
        "USD Amount": st.column_config.NumberColumn("USD Amount", format="$%,.2f"),
        "ILS Amount": st.column_config.NumberColumn("ILS Amount", format="₪%,.2f"),
    },
    width="stretch",
    hide_index=True,
)
