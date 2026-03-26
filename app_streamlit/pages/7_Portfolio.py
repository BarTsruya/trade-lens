from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from display_utils import (
    get_plotly_template,
    inject_global_css,
)
from trade_lens.services.balance import get_balance_summary
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
# Live price helpers — cached 5 min
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _get_live_prices(symbols: tuple[str, ...]) -> dict[str, dict]:
    from trade_lens.services.market_data import fetch_live_prices
    return fetch_live_prices(list(symbols))


# ---------------------------------------------------------------------------
# Current Holdings
# ---------------------------------------------------------------------------

st.subheader("Current Holdings")

live: dict = {}  # populated below if there are open positions

if summary.holdings.empty:
    st.info("No open positions found.")
else:
    h = summary.holdings.copy()
    symbols = tuple(h["symbol"].tolist())

    with st.spinner("Fetching live prices…"):
        live = _get_live_prices(symbols)  # noqa: F841 — used in Wealth Summary

    # Build extended holdings table
    h["Current Price"] = h["symbol"].map(lambda s: live.get(s, {}).get("price"))
    h["Mkt Value"] = h.apply(
        lambda r: r["quantity"] * r["Current Price"] if r["Current Price"] is not None else None,
        axis=1,
    )
    h["Unrealized P&L"] = h.apply(
        lambda r: (r["Current Price"] - r["avg_price"]) * r["quantity"]
        if r["Current Price"] is not None else None,
        axis=1,
    )
    h["Unrealized P&L %"] = h.apply(
        lambda r: (r["Current Price"] - r["avg_price"]) / r["avg_price"] * 100
        if r["Current Price"] is not None and r["avg_price"] else None,
        axis=1,
    )
    h["Day Change $"] = h.apply(
        lambda r: live.get(r["symbol"], {}).get("day_change") * r["quantity"]
        if live.get(r["symbol"], {}).get("day_change") is not None else None,
        axis=1,
    )
    h["Day Change %"] = h["symbol"].map(lambda s: live.get(s, {}).get("day_change_pct"))

    # ---------------------------------------------------------------------------
    # Holding detail dialog
    # ---------------------------------------------------------------------------

    @st.dialog("Position Details", width="large")
    def _show_holding_detail(row: pd.Series) -> None:
        pnl      = row["Unrealized P&L"]
        pnl_pct  = row["Unrealized P&L %"]
        pnl_sign = "+" if pd.notna(pnl) and pnl >= 0 else "-"
        pct_arrow = "↑" if pd.notna(pnl_pct) and pnl_pct >= 0 else "↓"
        pnl_color = "green" if pd.notna(pnl) and pnl >= 0 else "red"
        pnl_str = (
            f"{pnl_sign}${abs(pnl):,.2f} ({pct_arrow}{abs(pnl_pct):.1f}%)"
            if pd.notna(pnl) and pd.notna(pnl_pct) else "—"
        )

        st.markdown(f"**{row['symbol']}** &nbsp; :{pnl_color}[{pnl_str}]")
        st.caption(row["paper_name"] or "")

        day_chg     = row["Day Change $"]
        day_chg_pct = row["Day Change %"]

        total_fees = pd.to_numeric(
            summary.trades[summary.trades["symbol"] == row["symbol"]].get("fees_usd", pd.Series(dtype=float)),
            errors="coerce",
        ).fillna(0).sum()

        _dc_d   = f"{day_chg_pct:+.2f}%" if pd.notna(day_chg_pct) else None
        _pnl_d  = f"{pnl_pct:+.2f}%" if pd.notna(pnl_pct) else None

        c1, c2, c3 = st.columns(3)
        # Row 1
        c1.metric("Current Price", f"${row['Current Price']:,.2f}" if pd.notna(row["Current Price"]) else "—")
        c2.metric("Qty",           f"{row['quantity']:.4g}")
        c3.metric("Mkt Value",     f"${row['Mkt Value']:,.2f}" if pd.notna(row["Mkt Value"]) else "—")
        # Row 2
        def _sfmt(v): return (f"+${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}") if pd.notna(v) else "—"
        c1.metric("Day Change",    _sfmt(day_chg), delta=_dc_d)
        c2.markdown(
            f"""<div style="border:1px solid rgba(128,128,128,0.2);border-radius:10px;
                padding:1rem 1.25rem;box-shadow:0 1px 3px rgba(0,0,0,0.06);margin-bottom:1rem">
                <p style="font-size:0.8rem;font-weight:500;text-transform:uppercase;
                    letter-spacing:0.03em;opacity:0.7;margin:0 0 0.3rem">Avg Buy Price</p>
                <p style="font-size:1.6rem;font-weight:700;margin:0 0 0.4rem">${row['avg_price']:,.2f}</p>
                <p style="font-size:0.85rem;opacity:0.6;margin:0">Cost Basis: ${row['total_cost']:,.2f}</p>
            </div>""",
            unsafe_allow_html=True,
        )
        c3.metric("Unrealized P&L", _sfmt(pnl), delta=_pnl_d)

        st.divider()
        st.caption("Transaction History")
        sym_trades = summary.trades[summary.trades["symbol"] == row["symbol"]].copy()
        sym_trades["date"] = pd.to_datetime(sym_trades["date"], errors="coerce").dt.date
        sym_trades["quantity"] = pd.to_numeric(sym_trades["quantity"], errors="coerce").abs()
        sym_trades = sym_trades.rename(columns={
            "action_type":      "Action",
            "quantity":         "Qty",
            "execution_price":  "Price",
            "delta_usd":        "Amount",
            "fees_usd":         "Fees",
        })
        sym_trades["Amount"] = pd.to_numeric(sym_trades.get("Amount"), errors="coerce").abs()
        sym_trades = sym_trades.sort_values("date", ascending=False)
        display_cols = [c for c in ("date", "Action", "Qty", "Price", "Amount") if c in sym_trades.columns]
        st.dataframe(
            sym_trades[display_cols],
            column_config={
                "Qty":    st.column_config.NumberColumn("Qty",    format="%.4g"),
                "Price":  st.column_config.NumberColumn("Price",  format="$%,.2f"),
                "Amount": st.column_config.NumberColumn("Amount", format="$%,.2f"),
            },
            hide_index=True,
            width="stretch",
        )
        num_buy_txns = (sym_trades["Action"] == "buy").sum()
        _mf1, _mf2 = st.columns(2)
        _mf1.metric("Total Fees", f"${total_fees:,.2f}")
        _mf2.metric("Number of Buy Transactions", num_buy_txns)

    # ---------------------------------------------------------------------------
    # Summary table (5 columns) — select a row to open detail
    # ---------------------------------------------------------------------------

    def _fmt_pnl(v):
        if v is None or pd.isna(v):
            return "—"
        return f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}"

    def _fmt_pct(v):
        if v is None or pd.isna(v):
            return "—"
        return f"{v:+.2f}%"

    summary_cols = h[["symbol", "Current Price", "quantity", "avg_price", "total_cost", "Unrealized P&L", "Unrealized P&L %"]].copy()
    summary_cols = summary_cols.rename(columns={
        "symbol":        "Ticker",
        "Current Price": "Current Price",
        "quantity":      "Qty",
        "avg_price":     "Avg Buy Price",
        "total_cost":    "Cost Basis",
    })

    def _color(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        return "color: #22c55e" if v > 0 else ("color: #ef4444" if v < 0 else "")

    styled = (
        summary_cols.style
        .map(_color, subset=["Unrealized P&L", "Unrealized P&L %"])
        .format({
            "Current Price":    lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
            "Qty":              lambda v: f"{v:.4g}" if pd.notna(v) else "—",
            "Avg Buy Price":    lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
            "Cost Basis":       lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
            "Unrealized P&L":   _fmt_pnl,
            "Unrealized P&L %": _fmt_pct,
        })
    )

    _total_day_chg  = h["Day Change $"].dropna().sum()
    _total_unrealized = h["Unrealized P&L"].dropna().sum()
    _total_unreal_pct = (
        _total_unrealized / h["total_cost"].sum() * 100
        if h["total_cost"].sum() != 0 else None
    )
    _total_dc_pct = (
        _total_day_chg / (h["Mkt Value"].dropna().sum() - _total_day_chg) * 100
        if (h["Mkt Value"].dropna().sum() - _total_day_chg) != 0 else None
    )
    _sm1, _sm2 = st.columns(2)
    def _signed_usd(v: float) -> str:
        return f"+${v:,.2f}" if v >= 0 else f"-${abs(v):,.2f}"

    _sm1.metric(
        "Unrealized P&L",
        _signed_usd(_total_unrealized),
        delta=f"{_total_unreal_pct:+.2f}%" if _total_unreal_pct is not None else None,
    )
    _sm2.metric(
        "Day Change",
        _signed_usd(_total_day_chg),
        delta=f"{_total_dc_pct:+.2f}%" if _total_dc_pct is not None else None,
    )

    st.markdown("🖱️ **Click any row** for full position details.")
    event = st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
    )

    selected = event.selection.rows
    if selected:
        _show_holding_detail(h.iloc[selected[0]])

    # Assign consistent colors per ticker for both pie charts
    _palette = px.colors.qualitative.Plotly
    _color_map = {sym: _palette[i % len(_palette)] for i, sym in enumerate(h["symbol"].tolist())}

    # Market value: use live price where available, fall back to cost basis
    h["_mkt_val_plot"] = h.apply(
        lambda r: r["Mkt Value"] if pd.notna(r["Mkt Value"]) else r["total_cost"], axis=1
    )

    pie_c1, pie_c2 = st.columns(2)

    _symbol_order = {"symbol": h["symbol"].tolist()}

    _total_cost_basis = h["total_cost"].sum()
    _total_mkt_value  = h["_mkt_val_plot"].sum()

    with pie_c1:
        st.metric("Total Cost Basis", f"${_total_cost_basis:,.2f}")
        fig_cost = px.pie(
            h, values="total_cost", names="symbol", hole=0.4,
            template=get_plotly_template(),
            color="symbol", color_discrete_map=_color_map,
            category_orders=_symbol_order,
        )
        fig_cost.update_traces(textinfo="label+percent", hovertemplate="%{label}<br>$%{value:,.2f}<extra></extra>")
        fig_cost.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_cost, width="stretch")

    with pie_c2:
        st.metric("Total Market Value", f"${_total_mkt_value:,.2f}")
        fig_mkt = px.pie(
            h, values="_mkt_val_plot", names="symbol", hole=0.4,
            template=get_plotly_template(),
            color="symbol", color_discrete_map=_color_map,
            category_orders=_symbol_order,
        )
        fig_mkt.update_traces(textinfo="label+percent", hovertemplate="%{label}<br>$%{value:,.2f}<extra></extra>")
        fig_mkt.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_mkt, width="stretch")


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Performance")
st.caption("Portfolio net asset value over time, return metrics, and wealth breakdown.")

