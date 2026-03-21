# Trade Lens

A local desktop dashboard for analyzing your IBI broker export. Upload your `.xlsx` file and get a clear view of your trading activity — no cloud, no accounts.

**What you get:**
- **Ledger** — every action in one searchable table
- **Balance** — cash timeline (USD & ILS), FX conversions, running balances
- **Fees** — trading commissions and account maintenance charges, by year and ticker
- **Taxes** — capital gains tax summary and tax shield history
- **Dividends** — dividend income by year and stock

---

## Requirements

- Python 3.10+
- An IBI actions export in `.xlsx` format

---

## Run

**Easiest — double-click `run.bat`**

On first run it creates a virtual environment and installs all dependencies automatically.

**Manual:**

```bash
pip install -r requirements.txt
streamlit run app_streamlit/Home.py
.venv\Scripts\python.exe -m streamlit run app_streamlit/Home.py --server.address 0.0.0.0 --server.port 8503
```

Then open `http://localhost:8501` in your browser.

---

## Project structure

```
trade_lens/
  brokers/        # Broker-specific file loaders (IBI)
  services/       # Business logic: ingestion, balance, fees, taxes, dividends
  models/         # Pydantic response schemas
app_streamlit/
  Home.py         # Entry point — file upload and session state
  pages/          # One file per sidebar tab
  display_utils.py # Shared UI helpers and chart colors
requirements.txt
run.bat           # One-click launcher (Windows)
```

---

## Disclaimer

Not investment advice. Use at your own risk.
