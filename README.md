# TradeLens

Python-first trade activity import + normalization + analytics.

## Current scope (v1)
- Broker: IBI (Israeli broker) `.xlsx` export
- Trading currency: USD (ledger includes `gross_usd`)
- Also keeps ILS values from the export for reporting (`gross_ils`)

## Structure
- `trade_lens/brokers/` – broker-specific loaders (IBI)
- `trade_lens/pipeline/` – normalization into a canonical ledger dataframe
- `trade_lens/analytics/` – pure analytics functions on top of the ledger
- `trade_lens/models/` – small enums/dataclasses used across layers

## Quickstart
```python
from trade_lens.brokers.ibi import IbiRawLoader
from trade_lens.pipeline.normalize import to_ledger
from trade_lens.analytics.cashflow import monthly_net_cashflow
from trade_lens.analytics.symbols import symbol_summary

raw = IbiRawLoader("ibi_export.xlsx").load()
ledger = to_ledger(raw)

print(monthly_net_cashflow(ledger, currency="USD", include_deposits=True))
print(symbol_summary(ledger, currency="USD").head(10))
```

## Fee rules
- IBI exports include `commission_fee` and `additional_fees` on buy/sell rows.
- For buy/sell rows:
  - `net_ils = gross_ils - (commission_fee + additional_fees)`
- For other rows (e.g. cash handling fee):
  - `net_ils = gross_ils` (avoid double-counting)