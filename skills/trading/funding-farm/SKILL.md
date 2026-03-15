---
name: funding-farm
description: Automated funding rate farming on Hyperliquid. Opens positions to collect funding payments when rates exceed a threshold. Closes when funding normalizes or PnL targets are hit. Use this skill when the user wants to farm funding rates, collect funding payments, or run a funding-based strategy.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, funding, automation, strategy]
---

# Funding Farm Strategy

Collect funding payments by positioning against extreme funding rates. When funding is significantly positive (longs pay shorts), open a short. When significantly negative (shorts pay longs), open a long. Close when funding normalizes or a PnL exit is triggered.

## Tools Required

- `hyperliquid_info` — funding rates, prices, positions
- `hyperliquid_trade` — market orders with guardrails
- `read_file` / `write_file` — state persistence

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. Safety is enforced by state-level limits (max_total_notional_usd, max_loss_usd, max_hold_hours, enabled flag) and exchange guardrails (kill switch, notional cap, coin allowlist).

## State File

Location: `~/.hermes/strategies/funding-farm/state.json`

```json
{
  "strategy": "funding-farm",
  "version": "1.0.0",
  "coins": ["BTC", "ETH", "SOL", "HYPE"],
  "notional_per_coin_usd": 100,
  "max_total_notional_usd": 1000,
  "funding_threshold_bps": 5,
  "funding_exit_bps": 1,
  "max_loss_usd": 20,
  "max_hold_hours": 48,
  "network": "testnet",
  "enabled": true,
  "positions": {},
  "stats": {
    "total_funding_collected_usd": 0,
    "total_trades": 0,
    "total_pnl_usd": 0,
    "win_count": 0,
    "loss_count": 0
  },
  "history": []
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `coins` | string[] | Coins to scan for funding opportunities |
| `notional_per_coin_usd` | number | Position size per coin |
| `max_total_notional_usd` | number | Max total open notional across all coins |
| `funding_threshold_bps` | number | Min annualized funding rate (bps) to enter |
| `funding_exit_bps` | number | Close when funding drops below this |
| `max_loss_usd` | number | Per-position stop loss in USD |
| `max_hold_hours` | number | Max hours to hold a funding position |

## Execution Flow

### Step 1 — Load State

Read `~/.hermes/strategies/funding-farm/state.json`. Stop if missing or `enabled == false`.

### Step 2 — Fetch Funding Rates

Call `hyperliquid_info` with `query="predicted_fundings"` to get predicted next funding rates for all coins.

Also call `hyperliquid_info` with `query="all_mids"` for current prices.

### Step 3 — Check Existing Positions

Call `hyperliquid_info` with `query="user_state"` to get current open positions.

For each position tracked in `state.positions`:

**Exit conditions (close if ANY is true):**
- Funding rate for this coin has dropped below `funding_exit_bps` (funding normalized)
- Unrealized PnL < `-max_loss_usd` (stop loss hit)
- Position held longer than `max_hold_hours`
- Funding flipped direction (was collecting, now paying)

**To close:** Call `hyperliquid_trade` with `action="market_close"`, `coin=<coin>`. Dry-run first, then execute. Update state: remove from `positions`, add to `history`, update `stats`.

### Step 4 — Scan for New Entries

For each coin in `coins` that does NOT have an open position:

1. Get predicted funding rate
2. Convert to annualized bps: `annual_bps = hourly_rate * 8760 * 10000`
3. If `abs(annual_bps) >= funding_threshold_bps`:
   - Funding positive (longs pay shorts) → open **short** (collect funding)
   - Funding negative (shorts pay longs) → open **long** (collect funding)

**Before entering, check:**
- Total open notional + new notional <= `max_total_notional_usd`
- No existing position in this coin

### Step 5 — Execute Entry

For each qualifying coin:

1. Dry-run: `hyperliquid_trade` with `action="market_open"`, `coin`, `is_buy` (opposite of funding direction), `notional_usd`, `dry_run=true`
2. If dry-run passes, execute live
3. Update state: add to `positions` with entry time, entry price, entry funding rate, direction

### Step 6 — Update State

Write updated state to file. Update `stats` with any closed positions.

### Step 7 — Report

```
Funding Farm Report
═══════════════════
Active Positions: 2
  BTC SHORT @ $97,400 | Funding: +12 bps/yr | Held: 6h | uPnL: +$1.20
  ETH SHORT @ $3,800  | Funding: +8 bps/yr  | Held: 2h | uPnL: -$0.30

Closed This Cycle: 1
  SOL LONG closed | Held: 14h | PnL: +$3.50 (funding) - $1.20 (price) = +$2.30

Cumulative: 15 trades | $42.50 funding collected | $28.30 net PnL
Network: testnet
```

---

## Cronjob Setup

```
cronjob(
  action="create",
  name="funding-farm",
  schedule="every 1h",
  skills=["trading/hyperliquid", "trading/funding-farm"],
  prompt="Run the funding farm cycle: check exits on existing positions, scan for new funding opportunities, execute entries, and report.",
  deliver="origin"
)
```

Run every hour to stay responsive to funding rate changes. The 8-hour funding cycle means you want to enter well before the settlement window.

---

## Safety

- All trades go through Hyperliquid guardrails (kill switch, notional cap, coin allowlist)
- Dry-run before every live trade
- Per-position stop loss (`max_loss_usd`)
- Max hold time prevents stuck positions
- Total notional cap limits exposure
- Strategy kill switch (`enabled` flag)
