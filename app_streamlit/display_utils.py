from __future__ import annotations

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Chart color palette — import this in every page to keep colors consistent
# ---------------------------------------------------------------------------

CHART_COLORS: dict[str, str] = {
    "positive":      "#10B981",  # emerald  — gains, dividends, credits
    "negative":      "#EF4444",  # red      — losses, tax payments, fees
    "primary":       "#3B82F6",  # blue     — neutral primary bars
    "warning":       "#F59E0B",  # amber    — FX rate, shield used, maintenance
    "shield_balance": "#EAB308", # yellow   — shield balance bar
    "muted":         "#6B7280",  # gray     — payable / pending bars
}


def get_plotly_template() -> str:
    """Return the appropriate Plotly template for the active Streamlit theme."""
    try:
        base = st.get_option("theme.base")
        return "plotly_dark" if base == "dark" else "plotly_white"
    except Exception:
        return "plotly_white"


def inject_global_css() -> None:
    """Inject shared CSS for a modern card-style dashboard look.

    Call this once at the top of every page (after st.set_page_config).
    """
    primary = CHART_COLORS["primary"]
    st.markdown(
        f"""
        <style>
        /* ── Metric cards ─────────────────────────────────────────────── */
        [data-testid="stMetric"] {{
            border: 1px solid rgba(128,128,128,0.2);
            border-radius: 10px;
            padding: 1rem 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }}
        [data-testid="stMetricLabel"] > div {{
            font-size: 0.8rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            opacity: 0.7;
        }}
        [data-testid="stMetricValue"] > div {{
            font-size: 1.6rem;
            font-weight: 700;
        }}

        /* ── Section headings — underline accent ──────────────────────── */
        h2, h3 {{
            border-bottom: 2px solid {primary};
            padding-bottom: 0.25rem;
            margin-top: 1.4rem !important;
            margin-bottom: 1rem !important;
        }}

        /* ── File uploader ────────────────────────────────────────────── */
        [data-testid="stFileUploaderDropzone"] {{
            border: 2px dashed {primary} !important;
            border-radius: 10px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def df_dates_to_date_only(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with date-like columns converted to Python date values."""
    out = df.copy()
    for col in out.columns:
        is_named_date = col == "date" or col.endswith("_date")
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype(out[col])
        if not (is_named_date or is_datetime_dtype):
            continue
        try:
            converted = pd.to_datetime(out[col], errors="coerce")
            if converted.notna().any():
                out[col] = converted.dt.date
        except Exception:
            continue
    return out


def order_table_newest_first_with_chrono_index(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """Display newest rows first while index labels start at 1 for the oldest row.

    If a ``_display_idx`` column is present it is used as the index label source,
    preserving alignment with the full unfiltered ledger.
    """
    if date_col not in df.columns:
        return df.copy()

    out = df.copy()
    out["_sort_date"] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.loc[out["_sort_date"].notna()].copy()
    if out.empty:
        return out.drop(columns=["_sort_date"], errors="ignore")

    if "_display_idx" in out.columns:
        out["_chrono_index"] = pd.to_numeric(out["_display_idx"], errors="coerce")
        if out["_chrono_index"].isna().any():
            out.sort_values(by="_sort_date", ascending=True, kind="mergesort", inplace=True)
            out["_chrono_index"] = range(1, len(out) + 1)
    else:
        out.sort_values(by="_sort_date", ascending=True, kind="mergesort", inplace=True)
        out["_chrono_index"] = range(1, len(out) + 1)

    out.sort_values(
        by=["_sort_date", "_chrono_index"], ascending=[False, False], kind="mergesort", inplace=True
    )
    out.index = out["_chrono_index"].astype(int)
    out.index.name = None
    out.drop(columns=["_sort_date", "_chrono_index"], inplace=True)
    return out


def format_signed_currency(value: object, symbol: str) -> str:
    """Format a numeric value as signed currency: e.g. ``-₪1,234.56`` or ``$0.00``."""
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return ""
    prefix = "-" if numeric < 0 else ""
    return f"{prefix}{symbol}{abs(float(numeric)):,.2f}"
