# TradeLens

TradeLens is a small local dashboard for analyzing an IBI (Israeli broker) Excel export (`.xlsx`).

It loads your broker export, normalizes it into a consistent “ledger”, and shows a simple set of insights:
- Monthly net cashflow (USD / ILS)
- Monthly fees (USD embedded trading fees, plus ILS cash-handling fees)
- Symbol (ticker) summary

> This project is intended for personal/local analysis. It does not perform FX conversion (USD↔ILS) in v1.

---

## What you need

- Python 3.10+ (recommended)
- An IBI export file in `.xlsx` format

---

## Run the app (local)

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Start the Streamlit app:

```powershell
streamlit run app_streamlit/app.py
```

3. Open the URL that Streamlit prints (usually `http://localhost:8501`) and upload your IBI `.xlsx`.

---

## Run the app from your phone (same Wi‑Fi)

On the computer running the app:

```Terminal
.venv\Scripts\activate.bat
.venv\Scripts\python.exe -m streamlit run app_streamlit/app.py --server.address 0.0.0.0 --server.port 8503
```

Then on your phone, open:

- `http://<YOUR_COMPUTER_IP>:8501`

Tip (Windows): find your local IP with:

```powershell
ipconfig
```

Look for the **IPv4 Address** of your Wi‑Fi adapter (often `192.168.x.x`).

---

## Using the UI

The app is a single page with tabs:

- **Ledger**: preview of the normalized rows (sanity check your import)
- **Cashflow**: monthly net cashflow chart + table
- **Fees**: monthly fee breakdown
  - trading fees are in **USD**
  - cash-handling fees are shown in **ILS** (as they appear in the export)
- **Symbols**: summary per ticker (buy/sell only)

---

## Notes about fees and currencies (IBI export)

- In the IBI export, `commission_fee` and `additional_fees` are treated as **USD** (v1 assumption validated on sample exports).
- For BUY/SELL rows:
  - `fees_usd = commission_fee + additional_fees`
  - `net_usd = gross_usd - fees_usd`
- For ILS-only cash actions (e.g. cash handling fee), the ILS amount appears in `gross_ils` / `net_ils`.

v1 does **not** convert currencies; USD and ILS are shown separately.

---

## Repo structure (for contributors)

- `trade_lens/brokers/` – broker-specific loaders (IBI)
- `trade_lens/pipeline/` – normalization into a canonical ledger dataframe
- `trade_lens/analytics/` – analytics functions on top of the ledger
- `app_streamlit/` – the Streamlit dashboard

---

## Troubleshooting

### The app opens but shows no analysis
Make sure you actually uploaded an `.xlsx` file (not a screenshot / Google Sheets link).
Try refreshing the page and uploading again.

### Phone can’t connect to the app
- Ensure the computer and phone are on the same Wi‑Fi network
- Start Streamlit with `--server.address 0.0.0.0`
- Allow inbound connections in Windows Firewall for the Streamlit port (default 8501)

---

## Disclaimer
This is not investment advice. Use at your own risk.