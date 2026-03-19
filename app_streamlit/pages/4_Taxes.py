from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    format_signed_currency,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.brokers.ibi import RawActionType
from trade_lens.services.taxes import get_tax_summary

st.set_page_config(page_title="Taxes — Trade Lens", layout="wide")
st.subheader("Taxes")

if "ledger" not in st.session_state:
    st.info("Upload files on the Home page first.")
    st.stop()

ledger = st.session_state["ledger"]
required_cols = {"action_type", "date", "delta_ils", "delta_usd", "paper_name", "quantity"}
missing = sorted(required_cols - set(ledger.columns))
if missing:
    st.warning("Cannot build taxes table — missing columns: " + ", ".join(missing))
    st.stop()

preview = get_tax_summary(ledger)
if not preview.year_options:
    st.info("No tax-related actions found.")
    st.stop()

selected_year = st.selectbox("Year", options=preview.year_options, index=0, key="taxes_year")
tax = get_tax_summary(ledger, selected_year) if selected_year != preview.selected_year else preview

# ---------------------------------------------------------------------------
# Capital Gains chart
# ---------------------------------------------------------------------------

st.subheader("Capital Gain Taxes")

if tax.capital_gains_by_year.empty:
    st.info("No capital gain tax actions found.")
else:
    chart = tax.monthly_chart
    month_labels = chart["month"].dt.strftime("%b").tolist()
    show_shield = st.checkbox("Show Tax Shield", value=True)

    n = len(chart)
    centers = list(range(n))
    slot_w = 0.8

    p_off, p_w = [], []
    pay_off, pay_w = [], []
    cr_off, cr_w = [], []
    sh_off, sh_w = [], []

    for i in range(n):
        slots = []
        if chart["payable_amount"].iloc[i] > 0:            slots.append("payable")
        if chart["payment_amount"].iloc[i] > 0:            slots.append("payment")
        if chart["credit_amount"].iloc[i] > 0:             slots.append("credit")
        if show_shield and chart["pre_settlement_shield"].iloc[i] > 0: slots.append("shield")

        sw = slot_w / len(slots) if slots else slot_w
        pos = centers[i] - slot_w / 2
        slot_pos: dict = {}
        for s in slots:
            slot_pos[s] = (pos - centers[i], sw)
            pos += sw

        def _get(name: str) -> tuple:
            return slot_pos.get(name, (0.0, 0.0))

        o, w = _get("payable");  p_off.append(o);   p_w.append(w)
        o, w = _get("payment"); pay_off.append(o); pay_w.append(w)
        o, w = _get("credit");   cr_off.append(o);  cr_w.append(w)
        o, w = _get("shield");   sh_off.append(o);  sh_w.append(w)

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Payable", x=centers, y=chart["payable_amount"], offset=p_off,   width=p_w,   marker_color="gray",      opacity=0.6))
    fig.add_trace(go.Bar(name="Payment", x=centers, y=chart["payment_amount"], offset=pay_off, width=pay_w, marker_color="crimson"))
    fig.add_trace(go.Bar(name="Credit",  x=centers, y=chart["credit_amount"],  offset=cr_off,  width=cr_w,  marker_color="seagreen"))
    if show_shield:
        fig.add_trace(go.Bar(name="Shield Used",    x=centers, y=chart["shield_used_bar"],    base=[0.0]*n, offset=sh_off, width=sh_w, marker_color="darkorange"))
        fig.add_trace(go.Bar(name="Shield Balance", x=centers, y=chart["shield_balance_bar"], base=chart["shield_used_bar"].tolist(), offset=sh_off, width=sh_w, marker_color="goldenrod"))
    fig.update_layout(
        barmode="overlay",
        xaxis=dict(tickmode="array", tickvals=centers, ticktext=month_labels),
        title=f"Capital Gains Tax — Monthly Breakdown [{selected_year}]",
        xaxis_title="Month", yaxis_title="Amount (₪)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch")

    # Summary metrics
    st.subheader("Summary")
    s = tax.summary
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Tax Payables",              f"₪{s['payable_sum']:,.2f}")
    c2.metric("Total Tax Credits",               f"₪{s['credit_sum']:,.2f}")
    c3.metric("Annual Tax (payments − credits)", f"₪{s['annual_tax']:,.2f}")
    c4.metric("Remaining Tax Shield",            f"₪{s['remaining_shield']:,.2f}")

    # Transactions table
    display_df = tax.capital_gains_by_year.drop(columns=["month"], errors="ignore").copy()
    for col in ("tax_shield_state", "tax_payable_state", "total_annual_tax"):
        if col in display_df.columns:
            display_df[col] = display_df[col].map(lambda v: format_signed_currency(v, "₪"))

    display_df = order_table_newest_first_with_chrono_index(display_df, "date")
    if "_display_idx" in display_df.columns:
        display_df = display_df.drop(columns=["_display_idx"])
    annual_end_idx = (
        set(display_df.index[display_df["_annual_year_end"].fillna(False)].tolist())
        if "_annual_year_end" in display_df.columns else set()
    )
    display_df = display_df.drop(columns=["_annual_year_end", "amount_value"], errors="ignore")
    display_df = df_dates_to_date_only(display_df)

    def _style(row: pd.Series) -> list[str]:
        styles = [""] * len(row)
        amt_i = list(row.index).index("amount") if "amount" in row.index else -1
        ann_i = list(row.index).index("total_annual_tax") if "total_annual_tax" in row.index else -1
        if amt_i >= 0:
            at = str(row.get("action_type", "") or "")
            if at == RawActionType.TAX_CREDIT.value:
                styles[amt_i] = "color: #2e7d32; font-weight: 600;"
            elif at == RawActionType.TAX_PAYMENT.value:
                styles[amt_i] = "color: #c62828; font-weight: 600;"
        if ann_i >= 0 and row.name in annual_end_idx:
            styles[ann_i] = "font-weight: 700;"
        return styles

    st.dataframe(display_df.style.apply(_style, axis=1), width="stretch", hide_index=False)

