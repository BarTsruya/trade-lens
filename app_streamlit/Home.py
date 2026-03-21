from __future__ import annotations

from typing import Tuple

import pandas as pd
import streamlit as st

from display_utils import format_signed_currency, inject_global_css
from trade_lens.services.ingestion import ingest_files

st.set_page_config(page_title="Home — Trade Lens", layout="wide")
inject_global_css()
st.title("Trade Lens")
st.caption("Upload one or more IBI actions .xlsx exports, then use the sidebar to explore your data.")


@st.cache_data(show_spinner=False)
def _cached_ingest(file_payloads: Tuple[Tuple[str, bytes], ...]):
    result = ingest_files(file_payloads)
    return (
        result.raw,
        result.ledger,
        result.unknown_action_count,
        result.unknown_action_details,
        result.file_count,
    )


uploaded_files = st.file_uploader(
    "Upload IBI actions export", type=["xlsx"], accept_multiple_files=True
)

# If the user navigated away and back, the uploader is empty but data is in session state.
already_loaded = "ledger" in st.session_state and st.session_state["ledger"] is not None

if not uploaded_files and not already_loaded:
    st.info("Upload one or more .xlsx files to begin, then navigate using the sidebar.")
    st.stop()

if uploaded_files:
    try:
        payloads = tuple((f.name, f.getvalue()) for f in uploaded_files)
        raw, ledger, unknown_count, unknown_details, file_count = _cached_ingest(payloads)
    except Exception as exc:
        st.error("Could not load these files. Make sure each is a valid IBI actions .xlsx export.")
        st.exception(exc)
        st.stop()

    # Persist data and file names for when the user navigates away and returns
    st.session_state["ledger"] = ledger
    st.session_state["raw"] = raw
    st.session_state["_loaded_file_names"] = [f.name for f in uploaded_files]
    st.session_state["_loaded_summary"] = (len(raw), len(ledger), unknown_count, unknown_details, file_count)

# From here, data is guaranteed to be in session state (either just loaded or previously loaded)
ledger = st.session_state["ledger"]
raw = st.session_state["raw"]
file_names = st.session_state.get("_loaded_file_names", [])
raw_count, ledger_count, unknown_count, unknown_details, file_count = st.session_state.get(
    "_loaded_summary", (len(raw), len(ledger), 0, pd.DataFrame(), 1)
)

# File name badges
if file_names:
    file_badges = " ".join(
        f"<span style='display:inline-block; background:#DBEAFE; color:#1E40AF; "
        f"padding:0.2rem 0.65rem; border-radius:20px; font-size:0.82rem; margin:0.15rem;'>📄 {name}</span>"
        for name in file_names
    )
    st.markdown(file_badges, unsafe_allow_html=True)

if unknown_count > 0:
    st.warning(
        f"Loaded {file_count:,} file(s): {raw_count:,} raw rows → {ledger_count:,} ledger rows. "
        f"Detected {unknown_count:,} row(s) with unrecognized action types."
    )
    with st.expander(f"Show unrecognized rows ({unknown_count:,})", expanded=False):
        if not unknown_details.empty:
            display_details = unknown_details.copy()
            if "date" in display_details.columns:
                display_details["date"] = pd.to_datetime(display_details["date"], errors="coerce").dt.date
            if len(file_names) == 1 and "source_file" in display_details.columns:
                display_details = display_details.drop(columns=["source_file"])
            if "usd_amount" in display_details.columns:
                display_details["usd_amount"] = display_details["usd_amount"].map(
                    lambda v: format_signed_currency(v, "$")
                )
            if "ils_amount" in display_details.columns:
                display_details["ils_amount"] = display_details["ils_amount"].map(
                    lambda v: format_signed_currency(v, "₪")
                )
            st.caption(
                "'raw_action_type' is the original unrecognized string from the broker export. "
                "Add it to HEBREW_ACTION_TYPE_MAP in ibi.py to resolve it."
            )
            st.dataframe(display_details, hide_index=True)
else:
    st.success(
        f"Loaded {file_count:,} file(s): {raw_count:,} raw rows → {ledger_count:,} ledger rows."
    )

st.info("Use the sidebar to navigate to Ledger, Balance, Fees, Taxes, or Dividends.")
