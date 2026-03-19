from __future__ import annotations

from typing import Tuple

import pandas as pd
import streamlit as st

from display_utils import format_signed_currency
from trade_lens.services.ingestion import ingest_files

st.set_page_config(page_title="Trade Lens", layout="wide")
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

if not uploaded_files:
    st.info("Upload one or more .xlsx files to begin, then navigate using the sidebar.")
    st.stop()

try:
    payloads = tuple((f.name, f.getvalue()) for f in uploaded_files)
    raw, ledger, unknown_count, unknown_details, file_count = _cached_ingest(payloads)
except Exception as exc:
    st.error("Could not load these files. Make sure each is a valid IBI actions .xlsx export.")
    st.exception(exc)
    st.stop()

# Make data available to all pages via session state
st.session_state["ledger"] = ledger
st.session_state["raw"] = raw

if unknown_count > 0:
    st.warning(
        f"Loaded {file_count:,} file(s): {len(raw):,} raw rows → {len(ledger):,} ledger rows. "
        f"Detected {unknown_count:,} row(s) with unrecognized action types."
    )
    with st.expander(f"Show unrecognized rows ({unknown_count:,})", expanded=False):
        if not unknown_details.empty:
            display_details = unknown_details.copy()
            if "date" in display_details.columns:
                display_details["date"] = pd.to_datetime(display_details["date"], errors="coerce").dt.date
            if len(uploaded_files) == 1 and "source_file" in display_details.columns:
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
        f"Loaded {file_count:,} file(s): {len(raw):,} raw rows → {len(ledger):,} ledger rows."
    )

st.info("Use the sidebar to navigate to Ledger, Balance, Fees, Taxes, or Dividends.")
