# Trade Lens — Roadmap

todo:
- [ ] check of the the 1.51$ missing in USD balance

---

## Balance

- [ ] Add expected ILS balance column (from broker export) and highlight mismatches
- [ ] Add deposits section or just a filter by action in balance table
- [ ] Fetch live USD/ILS rate and estimate conversion spread (IBI uses ~0.7% margin)
- [ ] Show per-conversion: executed rate, reference rate, spread %, implied cost

---

## Fees

- [ ] Show conversion spread as an implicit fee (per conversion + monthly aggregation)

---

## Portfolio (new tab — Holdings + Performance)

### Holdings
- [ ] Live market price + current value
- [ ] Unrealized P&L and day change


### Performance
- [ ] Portfolio NAV over time (daily/weekly/monthly resolution)
- [ ] Overlay deposits/withdrawals on NAV chart
- [ ] Return metrics: time-weighted return (TWR), money-weighted return (XIRR)
- [ ] Compare nominal gain vs real gain (inflation-adjusted)
- [ ] Export performance timeseries to CSV
- [ ] add final summary of cash deposits sum VS holdings gain sum + balances sum (how much the many realy changed).

---

## General / Quality

- [ ] Remember filter selections when switching tabs
- [ ] Export to CSV everywhere it could be useful

---

## Documentation

- [ ] Document ledger schema: delta_usd / delta_ils / fees_usd definitions and assumptions
- [ ] Document supported action types and behavior for unknown types
- [ ] Add known limitations section
