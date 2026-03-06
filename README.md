## Quickstart
```python
from trade_lens.brokers.ibi import IbiRawLoader
from trade_lens.pipeline.normalize import to_ledger
from trade_lens.analytics.cashflow import monthly_net_cashflow, monthly_fees_breakdown
from trade_lens.analytics.symbols import symbol_summary

raw = IbiRawLoader("ibi_export.xlsx").load()
ledger = to_ledger(raw)

print(monthly_net_cashflow(ledger, currency="USD", include_deposits=True))
print(monthly_fees_breakdown(ledger).head(12))
print(symbol_summary(ledger, currency="USD").head(10))
```

## Fee rules (IBI export)
- `commission_fee` and `additional_fees` are **USD** in the IBI export (v1 assumption validated on sample files).
- For **BUY/SELL** rows:
  - `fees_usd = commission_fee + additional_fees`
  - `net_usd = gross_usd - fees_usd`
- For **ILS-only** cash actions (e.g. `cash_handling_fee_shekel`):
  - The ILS amount is represented in `gross_ils` / `net_ils`
- v1 does **not** perform FX conversion between USD and ILS; ILS columns are kept only when present in the export.