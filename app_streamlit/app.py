from __future__ import annotations

import re
from typing import Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    format_signed_currency,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.analytics.balance import balance_timeline_actions
from trade_lens.analytics.cashflow import (
    build_maintenance_fees_ledger,
    build_trading_fees_ledger,
    monthly_fees_breakdown,
)
from trade_lens.analytics.ledger import (
    filter_ledger,
    ledger_action_options,
    ledger_date_bounds,
    ledger_symbol_options,
)
from trade_lens.analytics.dividends import (
    build_dividend_deposit_ledger,
    build_dividend_tax_ledger,
    build_monthly_amount_series,
    dividend_deposit_year_options,
)
from trade_lens.analytics.taxes import (
    build_capital_gains_monthly_chart_df,
    build_capital_gains_summary,
    build_tax_ledger,
    filter_tax_rows_by_year,
    tax_year_options,
)
from trade_lens.brokers.ibi import RawActionType
from trade_lens.pipeline.loader import count_unknown_action_rows, get_unknown_action_details, load_and_normalize_many


st.set_page_config(page_title="Trade Lens", layout="wide")
st.title("Trade Lens - IBI Actions Explorer")
st.caption("Upload an IBI actions .xlsx export to inspect ledger, cashflow, fees, and symbol activity.")


@st.cache_data(show_spinner=False)
def _cached_load(file_payloads: Tuple[Tuple[str, bytes], ...]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return load_and_normalize_many(file_payloads)


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

uploaded_files = st.file_uploader("Upload IBI actions export", type=["xlsx"], accept_multiple_files=True)

if not uploaded_files:
    st.info("Upload one or more .xlsx files to begin.")
    st.stop()

try:
    payloads = tuple((f.name, f.getvalue()) for f in uploaded_files)
    raw, ledger = _cached_load(payloads)
except Exception as exc:
    st.error("Could not load these files. Make sure each is a valid IBI actions .xlsx export.")
    st.exception(exc)
    st.stop()

unknown_action_rows = count_unknown_action_rows(ledger)
if unknown_action_rows > 0:
    st.warning(
        f"Loaded {len(uploaded_files):,} file(s): {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows. "
        f"Detected {unknown_action_rows:,} row(s) with unrecognized action types."
    )
    with st.expander(f"Show unrecognized rows ({unknown_action_rows:,})", expanded=False):
        unknown_details = get_unknown_action_details(raw, ledger)
        if not unknown_details.empty:
            display_details = unknown_details.copy()
            if "date" in display_details.columns:
                display_details["date"] = pd.to_datetime(display_details["date"], errors="coerce").dt.date
            if len(uploaded_files) == 1 and "source_file" in display_details.columns:
                display_details = display_details.drop(columns=["source_file"])
            for usd_col in ("usd_amount",):
                if usd_col in display_details.columns:
                    display_details[usd_col] = display_details[usd_col].map(lambda v: format_signed_currency(v, "$"))
            if "ils_amount" in display_details.columns:
                display_details["ils_amount"] = display_details["ils_amount"].map(lambda v: format_signed_currency(v, "₪"))
            st.caption("'raw_action_type' is the original unrecognized string from the broker export. Add it to HEBREW_ACTION_TYPE_MAP in ibi.py to resolve it.")
            st.dataframe(display_details, hide_index=True)
else:
    st.success(
        f"Loaded {len(uploaded_files):,} file(s): {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows."
    )

tab_ledger, tab_balance, tab_fees, tab_taxes, tab_dividend = st.tabs(["Ledger", "Balance", "Fees", "Taxes", "Dividends"])

# ---------------------------------------------------------------------------
# Ledger tab
# ---------------------------------------------------------------------------

with tab_ledger:
    st.subheader("Ledger Preview")

    min_date, max_date = ledger_date_bounds(ledger)
    default_date_range = (min_date, max_date)
    action_options = ledger_action_options(ledger)
    symbol_options = ledger_symbol_options(ledger)

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        if st.button("Full range", key="ledger_filter_full_range") and all(default_date_range):
            st.session_state["ledger_filter_date_range"] = default_date_range
            st.rerun()
        st.markdown("Date range")
        selected_date_range = st.date_input(
            "Date range",
            value=default_date_range if all(default_date_range) else (),
            key="ledger_filter_date_range",
            label_visibility="collapsed",
        )
    with filter_col2:
        if st.button("All types", key="ledger_filter_all_types"):
            for v in action_options:
                st.session_state[f"ledger_filter_action_visible_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"] = False
            st.rerun()
        st.markdown("Action type")
        selected_action_types: list[str] = []
        with st.expander("Select action types", expanded=False):
            for v in action_options:
                key = f"ledger_filter_action_visible_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"
                if st.checkbox(v, value=False, key=key):
                    selected_action_types.append(v)
    with filter_col3:
        if st.button("All symbols", key="ledger_filter_all_symbols"):
            for v in symbol_options:
                st.session_state[f"ledger_filter_symbol_visible_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"] = False
            st.rerun()
        st.markdown("Symbol")
        selected_symbols: list[str] = []
        with st.expander("Select symbols", expanded=False):
            for v in symbol_options:
                key = f"ledger_filter_symbol_visible_{re.sub(r'[^a-zA-Z0-9]+', '_', v).strip('_').lower()}"
                if st.checkbox(v, value=False, key=key):
                    selected_symbols.append(v)

    active_date_range = (
        (selected_date_range[0], selected_date_range[1])
        if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2 and all(selected_date_range)
        else None
    )
    filtered_ledger = filter_ledger(
        ledger,
        date_range=active_date_range,
        action_types=selected_action_types or None,
        symbols=selected_symbols or None,
    )

    f_dates = pd.to_datetime(filtered_ledger.get("date"), errors="coerce")
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    stat_col1.metric("Rows (filtered)", f"{len(filtered_ledger):,}")
    stat_col2.metric("Date From", "N/A" if f_dates.empty or f_dates.isna().all() else str(f_dates.min().date()))
    stat_col3.metric("Date To", "N/A" if f_dates.empty or f_dates.isna().all() else str(f_dates.max().date()))

    ledger_display_df = df_dates_to_date_only(filtered_ledger)
    for drop_col in ("execution_price", "ledger_row_id", "_source_order", "_date_desc", "expected_ils_balance"):
        if drop_col in ledger_display_df.columns:
            ledger_display_df = ledger_display_df.drop(columns=[drop_col])
    for usd_col in ("delta_usd", "fees_usd"):
        if usd_col in ledger_display_df.columns:
            ledger_display_df[usd_col] = ledger_display_df[usd_col].map(lambda v: format_signed_currency(v, "$"))
    if "delta_ils" in ledger_display_df.columns:
        ledger_display_df["delta_ils"] = ledger_display_df["delta_ils"].map(lambda v: format_signed_currency(v, "₪"))
    if "estimated_capital_gains_tax" in ledger_display_df.columns:
        ledger_display_df["estimated_capital_gains_tax"] = ledger_display_df["estimated_capital_gains_tax"].map(
            lambda v: format_signed_currency(v, "₪")
        )

    filtered_csv = (
        filtered_ledger.drop(
            columns=["_source_order", "_date_desc", "_display_idx", "expected_ils_balance", "ledger_row_id"],
            errors="ignore",
        )
        .to_csv(index=False)
        .encode("utf-8")
    )
    st.download_button("Download filtered ledger (CSV)", data=filtered_csv, file_name="ledger_filtered.csv", mime="text/csv")

    ledger_display_df = order_table_newest_first_with_chrono_index(ledger_display_df, "date")
    if "_display_idx" in ledger_display_df.columns:
        ledger_display_df = ledger_display_df.drop(columns=["_display_idx"])
    st.dataframe(ledger_display_df, width="stretch", hide_index=False)

# ---------------------------------------------------------------------------
# Balance tab
# ---------------------------------------------------------------------------

with tab_balance:
    st.subheader("Balance")
    st.caption("Action-level cash timeline with running balances based on cash-affecting rows.")
    st.caption("Rows are displayed newest first. Index labels are chronological (1 = oldest).")

    balance_df = balance_timeline_actions(ledger)
    if not balance_df.empty:
        balance_df["_display_idx"] = pd.to_numeric(ledger.get("_display_idx"), errors="coerce").reindex(balance_df.index)

    if balance_df.empty:
        st.warning("No balance actions found for these action types.")
    else:
        balance_display_df = df_dates_to_date_only(balance_df)
        balance_table_df = balance_display_df.drop(columns=["expected_ils_balance"], errors="ignore").copy()
        for usd_col in ("usd_delta", "fees_usd", "usd_balance"):
            if usd_col in balance_table_df.columns:
                balance_table_df[usd_col] = balance_table_df[usd_col].map(lambda v: format_signed_currency(v, "$"))
        for ils_col in ("ils_delta", "ils_balance"):
            if ils_col in balance_table_df.columns:
                balance_table_df[ils_col] = balance_table_df[ils_col].map(lambda v: format_signed_currency(v, "₪"))
        balance_table_df = order_table_newest_first_with_chrono_index(balance_table_df, "date")
        if "_display_idx" in balance_table_df.columns:
            balance_table_df = balance_table_df.drop(columns=["_display_idx"])
        st.dataframe(balance_table_df, width="stretch", hide_index=False)

        balance_long = balance_display_df.melt(
            id_vars=["date"], value_vars=["usd_balance", "ils_balance"],
            var_name="balance_type", value_name="balance",
        )
        st.plotly_chart(
            px.line(balance_long, x="date", y="balance", color="balance_type",
                    title="Running USD and ILS Balances",
                    labels={"date": "Day", "balance": "Balance", "balance_type": "Series"}),
            width="stretch",
        )

# ---------------------------------------------------------------------------
# Fees tab
# ---------------------------------------------------------------------------

with tab_fees:

    trading_fees_all_df = build_trading_fees_ledger(ledger)
    maintenance_fees_all_df = build_maintenance_fees_ledger(ledger)

    _fees_years = sorted(
        set(dividend_deposit_year_options(trading_fees_all_df))
        | set(dividend_deposit_year_options(maintenance_fees_all_df)),
        reverse=True,
    )

    if not _fees_years:
        st.info("No fees data available.")
    else:
        selected_fees_year = st.selectbox("Year", options=_fees_years, index=0, key="fees_year_filter")

    # ---------------------------------------------------------------------------
    # Section 1: Trading Fees (USD)
    # ---------------------------------------------------------------------------
    st.subheader("Trading Fees")

    if not _fees_years:
        st.info("No trading fee data available.")
    else:
        trading_fees_y = filter_tax_rows_by_year(trading_fees_all_df, selected_fees_year)

        _trade_months = build_monthly_amount_series(
            trading_fees_y,
            selected_year=selected_fees_year,
            amount_column="amount_value",
            output_column="fee_amount",
        )
        _trade_months["month_label"] = _trade_months["month"].dt.strftime("%b")
        _trade_month_order = pd.date_range(
            start=f"{selected_fees_year}-01-01", periods=12, freq="MS"
        ).strftime("%b").tolist()
        _trade_fig = px.bar(
            _trade_months,
            x="month_label",
            y="fee_amount",
            title=f"Monthly Trading Fees [{selected_fees_year}]",
            labels={"month_label": "Month", "fee_amount": "Amount"},
            category_orders={"month_label": _trade_month_order},
        )
        _trade_fig.update_traces(marker_color="indianred", width=0.2)
        _trade_fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)")
        st.plotly_chart(_trade_fig, width="stretch")

        if not trading_fees_y.empty:
            _trade_total = trading_fees_y["amount_value"].sum()
            st.metric("Total Trading Fees", f"${_trade_total:,.2f}")

            _trade_ticker_col = trading_fees_y["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
            _trade_by_ticker = (
                trading_fees_y.assign(Ticker=_trade_ticker_col)
                .groupby("Ticker")["amount_value"]
                .sum()
                .reset_index()
                .sort_values("amount_value", ascending=False)
            )
            _trade_by_ticker["Amount"] = "$" + _trade_by_ticker["amount_value"].map(lambda v: f"{v:,.2f}")
            st.dataframe(_trade_by_ticker[["Ticker", "Amount"]], hide_index=True)

            st.markdown("**Transactions**")
            _trade_display = df_dates_to_date_only(trading_fees_y[["date", "paper_name", "amount"]].copy())
            _trade_display = order_table_newest_first_with_chrono_index(_trade_display, "date")
            if "paper_name" in _trade_display.columns:
                _trade_display["paper_name"] = _trade_display["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
                _trade_display = _trade_display.rename(columns={"paper_name": "Ticker", "amount": "Amount"})
            st.dataframe(_trade_display, width="stretch", hide_index=True)

    st.divider()

    # ---------------------------------------------------------------------------
    # Section 2: Account Maintenance Fees (ILS)
    # ---------------------------------------------------------------------------
    st.subheader("Account Maintenance Fees")

    if not _fees_years:
        st.info("No account maintenance fee data available.")
    else:
        maintenance_fees_y = filter_tax_rows_by_year(maintenance_fees_all_df, selected_fees_year)

        _maint_months = build_monthly_amount_series(
            maintenance_fees_y,
            selected_year=selected_fees_year,
            amount_column="amount_value",
            output_column="fee_amount",
        )
        _maint_months["month_label"] = _maint_months["month"].dt.strftime("%b")
        _maint_month_order = pd.date_range(
            start=f"{selected_fees_year}-01-01", periods=12, freq="MS"
        ).strftime("%b").tolist()
        _maint_fig = px.bar(
            _maint_months,
            x="month_label",
            y="fee_amount",
            title=f"Monthly Account Maintenance Fees [{selected_fees_year}]",
            labels={"month_label": "Month", "fee_amount": "Amount"},
            category_orders={"month_label": _maint_month_order},
        )
        _maint_fig.update_traces(marker_color="darkorange", width=0.2)
        _maint_fig.update_layout(xaxis_title="Month", yaxis_title="Amount (₪)")
        st.plotly_chart(_maint_fig, width="stretch")

        if not maintenance_fees_y.empty:
            _maint_total = maintenance_fees_y["amount_value"].sum()
            st.metric("Total Maintenance Fees", f"₪{_maint_total:,.2f}")

            st.markdown("**Transactions**")
            _maint_display = df_dates_to_date_only(maintenance_fees_y[["date", "amount"]].copy())
            _maint_display = order_table_newest_first_with_chrono_index(_maint_display, "date")
            _maint_display = _maint_display.rename(columns={"amount": "Amount"})
            st.dataframe(_maint_display, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Taxes tab
# ---------------------------------------------------------------------------

with tab_taxes:
    required_cols = {"action_type", "date", "delta_ils", "delta_usd", "paper_name", "quantity"}
    missing_cols = sorted(required_cols - set(ledger.columns))
    if missing_cols:
        st.warning("Cannot build taxes table because required columns are missing: " + ", ".join(missing_cols))
    else:
        taxes_table_df = build_tax_ledger(ledger)
        dividend_tax_all_df = build_dividend_tax_ledger(ledger)
        _available_years = tax_year_options(ledger, taxes_table_df)

        if not _available_years:
            st.info("No tax-related actions found.")
        else:
            selected_year = st.selectbox("Year", options=_available_years, index=0, key="taxes_year_filter")
            st.subheader("Capital Gain Taxes")

            taxes_y = filter_tax_rows_by_year(taxes_table_df, selected_year)
            _sort_cols = ["date", "_display_idx"] if "_display_idx" in taxes_y.columns else ["date"]
            taxes_y = taxes_y.sort_values(_sort_cols, ascending=True, kind="mergesort").reset_index(drop=True)

            if not taxes_y.empty:
                _chart = build_capital_gains_monthly_chart_df(taxes_y, selected_year)
                _month_labels = _chart["month"].dt.strftime("%b").tolist()

                _show_shield = st.checkbox("Show Tax Shield", value=True)

                # Manual bar positioning: zero-value bars take no space.
                # Each month is centred at an integer position; active slots share 0.8 width evenly.
                _n = len(_chart)
                _centers = list(range(_n))
                _slot_width_total = 0.8

                _p_off, _p_w = [], []   # payable
                _pay_off, _pay_w = [], []  # payment
                _cr_off, _cr_w = [], []   # credit
                _sh_off, _sh_w = [], []   # shield

                for _i in range(_n):
                    _slots = []
                    if _chart["payable_amount"].iloc[_i] > 0:
                        _slots.append("payable")
                    if _chart["payment_amount"].iloc[_i] > 0:
                        _slots.append("payment")
                    if _chart["credit_amount"].iloc[_i] > 0:
                        _slots.append("credit")
                    if _show_shield and _chart["pre_settlement_shield"].iloc[_i] > 0:
                        _slots.append("shield")

                    _sw = _slot_width_total / len(_slots) if _slots else _slot_width_total
                    _pos = _centers[_i] - _slot_width_total / 2
                    _slot_pos: dict = {}
                    for _s in _slots:
                        _slot_pos[_s] = (_pos - _centers[_i], _sw)
                        _pos += _sw

                    def _get_slot(name: str) -> tuple:
                        return _slot_pos.get(name, (0.0, 0.0))

                    _o, _w = _get_slot("payable");  _p_off.append(_o);   _p_w.append(_w)
                    _o, _w = _get_slot("payment");  _pay_off.append(_o); _pay_w.append(_w)
                    _o, _w = _get_slot("credit");   _cr_off.append(_o);  _cr_w.append(_w)
                    _o, _w = _get_slot("shield");   _sh_off.append(_o);  _sh_w.append(_w)

                _fig = go.Figure()
                _fig.add_trace(go.Bar(
                    name="Payable",
                    x=_centers,
                    y=_chart["payable_amount"],
                    offset=_p_off,
                    width=_p_w,
                    marker_color="gray",
                    opacity=0.6,
                ))
                _fig.add_trace(go.Bar(
                    name="Payment",
                    x=_centers,
                    y=_chart["payment_amount"],
                    offset=_pay_off,
                    width=_pay_w,
                    marker_color="crimson",
                ))
                _fig.add_trace(go.Bar(
                    name="Credit",
                    x=_centers,
                    y=_chart["credit_amount"],
                    offset=_cr_off,
                    width=_cr_w,
                    marker_color="seagreen",
                ))
                if _show_shield:
                    _fig.add_trace(go.Bar(
                        name="Shield Used",
                        x=_centers,
                        y=_chart["shield_used_bar"],
                        base=[0.0] * _n,
                        offset=_sh_off,
                        width=_sh_w,
                        marker_color="darkorange",
                    ))
                    _fig.add_trace(go.Bar(
                        name="Shield Balance",
                        x=_centers,
                        y=_chart["shield_balance_bar"],
                        base=_chart["shield_used_bar"].tolist(),
                        offset=_sh_off,
                        width=_sh_w,
                        marker_color="goldenrod",
                    ))
                _fig.update_layout(
                    barmode="overlay",
                    xaxis=dict(
                        tickmode="array",
                        tickvals=_centers,
                        ticktext=_month_labels,
                    ),
                    title=f"Capital Gains Tax — Monthly Breakdown [{selected_year}]",
                    xaxis_title="Month",
                    yaxis_title="Amount (₪)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(_fig, width="stretch")

                # --- Summary ---
                st.subheader("Summary")
                _summary = build_capital_gains_summary(taxes_y)
                _sum_col1, _sum_col2, _sum_col3, _sum_col4 = st.columns(4)
                _sum_col1.metric("Total Tax Payables", f"₪{_summary['payable_sum']:,.2f}")
                _sum_col2.metric("Total Tax Credits",  f"₪{_summary['credit_sum']:,.2f}")
                _sum_col3.metric("Annual Tax (payments − credits)", f"₪{_summary['annual_tax']:,.2f}")
                _sum_col4.metric("Remaining Tax Shield", f"₪{_summary['remaining_shield']:,.2f}")

                # --- Table (year-filtered, formatted) ---
                taxes_display_df = taxes_y.drop(
                    columns=["month"],
                    errors="ignore",
                ).copy()

                for col in ("tax_shield_state", "tax_payable_state", "total_annual_tax"):
                    taxes_display_df[col] = taxes_display_df[col].map(lambda v: format_signed_currency(v, "₪"))

                taxes_display_df = order_table_newest_first_with_chrono_index(taxes_display_df, "date")
                if "_display_idx" in taxes_display_df.columns:
                    taxes_display_df = taxes_display_df.drop(columns=["_display_idx"])
                annual_year_end_index = set(
                    taxes_display_df.index[taxes_display_df["_annual_year_end"].fillna(False)].tolist()
                )
                taxes_display_df = taxes_display_df.drop(columns=["_annual_year_end", "amount_value"], errors="ignore")
                taxes_display_df = df_dates_to_date_only(taxes_display_df)

                def _style_tax_amount(row: pd.Series) -> list[str]:
                    styles = [""] * len(row)
                    amount_idx = list(row.index).index("amount") if "amount" in row.index else -1
                    annual_idx = list(row.index).index("total_annual_tax") if "total_annual_tax" in row.index else -1
                    if amount_idx >= 0:
                        action_type = str(row.get("action_type", "") or "")
                        if action_type == RawActionType.TAX_CREDIT.value:
                            styles[amount_idx] = "color: #2e7d32; font-weight: 600;"
                        elif action_type == RawActionType.TAX_PAYMENT.value:
                            styles[amount_idx] = "color: #c62828; font-weight: 600;"
                    if annual_idx >= 0 and row.name in annual_year_end_index:
                        styles[annual_idx] = "font-weight: 700;"
                    return styles

                st.dataframe(taxes_display_df.style.apply(_style_tax_amount, axis=1), width="stretch", hide_index=False)
            else:
                st.info("No capital gain tax actions found.")

            # ---------------------------------------------------------------------------
            # Dividend Taxes section
            # ---------------------------------------------------------------------------
            st.divider()
            st.subheader("Dividend Taxes")

            dividend_tax_df = filter_tax_rows_by_year(dividend_tax_all_df, selected_year)

            if dividend_tax_df.empty:
                st.info("No dividend tax rows found for this year.")
            else:
                # --- Monthly bar chart: full 12-month axis ---
                _div_months_merged = build_monthly_amount_series(
                    dividend_tax_df,
                    selected_year=selected_year,
                    amount_column="amount_value",
                    output_column="dividend_tax_amount",
                )
                _div_months_merged["month_label"] = _div_months_merged["month"].dt.strftime("%b")
                _month_order = pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS").strftime("%b").tolist()
                _div_fig = px.bar(
                    _div_months_merged,
                    x="month_label",
                    y="dividend_tax_amount",
                    title=f"Monthly Dividend Tax [{selected_year}]",
                    labels={"month_label": "Month", "dividend_tax_amount": "Amount"},
                    category_orders={"month_label": _month_order},
                )
                _div_fig.update_traces(marker_color="crimson", width=0.2)
                _div_fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)")
                st.plotly_chart(_div_fig, width="stretch")

                # --- Summary ---
                _div_tax_ticker = dividend_tax_df.copy()
                _div_tax_ticker["ticker"] = _div_tax_ticker["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
                _div_tax_totals = _div_tax_ticker.groupby("amount_currency")["amount_value"].sum()
                _div_tax_by_ticker = (
                    _div_tax_ticker.groupby(["ticker", "amount_currency"])["amount_value"]
                    .sum()
                    .reset_index()
                    .sort_values("amount_value", ascending=False)
                )
                _div_tax_by_ticker["total"] = _div_tax_by_ticker["amount_currency"] + _div_tax_by_ticker["amount_value"].map(lambda v: f"{v:,.2f}")
                _div_tax_summary = _div_tax_by_ticker[["ticker", "total"]].rename(columns={"ticker": "Ticker", "total": "Tax Paid"})

                _div_tax_metric_cols = st.columns(len(_div_tax_totals))
                for _col, (_cur, _val) in zip(_div_tax_metric_cols, _div_tax_totals.items()):
                    _col.metric(f"Total Dividend Tax ({_cur})", f"{_cur}{_val:,.2f}")
                st.dataframe(_div_tax_summary, hide_index=True)

                # --- Table ---
                st.markdown("**Transactions**")
                _div_display_cols = [
                    c for c in ("date", "paper_name", "currency", "amount")
                    if c in dividend_tax_df.columns
                ]
                _div_display = df_dates_to_date_only(dividend_tax_df[_div_display_cols].copy())
                if "paper_name" in _div_display.columns:
                    _div_display["paper_name"] = _div_display["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
                    _div_display = _div_display.rename(columns={"paper_name": "Ticker"})
                st.dataframe(_div_display, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Dividends tab
# ---------------------------------------------------------------------------

with tab_dividend:
    st.subheader("Dividends")

    dividend_deposit_all_df = build_dividend_deposit_ledger(ledger)
    _div_deposit_years = dividend_deposit_year_options(dividend_deposit_all_df)

    if not _div_deposit_years:
        st.info("No dividend deposit actions found.")
    else:
        selected_div_year = st.selectbox(
            "Year", options=_div_deposit_years, index=0, key="dividend_year_filter"
        )

        dividend_deposit_y = filter_tax_rows_by_year(dividend_deposit_all_df, selected_div_year)

        # --- Monthly bar chart ---
        _dep_months = build_monthly_amount_series(
            dividend_deposit_y,
            selected_year=selected_div_year,
            amount_column="amount_value",
            output_column="dividend_amount",
        )
        _dep_months["month_label"] = _dep_months["month"].dt.strftime("%b")
        _dep_month_order = pd.date_range(
            start=f"{selected_div_year}-01-01", periods=12, freq="MS"
        ).strftime("%b").tolist()
        _dep_fig = px.bar(
            _dep_months,
            x="month_label",
            y="dividend_amount",
            title=f"Monthly Dividends [{selected_div_year}]",
            labels={"month_label": "Month", "dividend_amount": "Amount"},
            category_orders={"month_label": _dep_month_order},
        )
        _dep_fig.update_traces(marker_color="seagreen", width=0.2)
        _dep_fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)")
        st.plotly_chart(_dep_fig, width="stretch")

        # --- Summary ---
        if not dividend_deposit_y.empty:
            _dep_ticker = dividend_deposit_y.copy()
            _dep_ticker["ticker"] = _dep_ticker["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
            _dep_totals = _dep_ticker.groupby("amount_currency")["amount_value"].sum()
            _dep_by_ticker = (
                _dep_ticker.groupby(["ticker", "amount_currency"])["amount_value"]
                .sum()
                .reset_index()
                .sort_values("amount_value", ascending=False)
            )
            _dep_by_ticker["total"] = _dep_by_ticker["amount_currency"] + _dep_by_ticker["amount_value"].map(lambda v: f"{v:,.2f}")
            _dep_summary = _dep_by_ticker[["ticker", "total"]].rename(columns={"ticker": "Ticker", "total": "Dividends Received"})

            _dep_metric_cols = st.columns(len(_dep_totals))
            for _col, (_cur, _val) in zip(_dep_metric_cols, _dep_totals.items()):
                _col.metric(f"Total Dividends ({_cur})", f"{_cur}{_val:,.2f}")
            st.dataframe(_dep_summary, hide_index=True)

        # --- Table ---
        if dividend_deposit_y.empty:
            st.info("No dividend deposit rows found for this year.")
        else:
            st.markdown("**Transactions**")
            _dep_display_cols = [
                c for c in ("date", "paper_name", "currency", "amount")
                if c in dividend_deposit_y.columns
            ]
            _dep_display = df_dates_to_date_only(dividend_deposit_y[_dep_display_cols].copy())
            _dep_display = order_table_newest_first_with_chrono_index(_dep_display, "date")
            if "paper_name" in _dep_display.columns:
                _dep_display["paper_name"] = _dep_display["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
                _dep_display = _dep_display.rename(columns={"paper_name": "Ticker"})
            st.dataframe(_dep_display, width="stretch", hide_index=True)