# Need balance timeline for cash positions and cash flows
balance = get_balance_summary(ledger)

if balance.timeline.empty:
    st.info("No balance data found — upload files on the Home page.")
    st.stop()


@st.cache_data(ttl=3600)
def _build_performance(
    trade_key: str,  # cache-busting key derived from ledger hash
    symbols: tuple[str, ...],
    start_str: str,
    end_str: str,
    balance_timeline_json: str,
    trades_json: str,
):
    """Heavy computation cached for 1 hour."""
    from trade_lens.services.market_data import (
        fetch_historical_prices,
        fetch_us_cpi,
        fetch_usdils_history,
    )
    from trade_lens.services.nav import compute_nav_timeline, compute_real_nav

    import io
    bt = pd.read_json(io.StringIO(balance_timeline_json), convert_dates=["date"])
    tr = pd.read_json(io.StringIO(trades_json), convert_dates=["date"])

    price_hist = fetch_historical_prices(list(symbols), start_str, end_str)
    usdils = fetch_usdils_history(start_str, end_str)
    cpi = fetch_us_cpi(start_str)

    nav_df = compute_nav_timeline(tr, bt, price_hist, usdils)
    real_nav = compute_real_nav(nav_df, cpi)

    return nav_df, real_nav


if summary.trades.empty or summary.holdings.empty and not summary.closed_trades:
    st.info("No trade data to compute performance.")
    st.stop()

