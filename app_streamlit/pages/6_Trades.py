from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    inject_global_css,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.services.portfolio import get_holdings_summary

st.set_page_config(page_title="Trades — Trade Lens", layout="wide")
inject_global_css()
st.subheader("Trades")
st.caption("Closed trade analysis and full buy/sell history.")

if "ledger" not in st.session_state:
    st.info("Upload files on the Home page first.")
    st.stop()

ledger = st.session_state["ledger"]
summary = get_holdings_summary(ledger)


# ---------------------------------------------------------------------------
# Trade detail dialog
# ---------------------------------------------------------------------------

@st.dialog("Trade Detail", width="large")
def _show_trade_detail(ct) -> None:
    date_from = pd.to_datetime(ct.date_from).strftime("%b %d, %Y") if pd.notna(ct.date_from) else "?"
    date_to   = pd.to_datetime(ct.date_to).strftime("%b %d, %Y")   if pd.notna(ct.date_to)   else "?"
    buy_rows  = ct.rows[ct.rows["action"] == "Buy"]
    sell_rows = ct.rows[ct.rows["action"] == "Sell"]
    total_qty     = buy_rows["quantity"].sum()
    avg_buy_price = ct.total_buy_cost / total_qty if total_qty > 0 else 0.0
    sell_price    = float(sell_rows.iloc[-1]["price"]) if not sell_rows.empty else 0.0
    pct = (sell_price - avg_buy_price) / avg_buy_price * 100 if avg_buy_price > 0 else 0.0

    pnl_sign  = "+" if ct.realized_pnl >= 0 else "-"
    pct_arrow = "↑" if pct >= 0 else "↓"
    pnl_color = "green" if ct.realized_pnl >= 0 else "red"
    pnl_str   = f"{pnl_sign}${abs(ct.realized_pnl):,.2f} ({pct_arrow}{abs(pct):.1f}%)"

    st.markdown(f"**{ct.symbol}** &nbsp; :{pnl_color}[{pnl_str}]")
    st.caption(f"{date_from} → {date_to}")

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
            "Price":    st.column_config.NumberColumn("Price",    format="$%,.2f"),
            "Amount":   st.column_config.NumberColumn("Amount",   format="$%,.2f"),
        },
        hide_index=True,
        width="stretch",
    )

    fc1, fc2 = st.columns(2)
    fc1.metric("Total Fees", f"${ct.total_fees_usd:,.2f}")
    tax_val = ct.total_estimated_tax
    tax_str = f"-₪{abs(tax_val):,.2f}" if tax_val < 0 else f"₪{tax_val:,.2f}"
    fc2.metric("Est. Tax", tax_str)


# ---------------------------------------------------------------------------
# Closed Trades
# ---------------------------------------------------------------------------

st.subheader("Closed Trades")

if not summary.closed_trades:
    st.info("No closed trades found.")
