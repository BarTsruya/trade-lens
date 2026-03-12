# Trade Lens — TODO / Roadmap (Open Tasks Only)

## my todo list:
- [ ] use currency column to write the correct price
- [ ] compare nominal gain and real gain
- [ ] my understanding about taxes:
      - tax shild accumulates
      - when a month which some profit was made in reaches to an end:
      - if tax_to_pay > tax_shield:
        then i will pay tax_to_pay - tax_shield
      - tax get paid OR tax credit received (if tax shield was bigger enough)
- [ ] calculate the average conversion rate (im crurious)
- [ ] fix full_range button warning

## 2) Balance tab (cash timeline)

### 2.1 Row model & ordering
- [ ] Ensure Balance shows **one row per action** (not grouped into fewer rows)
  - [ ] Keep per-row `usd_delta` / `ils_delta`
  - [ ] Compute running balances `usd_balance` / `ils_balance` (cumulative over actions)
  - [ ] Sort by date ascending (stable ordering)

### 2.2 Notes (readability)
- [ ] Improve note generation for key action types
  - [ ] Deposits / withdrawals
  - [ ] ILS->USD conversions (symbol 99028) + show rate text (from the export)
  - [ ] Buy/Sell trades (include symbol, qty, executed price, fees)
  - [ ] Fallback generic note for unknown action types

### 2.3 Running balances correctness
- [ ] Confirm and document fee treatment (avoid double counting)
  - [ ] delta_usd is separated from fees_usd
  - [ ] Ensure balance calculation matches normalization (net vs gross)

### 2.4 Balance reconciliation vs broker “expected”
- [ ] Add `expected_ils` column to Balance output
  - [ ] `expected_ils` values should come from the raw `SHEKEL_BALANCE` column (IBI export)
  - [ ] Map it onto each balance row correctly (action-level alignment)
- [ ] Add discrepancy columns
  - [ ] `ils_diff = ils_balance - expected_ils`
  - [ ] Optional: highlight non-zero diffs in the UI

---

## 3) Fees tab

### 3.1 Conversion fee / spread (reference rate from internet)
- [ ] Calculate conversion “implicit fee” (spread) for ILS->USD conversions
  - [ ] Extract the executed conversion rate from the export (paper_name or related fields)
  - [ ] Fetch reference USD/ILS rate from an internet data source
    - [ ] Choose provider and implement caching
    - [ ] Fetch by conversion timestamp/date (closest available rate)
  - [ ] Compute per-conversion:
    - [ ] executed_rate
    - [ ] reference_rate
    - [ ] spread (absolute and %)
    - [ ] implied_cost_ils and implied_cost_usd
- [ ] Add monthly aggregation of conversion spread
  - [ ] total implied cost
  - [ ] average spread (%), weighted average spread

### 3.2 Fee breakdown & exports
- [ ] Improve fee categorization (if possible from action_type)
- [ ] Download fees table as CSV

---

## 4) Investor-friendly tabs (new, assumes real-time market prices)

## 4.1 Trades (Buy/Sell blotter + closed trade stats)
- [ ] Add “Trades” tab
  - [ ] Show buy/sell actions table
    - [ ] Columns: date, symbol, side, quantity, executed price, delta_usd, fees_usd, note
    - [ ] Filters: date range, symbol
  - [ ] Closed trades statistics
    - [ ] Define “trade grouping” logic (FIFO / average cost / lot-based)
    - [ ] Realized P&L per closed trade
    - [ ] Success rate (win rate)
    - [ ] Count of closed trades
    - [ ] Average win / average loss
    - [ ] Total traded amount / turnover
    - [ ] Total fees for closed trades
  - [ ] Export trades + closed-trade stats to CSV

## 4.2 Holdings / Positions (with real-time prices)
- [ ] Add “Holdings” tab
  - [ ] Current quantity per symbol
  - [ ] Cost basis (avg buy price / lots)
  - [ ] Current market price (real-time)
  - [ ] Current market value
  - [ ] Unrealized P&L
  - [ ] Day change (optional)
  - [ ] Pie chart of current positions allocation (by market value)
  - [ ] Export holdings table to CSV

## 4.3 Performance (with real-time prices)
- [ ] Add “Performance” tab
  - [ ] Define portfolio NAV over time (requires price history or periodic snapshots)
  - [ ] Graph: portfolio growth over time (NAV)
    - [ ] Daily/weekly/monthly resolution selector
    - [ ] Overlay deposits/withdrawals (optional)
  - [ ] Return metrics
    - [ ] Time-weighted return (TWR)
    - [ ] Money-weighted return (IRR/XIRR) (optional)
  - [ ] Export performance timeseries to CSV

---

## 5) Documentation & maintenance
- [ ] Document the normalized ledger schema
  - [ ] delta_usd / delta_ils / fees_usd definitions
  - [ ] assumptions (fees handling, conversion interpretation, etc.)
- [ ] Document supported action types + behavior for unknown types
- [ ] Add “Known limitations” section (data availability, pricing source assumptions)