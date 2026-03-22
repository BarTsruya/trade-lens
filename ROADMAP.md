# Trade Lens — Roadmap

todo:
- present closed trades by monthes

---

## Balance

- [ ] Add expected ILS balance column (from broker export) and highlight mismatches
- [ ] Add deposits section
- [ ] Fetch live USD/ILS rate and estimate conversion spread (IBI uses ~0.7% margin)
- [ ] Show per-conversion: executed rate, reference rate, spread %, implied cost

---

## Fees

- [ ] Show conversion spread as an implicit fee (per conversion + monthly aggregation)
- [ ] Download fees table as CSV

---

## Trades (new tab)

- [ ] Filters: date range, symbol
- [ ] Export to CSV

---

## Portfolio (new tab — Holdings + Performance)

### Holdings
- [ ] Live market price + current value
- [ ] Unrealized P&L and day change
- [ ] Export to CSV

### Performance
- [ ] Portfolio NAV over time (daily/weekly/monthly resolution)
- [ ] Overlay deposits/withdrawals on NAV chart
- [ ] Return metrics: time-weighted return (TWR), money-weighted return (XIRR)
- [ ] Compare nominal gain vs real gain (inflation-adjusted)
- [ ] Export performance timeseries to CSV

---

## General / Quality

- [ ] Remember filter selections when switching tabs
- [ ] Fix "full range" button warning in charts
- [ ] Persist loaded data across browser refresh (cache to disk)

---

## Documentation

- [ ] Document ledger schema: delta_usd / delta_ils / fees_usd definitions and assumptions
- [ ] Document supported action types and behavior for unknown types
- [ ] Add known limitations section
