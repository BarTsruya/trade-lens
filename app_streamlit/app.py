from __future__ import annotations

import re
from typing import Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from display_utils import (
    df_dates_to_date_only,
    format_signed_currency,
    order_table_newest_first_with_chrono_index,
)
from trade_lens.brokers.ibi import RawActionType
from trade_lens.services.ingestion import ingest_files
from trade_lens.services.ledger_view import LedgerFilters, get_ledger_view
from trade_lens.services.balance import get_balance_summary
from trade_lens.services.fees import get_fees_summary
from trade_lens.services.taxes import get_tax_summary
from trade_lens.services.dividends import get_dividend_summary


st.set_page_config(page_title="Trade Lens", layout="wide")
st.title("Trade Lens - IBI Actions Explorer")
st.caption("Upload an IBI actions .xlsx export to inspect ledger, cashflow, fees, and symbol activity.")


@st.cache_data(show_spinner=False)
def _cached_ingest(file_payloads: Tuple[Tuple[str, bytes], ...]):
    return ingest_files(file_payloads)


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

uploaded_files = st.file_uploader("Upload IBI actions export", type=["xlsx"], accept_multiple_files=True)

if not uploaded_files:
    st.info("Upload one or more .xlsx files to begin.")
    st.stop()

try:
    payloads = tuple((f.name, f.getvalue()) for f in uploaded_files)
    ingestion = _cached_ingest(payloads)
except Exception as exc:
    st.error("Could not load these files. Make sure each is a valid IBI actions .xlsx export.")
    st.exception(exc)
    st.stop()

raw = ingestion.raw
ledger = ingestion.ledger

if ingestion.unknown_action_count > 0:
    st.warning(
        f"Loaded {ingestion.file_count:,} file(s): {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows. "
        f"Detected {ingestion.unknown_action_count:,} row(s) with unrecognized action types."
    )
    with st.expander(f"Show unrecognized rows ({ingestion.unknown_action_count:,})", expanded=False):
        unknown_details = ingestion.unknown_action_details
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
        f"Loaded {ingestion.file_count:,} file(s): {len(raw):,} raw rows and normalized to {len(ledger):,} ledger rows."
    )

tab_ledger, tab_balance, tab_fees, tab_taxes, tab_dividend = st.tabs(["Ledger", "Balance", "Fees", "Taxes", "Dividends"])

# ---------------------------------------------------------------------------
# Ledger tab
# ---------------------------------------------------------------------------

