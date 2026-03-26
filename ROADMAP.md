# Trade Lens — Roadmap

todo:
- [ ] check of the the 1.51$ missing in USD balance (use another csv)
- [ ] design a home page that linked to all sub pages (boxes view)
- [ ] change tabs order (portfolio at top, ledger at bottom)
- [ ] add tax payments to taxes summary
- [ ] make sure consistant UI and terminology (Qty / Quantity for example)

---

## Balance

- [ ] Add expected ILS balance column (from broker export) and highlight mismatches
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
- [ ] add final summary of cash deposits sum VS holdings gain sum + balances sum (how is the money realy changed)

---

## General / Quality

- [ ] Remember filter selections when switching tabs
- [ ] Export to CSV everywhere it could be useful

---

## Documentation

- [ ] Document ledger schema: delta_usd / delta_ils / fees_usd definitions and assumptions
- [ ] Document supported action types and behavior for unknown types
- [ ] Add known limitations section