# ---------------------------------------------------------------------------
# Dividend Taxes
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Dividend Taxes")

if tax.dividend_tax_by_year.empty:
    st.info("No dividend tax rows found for this year.")
else:
    div_months = tax.dividend_tax_monthly.copy()
    div_months["month_label"] = div_months["month"].dt.strftime("%b")
    month_order = pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS").strftime("%b").tolist()

    div_fig = px.bar(
        div_months, x="month_label", y="dividend_tax_amount",
        title=f"Monthly Dividend Tax [{selected_year}]",
        labels={"month_label": "Month", "dividend_tax_amount": "Amount"},
        category_orders={"month_label": month_order},
    )
    div_fig.update_traces(marker_color="crimson", width=0.2)
    div_fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)")
    st.plotly_chart(div_fig, width="stretch")

    if not tax.dividend_tax_by_ticker.empty:
        by_ticker = tax.dividend_tax_by_ticker.copy()
        by_ticker["total"] = by_ticker["amount_currency"] + by_ticker["amount_value"].map(lambda v: f"{v:,.2f}")
        ticker_summary = by_ticker[["ticker", "total"]].rename(columns={"ticker": "Ticker", "total": "Tax Paid"})

        metric_cols = st.columns(max(1, len(tax.dividend_tax_totals)))
        for col, (cur, val) in zip(metric_cols, tax.dividend_tax_totals.items()):
            col.metric(f"Total Dividend Tax ({cur})", f"{cur}{val:,.2f}")
        st.dataframe(ticker_summary, hide_index=True)

    st.markdown("**Transactions**")
    tx_cols = [c for c in ("date", "paper_name", "amount") if c in tax.dividend_tax_by_year.columns]
    tx_df = df_dates_to_date_only(tax.dividend_tax_by_year[tx_cols].copy())
    if "paper_name" in tx_df.columns:
        tx_df["paper_name"] = tx_df["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
        tx_df = tx_df.rename(columns={"paper_name": "Ticker"})
    st.dataframe(tx_df, width="stretch", hide_index=True)