all_symbols = tuple(summary.trades["symbol"].dropna().unique().tolist())

_bt = balance.timeline.copy()
_bt["date"] = pd.to_datetime(_bt["date"], errors="coerce")

_start = _bt["date"].dropna().min()
_end = pd.Timestamp(date.today())

if pd.isna(_start):
    st.info("No dated transactions found.")
    st.stop()

start_str = _start.strftime("%Y-%m-%d")
end_str = _end.strftime("%Y-%m-%d")

# Stable cache key from a lightweight ledger hash
_cache_key = str(hash(tuple(sorted(str(v) for v in ledger.iloc[:, 0].tolist()[:20]))))

with st.spinner("Loading market data for performance analysis…"):
    try:
        nav_df, real_nav = _build_performance(
            _cache_key,
            all_symbols,
            start_str,
            end_str,
            _bt[["date", "usd_balance", "ils_balance", "action_type", "usd_delta", "ils_delta"]].to_json(date_format="iso"),
            summary.trades[["date", "symbol", "action_type", "quantity", "execution_price"]].to_json(date_format="iso"),
        )
    except Exception as e:
        st.error(f"Performance data unavailable: {e}")
        st.stop()

if nav_df.empty or nav_df["nav"].isna().all():
    st.warning("Could not compute NAV — check that tickers are valid Yahoo Finance symbols.")
    st.stop()