else:
    # --- Filters ---
    close_years = sorted(
        {pd.to_datetime(ct.date_to).year for ct in summary.closed_trades if pd.notna(ct.date_to)},
        reverse=True,
    )
    all_ct_symbols = sorted({ct.symbol for ct in summary.closed_trades})

    f1, f2 = st.columns(2)
    with f1:
        year_opts = ["All time"] + close_years
        selected_ct_year = st.selectbox("Close year", options=year_opts, index=0, key="ct_year")
    with f2:
        ticker_opts = ["All tickers"] + all_ct_symbols
        selected_ct_ticker = st.selectbox("Ticker", options=ticker_opts, index=0, key="ct_ticker")

    filtered_cts = [
        ct for ct in summary.closed_trades
        if (selected_ct_year == "All time" or pd.to_datetime(ct.date_to).year == int(selected_ct_year))
        and (selected_ct_ticker == "All tickers" or ct.symbol == selected_ct_ticker)
    ]

    if not filtered_cts:
        parts = []
        if selected_ct_year != "All time":
            parts.append(str(selected_ct_year))
        if selected_ct_ticker != "All tickers":
            parts.append(selected_ct_ticker)
        suffix = f" for {' · '.join(parts)}" if parts else ""
        st.info(f"No closed trades{suffix}.")
    else:
        # --- Summary metrics ---
        win_cts  = [ct for ct in filtered_cts if ct.realized_pnl > 0]
        loss_cts = [ct for ct in filtered_cts if ct.realized_pnl < 0]
        pnls     = [ct.realized_pnl for ct in filtered_cts]
        total_pnl = sum(pnls)
        win_rate  = len(win_cts) / len(pnls) * 100 if pnls else 0.0

        avg_win     = sum(ct.realized_pnl for ct in win_cts) / len(win_cts) if win_cts else 0.0
        avg_win_pct = sum(ct.realized_pnl / ct.total_buy_cost * 100 for ct in win_cts if ct.total_buy_cost) / len(win_cts) if win_cts else 0.0
        avg_loss     = sum(ct.realized_pnl for ct in loss_cts) / len(loss_cts) if loss_cts else 0.0
        avg_loss_pct = sum(ct.realized_pnl / ct.total_buy_cost * 100 for ct in loss_cts if ct.total_buy_cost) / len(loss_cts) if loss_cts else 0.0

        pnl_sign = "+" if total_pnl >= 0 else "-"
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Realized P&L", f"{pnl_sign}${abs(total_pnl):,.2f}")
        c2.metric("Win Rate", f"{win_rate:.0f}%  ({len(win_cts)}/{len(pnls)})")
        c3.metric("Avg Win %",  f"+{avg_win_pct:.1f}%" if win_cts else "—")
        c4.metric("Avg Loss %", f"-{abs(avg_loss_pct):.1f}%" if loss_cts else "—")

        # --- P&L over time chart ---
        chart_rows = sorted(
            [{"date": pd.to_datetime(ct.date_to), "pnl": ct.realized_pnl, "ticker": ct.symbol}
             for ct in filtered_cts if pd.notna(ct.date_to)],
            key=lambda r: r["date"],
        )
        chart_df = pd.DataFrame(chart_rows)
        chart_df["cumulative"] = chart_df["pnl"].cumsum()
        chart_df["color"] = chart_df["pnl"].apply(lambda v: "gain" if v >= 0 else "loss")

        _line = alt.Chart(chart_df).mark_line(color="#94a3b8").encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %Y")),
            y=alt.Y("cumulative:Q", title="Cumulative P&L ($)"),
        )
        _dots = alt.Chart(chart_df).mark_circle(size=80).encode(
            x="date:T",
            y="cumulative:Q",
            color=alt.Color(
                "color:N",
                scale=alt.Scale(domain=["gain", "loss"], range=["#22c55e", "#ef4444"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("ticker:N",     title="Ticker"),
                alt.Tooltip("date:T",       title="Close Date", format="%Y-%m-%d"),
                alt.Tooltip("pnl:Q",        title="Trade P&L ($)",      format="$,.2f"),
                alt.Tooltip("cumulative:Q", title="Cumulative P&L ($)", format="$,.2f"),
            ],
        )
        st.altair_chart((_line + _dots).properties(height=280), width="stretch")

        # --- Summary table ---
        summary_rows = []
        for ct in filtered_cts:
            buy_rows  = ct.rows[ct.rows["action"] == "Buy"]
            sell_rows = ct.rows[ct.rows["action"] == "Sell"]
            total_qty     = buy_rows["quantity"].sum()
            avg_buy_price = ct.total_buy_cost / total_qty if total_qty > 0 else 0.0
            sell_price    = float(sell_rows.iloc[-1]["price"]) if not sell_rows.empty else 0.0
            pnl_pct  = ct.realized_pnl / ct.total_buy_cost * 100 if ct.total_buy_cost else 0.0
            date_from = pd.to_datetime(ct.date_from)
            date_to   = pd.to_datetime(ct.date_to)
            hold_days = (date_to - date_from).days if pd.notna(date_from) and pd.notna(date_to) else None
            summary_rows.append({
                "Ticker":      ct.symbol,
                "Close Date":  date_to.date() if pd.notna(date_to) else None,
                "Days Held":   hold_days,
                "Buy Cost":    ct.total_buy_cost,
                "Avg Buy":     avg_buy_price,
                "Sell Price":  sell_price,
                "P&L amount":  ct.realized_pnl,
                "P&L %":       pnl_pct,
            })

        summary_df = pd.DataFrame(summary_rows)

        st.caption("Select a row to view trade detail.")

        styled_df = (
            summary_df.style
            .map(
                lambda v: "color: #22c55e" if v > 0 else ("color: #ef4444" if v < 0 else ""),
                subset=["P&L amount", "P&L %"],
            )
            .format({
                "P&L amount": lambda v: f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}",
                "P&L %":      lambda v: f"{v:+.1f}%",
            })
        )
        event = st.dataframe(
            styled_df,
            column_config={
                "Buy Cost":   st.column_config.NumberColumn("Buy Cost",   format="$%,.2f"),
                "Avg Buy":    st.column_config.NumberColumn("Avg Buy",    format="$%,.2f"),
                "Sell Price": st.column_config.NumberColumn("Sell Price", format="$%,.2f"),
            },
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
        )

        selected_rows = event.selection.rows
        if selected_rows:
            _show_trade_detail(filtered_cts[selected_rows[0]])

st.divider()

# ---------------------------------------------------------------------------
# Trade History
# ---------------------------------------------------------------------------

st.subheader("Trade History")

if not summary.year_options:
    st.info("No buy/sell transactions found.")
else:
    th_col1, th_col2 = st.columns(2)

    with th_col1:
        year_options = ["All time"] + summary.year_options
        selected_year = st.selectbox("Year", options=year_options, index=0, key="trades_year")

    trades = summary.trades.copy()
    if selected_year != "All time":
        dates = pd.to_datetime(trades["date"], errors="coerce")
        trades = trades[dates.dt.year == int(selected_year)].copy()

    all_symbols = sorted(trades["symbol"].dropna().unique().tolist()) if "symbol" in trades.columns else []

    with th_col2:
        ticker_opts = ["All tickers"] + all_symbols
        selected_th_ticker = st.selectbox("Ticker", options=ticker_opts, index=0, key="th_ticker")

    if selected_th_ticker != "All tickers":
        trades = trades[trades["symbol"] == selected_th_ticker].copy()

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
            "Price":    st.column_config.NumberColumn("Price",    format="$%,.2f"),
            "Amount":   st.column_config.NumberColumn("Amount",   format="$%,.2f"),
            "Fees":     st.column_config.NumberColumn("Fees",     format="$%,.2f"),
        },
        width="stretch",
        hide_index=False,
    )
