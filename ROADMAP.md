# Trade Lens — Roadmap

todo:
- sorting table by column doesnt work well

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

- [ ] Buy/sell blotter: date, symbol, side, qty, executed price, fees, delta USD
- [ ] for each trade: write the total fees and tax to pay in case of profitable one
- [ ] Filters: date range, symbol
- [ ] Closed trade stats (FIFO): realized P&L, win rate, avg win/loss, turnover
- [ ] Export to CSV

---

## Portfolio (new tab — Holdings + Performance)

### Holdings
- [ ] Current quantity per symbol
- [ ] Cost basis (avg buy price)
- [ ] Live market price + current value
- [ ] Unrealized P&L and day change
- [ ] Allocation pie chart
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