# ---------------------------------------------------------------------------
# Return metrics
# ---------------------------------------------------------------------------

# Total deposited in USD
deposits = _bt[_bt["action_type"] == "cash_deposit"].copy()
deposits["usd_delta"] = pd.to_numeric(deposits.get("usd_delta", 0), errors="coerce").fillna(0.0)
total_deposited_usd = deposits["usd_delta"].sum()

first_nav = float(nav_df["nav"].dropna().iloc[0]) if not nav_df["nav"].dropna().empty else 0.0
final_nav = float(nav_df["nav"].dropna().iloc[-1]) if not nav_df["nav"].dropna().empty else 0.0

nav_dates = pd.to_datetime(nav_df["date"])
years_held = (nav_dates.iloc[-1] - nav_dates.iloc[0]).days / 365.25

total_return_pct = (final_nav - total_deposited_usd) / total_deposited_usd * 100 if total_deposited_usd > 0 else 0.0
cagr_pct = ((final_nav / total_deposited_usd) ** (1 / years_held) - 1) * 100 if total_deposited_usd > 0 and years_held > 0 else 0.0

# TWR
from trade_lens.services.nav import compute_twr, compute_xirr

_cash_flows_for_twr = deposits[["date", "usd_delta"]].rename(columns={"usd_delta": "amount"}).copy()
_cash_flows_for_twr["date"] = pd.to_datetime(_cash_flows_for_twr["date"])
twr = compute_twr(nav_df, _cash_flows_for_twr) * 100  # as %

# XIRR
_xirr_flows = [(row["date"], -row["amount"]) for _, row in _cash_flows_for_twr.iterrows()]
xirr_val = compute_xirr(_xirr_flows, final_nav, date.today())
xirr_pct = xirr_val * 100 if xirr_val is not None else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Return",     f"{total_return_pct:+.1f}%")
c2.metric("CAGR (annualized)", f"{cagr_pct:+.1f}%")
c3.metric("TWR",              f"{twr:+.1f}%")
c4.metric("XIRR",             f"{xirr_pct:+.1f}%" if xirr_pct is not None else "—")

# Nominal vs real
if real_nav is not None and not real_nav.empty:
    real_final = float(real_nav.dropna().iloc[-1])
    real_return_pct = (real_final - total_deposited_usd) / total_deposited_usd * 100 if total_deposited_usd > 0 else 0.0
    nm1, nm2 = st.columns(2)
    nm1.metric("Nominal Total Return", f"{total_return_pct:+.1f}%")
    nm2.metric("Real Return (US CPI adjusted)", f"{real_return_pct:+.1f}%")

# ---------------------------------------------------------------------------
# NAV chart
# ---------------------------------------------------------------------------

resolution = st.selectbox("Resolution", ["Daily", "Weekly", "Monthly"], index=0, key="nav_resolution")

chart_nav = nav_df.copy()
chart_nav["date"] = pd.to_datetime(chart_nav["date"])
chart_nav = chart_nav.set_index("date")

if resolution == "Weekly":
    chart_nav = chart_nav.resample("W").last()
elif resolution == "Monthly":
    chart_nav = chart_nav.resample("ME").last()

chart_nav = chart_nav.reset_index()

fig = go.Figure()

# Nominal NAV
fig.add_trace(go.Scatter(
    x=chart_nav["date"],
    y=chart_nav["nav"],
    mode="lines",
    name="NAV (nominal)",
    line=dict(color="#60a5fa", width=2),
    hovertemplate="<b>NAV</b><br>%{x|%Y-%m-%d}<br>$%{y:,.0f}<extra></extra>",
))

