from __future__ import annotations

import pandas as pd
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    format_signed_currency,
    inject_global_css,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.services.portfolio import get_holdings_summary

st.set_page_config(page_title="Portfolio — Trade Lens", layout="wide")
inject_global_css()
st.subheader("Portfolio")
st.caption("Your current holdings and full buy/sell history.")

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
    h["Ticker"] = h["symbol"]
    h["Name"] = h["paper_name"]
    h["Qty"] = h["quantity"].map(lambda v: f"{v:,.4f}".rstrip("0").rstrip("."))
    h["Avg Buy Price"] = h["avg_price"].map(lambda v: f"${v:,.2f}" if v else "")
    h["Cost Basis"] = h["total_cost"].map(lambda v: f"${v:,.2f}" if v else "")

    st.dataframe(
        h[["Ticker", "Name", "Qty", "Avg Buy Price", "Cost Basis"]],
        hide_index=True,
        width="stretch",
    )

st.divider()

# ---------------------------------------------------------------------------
# Trade History
# ---------------------------------------------------------------------------

st.subheader("Trade History")

if not summary.year_options:
    st.info("No buy/sell transactions found.")
else:
    year_options = ["All time"] + summary.year_options
    selected_year = st.selectbox("Year", options=year_options, index=0, key="portfolio_year")

    trades = summary.trades.copy()
    if selected_year != "All time":
        dates = pd.to_datetime(trades["date"], errors="coerce")
        trades = trades[dates.dt.year == int(selected_year)].copy()

    display_cols = [
        c for c in ("date", "action_type", "symbol", "quantity", "execution_price", "delta_usd", "fees_usd")
        if c in trades.columns
    ]
    display_df = df_dates_to_date_only(trades[display_cols].copy())

    if "delta_usd" in display_df.columns:
        display_df["delta_usd"] = display_df["delta_usd"].map(
            lambda v: f"${abs(float(v)):,.2f}" if pd.notna(v) else ""
        )
    if "fees_usd" in display_df.columns:
        display_df["fees_usd"] = display_df["fees_usd"].map(lambda v: format_signed_currency(v, "$"))
    if "execution_price" in display_df.columns:
        display_df["execution_price"] = display_df["execution_price"].map(
            lambda v: f"${float(v):,.2f}" if pd.notna(v) and float(v) != 0 else ""
        )
    if "quantity" in display_df.columns:
        display_df["quantity"] = display_df["quantity"].map(
            lambda v: f"{abs(float(v)):,.4f}".rstrip("0").rstrip(".") if pd.notna(v) and float(v) != 0 else ""
        )

    display_df = display_df.rename(columns={
        "action_type": "Action",
        "symbol": "Ticker",
        "quantity": "Quantity",
        "execution_price": "Price",
        "delta_usd": "Amount",
        "fees_usd": "Fees",
    })

    display_df = order_table_newest_first_with_chrono_index(display_df, "date")

    csv_cols = [c for c in ("date", "action_type", "symbol", "quantity", "execution_price", "delta_usd", "fees_usd") if c in trades.columns]
    csv = trades[csv_cols].to_csv(index=False).encode("utf-8")
    label = f"trades_{selected_year}.csv" if selected_year != "All time" else "trades_all.csv"
    st.download_button("Download CSV", data=csv, file_name=label, mime="text/csv")

    st.dataframe(display_df, width="stretch", hide_index=False)

st.divider()

# ---------------------------------------------------------------------------
# Closed Trades
# ---------------------------------------------------------------------------

st.subheader("Closed Trades")

if not summary.closed_trades:
    st.info("No closed trades found.")
else:
    pnls = [ct.realized_pnl for ct in summary.closed_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total_pnl = sum(pnls)
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    turnover = sum(ct.total_proceeds for ct in summary.closed_trades)

    pnl_sign = "+" if total_pnl >= 0 else "-"
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Realized P&L", f"{pnl_sign}${abs(total_pnl):,.2f}")
    c2.metric("Win Rate", f"{win_rate:.0f}%  ({len(wins)}/{len(pnls)})")
    c3.metric("Avg Win", f"+${avg_win:,.2f}" if wins else "—")
    c4.metric("Avg Loss", f"-${abs(avg_loss):,.2f}" if losses else "—")
    c5.metric("Turnover", f"${turnover:,.2f}")

    st.divider()

    for ct in summary.closed_trades:
        date_from = pd.to_datetime(ct.date_from).strftime("%b %d, %Y") if pd.notna(ct.date_from) else "?"
        date_to = pd.to_datetime(ct.date_to).strftime("%b %d, %Y") if pd.notna(ct.date_to) else "?"
        pnl_sign = "+" if ct.realized_pnl >= 0 else "-"
        pnl_color = "green" if ct.realized_pnl >= 0 else "red"

        with st.expander(
            f"**{ct.symbol}** — {date_from} → {date_to} &nbsp;&nbsp; "
            f"P&L: :{pnl_color}[{pnl_sign}${abs(ct.realized_pnl):,.2f}]",
            expanded=False,
        ):
            c1, c2, c3 = st.columns(3)
            c1.metric("Proceeds", f"${ct.total_proceeds:,.2f}")
            c2.metric("Cost Basis", f"${ct.total_buy_cost:,.2f}")
            c3.metric("Realized P&L", f"{pnl_sign}${abs(ct.realized_pnl):,.2f}")

            rows = ct.rows.copy()
            rows["date"] = pd.to_datetime(rows["date"], errors="coerce").dt.date
            rows["quantity"] = rows["quantity"].map(
                lambda v: f"{float(v):,.4f}".rstrip("0").rstrip(".")
            )
            rows["price"] = rows["price"].map(lambda v: f"${float(v):,.2f}" if v else "")
            rows["amount"] = rows["amount"].map(lambda v: f"${float(v):,.2f}")
            rows = rows.rename(columns={
                "action": "Action",
                "quantity": "Quantity",
                "price": "Price",
                "amount": "Amount",
            })
            st.dataframe(rows[["date", "Action", "Quantity", "Price", "Amount"]], hide_index=True)