with tab_ledger:
    st.subheader("Ledger Preview")

    # Unfiltered view to populate filter controls
    full_view = get_ledger_view(ledger)
    min_date, max_date = full_view.date_bounds
    default_date_range = (min_date, max_date)
    action_options = full_view.action_options
    symbol_options = full_view.symbol_options

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
    filters = LedgerFilters(
        date_range=active_date_range,
        action_types=selected_action_types or None,
        symbols=selected_symbols or None,
    )
    view = get_ledger_view(ledger, filters) if any([active_date_range, selected_action_types, selected_symbols]) else full_view
    filtered_ledger = view.filtered

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

    balance = get_balance_summary(ledger)

    if balance.timeline.empty:
        st.warning("No balance actions found for these action types.")
    else:
        balance_display_df = df_dates_to_date_only(balance.timeline)
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
        balance_table_df = balance_table_df.drop(columns=["action_type"], errors="ignore")
        st.dataframe(balance_table_df, width="stretch", hide_index=False)

        st.divider()
        st.subheader("Foreign Exchange Conversions")

        if balance.fx_transactions.empty:
            st.info("No foreign exchange conversion rows found.")
        else:
            fx = balance.fx_transactions.copy()

            _fx_chart_df = fx.dropna(subset=["rate_value", "delta_ils"]).sort_values("date").copy()
            _fx_chart_df["delta_ils_abs"] = _fx_chart_df["delta_ils"].abs()
            _fx_chart_df["delta_usd_abs"] = _fx_chart_df["delta_usd"].abs()

            if not _fx_chart_df.empty:
                _fx_fig = make_subplots(specs=[[{"secondary_y": True}]])
                _fx_fig.add_trace(
                    go.Bar(x=_fx_chart_df["date"], y=_fx_chart_df["delta_ils_abs"], name="ILS Converted", marker_color="steelblue", opacity=0.6),
                    secondary_y=False,
                )
                _fx_fig.add_trace(
                    go.Scatter(x=_fx_chart_df["date"], y=_fx_chart_df["rate_value"], name="Rate (USD/ILS)", mode="lines+markers", marker_color="darkorange"),
                    secondary_y=True,
                )
                _fx_fig.update_layout(title="ILS Converted & Conversion Rate Over Time", xaxis_title="Date")
                _fx_fig.update_yaxes(title_text="ILS Amount (₪)", secondary_y=False)
                _fx_fig.update_yaxes(title_text="Rate (USD/ILS)", secondary_y=True)
                st.plotly_chart(_fx_fig, width="stretch")

                if balance.fx_summary is not None:
                    _fx_sum_col1, _fx_sum_col2, _fx_sum_col3 = st.columns(3)
                    _fx_sum_col1.metric("Average Rate (USD/ILS)", f"{balance.fx_summary.avg_rate:,.4f}")
                    _fx_sum_col2.metric("Total ILS Converted", f"₪{balance.fx_summary.total_ils_converted:,.2f}")
                    _fx_sum_col3.metric("Total USD Produced", f"${balance.fx_summary.total_usd_produced:,.2f}")

            fx["ILS Amount"] = fx["delta_ils"].map(lambda v: format_signed_currency(v, "₪"))
            fx["USD Amount"] = fx["delta_usd"].map(lambda v: format_signed_currency(v, "$"))
            fx["Rate"] = fx["rate_label"]
            _fx_display = fx[["date", "USD Amount", "ILS Amount", "Rate"]].copy()
            _fx_display = order_table_newest_first_with_chrono_index(_fx_display, "date")
            st.dataframe(_fx_display, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Fees tab
# ---------------------------------------------------------------------------

with tab_fees:
    # Call service with no year first to get year options and default data
    _fees_preview = get_fees_summary(ledger)

    if not _fees_preview.year_options:
        st.info("No fees data available.")
    else:
        selected_fees_year = st.selectbox("Year", options=_fees_preview.year_options, index=0, key="fees_year_filter")
        fees = get_fees_summary(ledger, selected_fees_year) if selected_fees_year != _fees_preview.selected_year else _fees_preview

        # -----------------------------------------------------------------------
        # Section 1: Trading Fees (USD)
        # -----------------------------------------------------------------------
        st.subheader("Trading Fees")

        _trade_months = fees.trading_monthly.copy()
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

        if not fees.trading_by_year.empty:
            st.metric("Total Trading Fees", f"${fees.trading_total:,.2f}")

            if not fees.trading_by_ticker.empty:
                _trade_by_ticker = fees.trading_by_ticker.copy()
                _trade_by_ticker["Amount"] = "$" + _trade_by_ticker["amount_value"].map(lambda v: f"{v:,.2f}")
                st.dataframe(_trade_by_ticker[["symbol", "Amount"]].rename(columns={"symbol": "Ticker"}), hide_index=True)

            st.markdown("**Transactions**")
            _trade_cols = [c for c in ("date", "action_type", "symbol", "amount") if c in fees.trading_by_year.columns]
            _trade_display = df_dates_to_date_only(fees.trading_by_year[_trade_cols].copy())
            _trade_display = order_table_newest_first_with_chrono_index(_trade_display, "date")
            _trade_display = _trade_display.rename(columns={"action_type": "Action", "symbol": "Ticker", "amount": "Amount"})
            st.dataframe(_trade_display, width="stretch", hide_index=True)

        st.divider()

        # -----------------------------------------------------------------------
        # Section 2: Account Maintenance Fees (ILS)
        # -----------------------------------------------------------------------
        st.subheader("Account Maintenance Fees")

        if fees.maintenance_by_year.empty:
            st.info("No account maintenance fee rows found for this year.")
        else:
            _maint_months = fees.maintenance_monthly.copy()
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

            st.metric("Total Maintenance Fees", f"₪{fees.maintenance_total:,.2f}")

            st.markdown("**Transactions**")
            _maint_display = df_dates_to_date_only(fees.maintenance_by_year[["date", "amount"]].copy())
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
        _tax_preview = get_tax_summary(ledger)

        if not _tax_preview.year_options:
            st.info("No tax-related actions found.")
        else:
            selected_year = st.selectbox("Year", options=_tax_preview.year_options, index=0, key="taxes_year_filter")
            tax = get_tax_summary(ledger, selected_year) if selected_year != _tax_preview.selected_year else _tax_preview

            st.subheader("Capital Gain Taxes")

            if not tax.capital_gains_by_year.empty:
                _chart = tax.monthly_chart
                _month_labels = _chart["month"].dt.strftime("%b").tolist()

                _show_shield = st.checkbox("Show Tax Shield", value=True)

                _n = len(_chart)
                _centers = list(range(_n))
                _slot_width_total = 0.8

                _p_off, _p_w = [], []
                _pay_off, _pay_w = [], []
                _cr_off, _cr_w = [], []
                _sh_off, _sh_w = [], []

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

                st.subheader("Summary")
                _summary = tax.summary
                _sum_col1, _sum_col2, _sum_col3, _sum_col4 = st.columns(4)
                _sum_col1.metric("Total Tax Payables", f"₪{_summary['payable_sum']:,.2f}")
                _sum_col2.metric("Total Tax Credits",  f"₪{_summary['credit_sum']:,.2f}")
                _sum_col3.metric("Annual Tax (payments − credits)", f"₪{_summary['annual_tax']:,.2f}")
                _sum_col4.metric("Remaining Tax Shield", f"₪{_summary['remaining_shield']:,.2f}")

                taxes_display_df = tax.capital_gains_by_year.drop(columns=["month"], errors="ignore").copy()
                for col in ("tax_shield_state", "tax_payable_state", "total_annual_tax"):
                    if col in taxes_display_df.columns:
                        taxes_display_df[col] = taxes_display_df[col].map(lambda v: format_signed_currency(v, "₪"))

                taxes_display_df = order_table_newest_first_with_chrono_index(taxes_display_df, "date")
                if "_display_idx" in taxes_display_df.columns:
                    taxes_display_df = taxes_display_df.drop(columns=["_display_idx"])
                annual_year_end_index = set(
                    taxes_display_df.index[taxes_display_df["_annual_year_end"].fillna(False)].tolist()
                ) if "_annual_year_end" in taxes_display_df.columns else set()
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

            # -----------------------------------------------------------------------
            # Dividend Taxes section
            # -----------------------------------------------------------------------
            st.divider()
            st.subheader("Dividend Taxes")

            if tax.dividend_tax_by_year.empty:
                st.info("No dividend tax rows found for this year.")
            else:
                _div_months = tax.dividend_tax_monthly.copy()
                _div_months["month_label"] = _div_months["month"].dt.strftime("%b")
                _month_order = pd.date_range(start=f"{selected_year}-01-01", periods=12, freq="MS").strftime("%b").tolist()
                _div_fig = px.bar(
                    _div_months,
                    x="month_label",
                    y="dividend_tax_amount",
                    title=f"Monthly Dividend Tax [{selected_year}]",
                    labels={"month_label": "Month", "dividend_tax_amount": "Amount"},
                    category_orders={"month_label": _month_order},
                )
                _div_fig.update_traces(marker_color="crimson", width=0.2)
                _div_fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)")
                st.plotly_chart(_div_fig, width="stretch")

                if tax.dividend_tax_by_ticker is not None and not tax.dividend_tax_by_ticker.empty:
                    _div_tax_by_ticker = tax.dividend_tax_by_ticker.copy()
                    _div_tax_by_ticker["total"] = _div_tax_by_ticker["amount_currency"] + _div_tax_by_ticker["amount_value"].map(lambda v: f"{v:,.2f}")
                    _div_tax_summary = _div_tax_by_ticker[["ticker", "total"]].rename(columns={"ticker": "Ticker", "total": "Tax Paid"})

                    _div_tax_metric_cols = st.columns(max(1, len(tax.dividend_tax_totals)))
                    for _col, (_cur, _val) in zip(_div_tax_metric_cols, tax.dividend_tax_totals.items()):
                        _col.metric(f"Total Dividend Tax ({_cur})", f"{_cur}{_val:,.2f}")
                    st.dataframe(_div_tax_summary, hide_index=True)

                st.markdown("**Transactions**")
                _div_display_cols = [c for c in ("date", "paper_name", "amount") if c in tax.dividend_tax_by_year.columns]
                _div_display = df_dates_to_date_only(tax.dividend_tax_by_year[_div_display_cols].copy())
                if "paper_name" in _div_display.columns:
                    _div_display["paper_name"] = _div_display["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
                    _div_display = _div_display.rename(columns={"paper_name": "Ticker"})
                st.dataframe(_div_display, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Dividends tab
# ---------------------------------------------------------------------------

with tab_dividend:
    st.subheader("Dividends")

    _div_preview = get_dividend_summary(ledger)

    if not _div_preview.year_options:
        st.info("No dividend deposit actions found.")
    else:
        selected_div_year = st.selectbox(
            "Year", options=_div_preview.year_options, index=0, key="dividend_year_filter"
        )
        div = get_dividend_summary(ledger, selected_div_year) if selected_div_year != _div_preview.selected_year else _div_preview

        _dep_months = div.monthly.copy()
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

        if not div.deposit_by_year.empty:
            if not div.by_ticker.empty:
                _dep_by_ticker = div.by_ticker.copy()
                _dep_by_ticker["total"] = _dep_by_ticker["amount_currency"] + _dep_by_ticker["amount_value"].map(lambda v: f"{v:,.2f}")
                _dep_summary = _dep_by_ticker[["ticker", "total"]].rename(columns={"ticker": "Ticker", "total": "Dividends Received"})

                _dep_metric_cols = st.columns(max(1, len(div.totals)))
                for _col, (_cur, _val) in zip(_dep_metric_cols, div.totals.items()):
                    _col.metric(f"Total Dividends ({_cur})", f"{_cur}{_val:,.2f}")
                st.dataframe(_dep_summary, hide_index=True)

            st.markdown("**Transactions**")
            _dep_display_cols = [c for c in ("date", "paper_name", "amount") if c in div.deposit_by_year.columns]
            _dep_display = df_dates_to_date_only(div.deposit_by_year[_dep_display_cols].copy())
            _dep_display = order_table_newest_first_with_chrono_index(_dep_display, "date")
            if "paper_name" in _dep_display.columns:
                _dep_display["paper_name"] = _dep_display["paper_name"].str.split("/").str[-1].str.strip().str.split().str[0]
                _dep_display = _dep_display.rename(columns={"paper_name": "Ticker"})
            st.dataframe(_dep_display, width="stretch", hide_index=True)
        else:
            st.info("No dividend deposit rows found for this year.")