# Real NAV
if real_nav is not None and not real_nav.empty:
    _real = real_nav.copy()
    _real.index = pd.to_datetime(_real.index)
    if resolution == "Weekly":
        _real = _real.resample("W").last()
    elif resolution == "Monthly":
        _real = _real.resample("ME").last()
    fig.add_trace(go.Scatter(
        x=_real.index,
        y=_real.values,
        mode="lines",
        name="NAV (real, CPI-adjusted)",
        line=dict(color="#fb923c", width=2, dash="dash"),
        hovertemplate="<b>Real NAV</b><br>%{x|%Y-%m-%d}<br>$%{y:,.0f}<extra></extra>",
    ))

# Deposit markers
_dep_markers = _cash_flows_for_twr[_cash_flows_for_twr["amount"] > 0].copy()
if not _dep_markers.empty:
    # Find NAV value on deposit dates for y-position
    nav_indexed = chart_nav.set_index("date")["nav"]

    def _closest_nav(d):
        candidates = nav_indexed[nav_indexed.index <= d]
        return float(candidates.iloc[-1]) if not candidates.empty else float(nav_indexed.iloc[0])

    _dep_markers["nav_y"] = _dep_markers["date"].apply(_closest_nav)
    fig.add_trace(go.Scatter(
        x=_dep_markers["date"],
        y=_dep_markers["nav_y"],
        mode="markers",
        name="Deposit",
        marker=dict(symbol="triangle-up", color="#22c55e", size=12),
        customdata=_dep_markers[["amount"]].values,
        hovertemplate="<b>Deposit</b><br>%{x|%Y-%m-%d}<br>$%{customdata[0]:,.2f}<extra></extra>",
    ))

fig.update_layout(
    template=get_plotly_template(),
    height=350,
    xaxis_title=None,
    yaxis_title="Portfolio NAV ($)",
    legend=dict(orientation="h", y=-0.15),
    margin=dict(l=60, r=20, t=20, b=60),
)
st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Wealth Summary
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Wealth Summary")
st.caption("Where your money is: deposits vs gains vs cash.")

# Realized gains from closed trades
total_realized = sum(ct.realized_pnl for ct in summary.closed_trades)

# Unrealized gains: market value of open positions - cost basis
mkt_value_total = 0.0
cost_basis_total = 0.0
if not summary.holdings.empty and live:
    for _, row in summary.holdings.iterrows():
        sym = row["symbol"]
        price_now = (live or {}).get(sym, {}).get("price")
        cost_basis_total += float(row["total_cost"])
        if price_now is not None:
            mkt_value_total += float(row["quantity"]) * float(price_now)
        else:
            mkt_value_total += float(row["total_cost"])  # fallback: cost basis

unrealized = mkt_value_total - cost_basis_total

# Current cash balances
_last_bal = balance.timeline.iloc[-1]
current_usd_cash = float(pd.to_numeric(_last_bal.get("usd_balance", 0), errors="coerce") or 0)
current_ils_cash = float(pd.to_numeric(_last_bal.get("ils_balance", 0), errors="coerce") or 0)

# ILS deposits
ils_deposits = _bt[_bt["action_type"] == "cash_deposit"].copy()
ils_deposits["ils_delta"] = pd.to_numeric(ils_deposits.get("ils_delta", 0), errors="coerce").fillna(0.0)
total_deposited_ils = ils_deposits["ils_delta"].sum()

summary_rows = [
    {"Metric": "Total Deposited (USD)",    "Value": f"${total_deposited_usd:,.2f}"},
    {"Metric": "Total Deposited (ILS)",    "Value": f"₪{total_deposited_ils:,.2f}"},
    {"Metric": "Realized Gains",           "Value": f"${total_realized:+,.2f}"},
    {"Metric": "Unrealized Gains",         "Value": f"${unrealized:+,.2f}"},
    {"Metric": "Current Cash (USD)",       "Value": f"${current_usd_cash:,.2f}"},
    {"Metric": "Current Cash (ILS)",       "Value": f"₪{current_ils_cash:,.2f}"},
    {"Metric": "Current Holdings Value",   "Value": f"${mkt_value_total:,.2f}"},
    {"Metric": "Total Total Market Value",    "Value": f"${final_nav:,.2f}"},
]

summary_df = pd.DataFrame(summary_rows)
st.dataframe(summary_df, hide_index=True, width="stretch")
