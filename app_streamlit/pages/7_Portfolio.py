from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    get_plotly_template,
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
        display_df["delta_usd"] = pd.to_numeric(display_df["delta_usd"], errors="coerce").abs()
    if "quantity" in display_df.columns:
        display_df["quantity"] = pd.to_numeric(display_df["quantity"], errors="coerce").abs()

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

    st.dataframe(
        display_df,
        column_config={
            "Quantity": st.column_config.NumberColumn("Quantity", format="%.4g"),
            "Price":    st.column_config.NumberColumn("Price",    format="$%.2f"),
            "Amount":   st.column_config.NumberColumn("Amount",   format="$%.2f"),
            "Fees":     st.column_config.NumberColumn("Fees",     format="$%.2f"),
        },
        width="stretch",
        hide_index=False,
    )

st.divider()

# ---------------------------------------------------------------------------
# Closed Trades
# ---------------------------------------------------------------------------

st.subheader("Closed Trades")

if not summary.closed_trades:
    st.info("No closed trades found.")
else:
    win_cts = [ct for ct in summary.closed_trades if ct.realized_pnl > 0]
    loss_cts = [ct for ct in summary.closed_trades if ct.realized_pnl < 0]
    pnls = [ct.realized_pnl for ct in summary.closed_trades]
    total_pnl = sum(pnls)
    win_rate = len(win_cts) / len(pnls) * 100 if pnls else 0.0

    avg_win = sum(ct.realized_pnl for ct in win_cts) / len(win_cts) if win_cts else 0.0
    avg_win_pct = sum(ct.realized_pnl / ct.total_buy_cost * 100 for ct in win_cts if ct.total_buy_cost) / len(win_cts) if win_cts else 0.0

    avg_loss = sum(ct.realized_pnl for ct in loss_cts) / len(loss_cts) if loss_cts else 0.0
    avg_loss_pct = sum(ct.realized_pnl / ct.total_buy_cost * 100 for ct in loss_cts if ct.total_buy_cost) / len(loss_cts) if loss_cts else 0.0

    pnl_sign = "+" if total_pnl >= 0 else "-"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Realized P&L", f"{pnl_sign}${abs(total_pnl):,.2f}")
    c2.metric("Win Rate", f"{win_rate:.0f}%  ({len(win_cts)}/{len(pnls)})")
    c3.metric("Avg Win", f"+${avg_win:,.2f}  (+{avg_win_pct:.1f}%)" if win_cts else "—")
    c4.metric("Avg Loss", f"-${abs(avg_loss):,.2f}  ({avg_loss_pct:.1f}%)" if loss_cts else "—")

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
            buy_rows = ct.rows[ct.rows["action"] == "Buy"]
            sell_rows = ct.rows[ct.rows["action"] == "Sell"]
            total_qty = buy_rows["quantity"].sum()
            avg_buy_price = ct.total_buy_cost / total_qty if total_qty > 0 else 0.0
            sell_price = float(sell_rows.iloc[-1]["price"]) if not sell_rows.empty else 0.0
            pct = (sell_price - avg_buy_price) / avg_buy_price * 100 if avg_buy_price > 0 else 0.0

            def _price_card(label: str, price: str, sub_label: str, sub_value: str) -> str:
                return f"""<div style="border:1px solid rgba(128,128,128,0.2);border-radius:10px;
                    padding:1rem 1.25rem;box-shadow:0 1px 3px rgba(0,0,0,0.06);margin-bottom:1rem">
                    <p style="font-size:0.8rem;font-weight:500;text-transform:uppercase;
                        letter-spacing:0.03em;opacity:0.7;margin:0 0 0.3rem">{label}</p>
                    <p style="font-size:1.6rem;font-weight:700;margin:0 0 0.4rem">{price}</p>
                    <p style="font-size:0.85rem;opacity:0.6;margin:0">{sub_label}: {sub_value}</p>
                </div>"""

            c1, c2, c3 = st.columns(3)
            c1.markdown(_price_card("Avg Buy Price", f"${avg_buy_price:,.2f}", "Cost basis", f"${ct.total_buy_cost:,.2f}"), unsafe_allow_html=True)
            c2.markdown(_price_card("Sell Price", f"${sell_price:,.2f}", "Proceeds", f"${ct.total_proceeds:,.2f}"), unsafe_allow_html=True)
            c3.metric("Realized P&L", f"{pnl_sign}${abs(ct.realized_pnl):,.2f}", delta=f"{pct:+.1f}%")

            rows = ct.rows.copy()
            rows["date"] = pd.to_datetime(rows["date"], errors="coerce").dt.date
            rows = rows.rename(columns={"action": "Action", "quantity": "Quantity", "price": "Price", "amount": "Amount"})
            st.dataframe(
                rows[["date", "Action", "Quantity", "Price", "Amount"]],
                column_config={
                    "Quantity": st.column_config.NumberColumn("Quantity", format="%.4g"),
                    "Price":    st.column_config.NumberColumn("Price",    format="$%.2f"),
                    "Amount":   st.column_config.NumberColumn("Amount",   format="$%.2f"),
                },
                hide_index=True,
            )

            fc1, fc2 = st.columns(2)
            fc1.metric("Total Fees", f"${ct.total_fees_usd:,.2f}")
            tax_val = ct.total_estimated_tax
            tax_str = f"-₪{abs(tax_val):,.2f}" if tax_val < 0 else f"₪{tax_val:,.2f}"
            fc2.metric("Est. Tax", tax_str)
