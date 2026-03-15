---
name: mean-reversion
description: Mean reversion trading strategy on Hyperliquid. Identifies overextended price moves using Bollinger Band-style deviation from moving average, enters counter-trend positions, and exits on reversion. Use this skill when the user wants mean reversion, deviation trading, or overbought/oversold strategies.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, mean-reversion, automation, strategy]
---

# Mean Reversion Strategy

Enters counter-trend positions when price deviates significantly from its moving average, and exits when price reverts toward the mean. Uses candle data to compute standard deviation bands.

## Tools Required

- `hyperliquid_info` — candles, prices, positions
- `hyperliquid_trade` — market/limit orders
- `read_file` / `write_file` — state persistence
- `execute_code` — compute moving average and standard deviation from candle data

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. Safety is enforced by state-level limits (max_positions, max_loss_usd, stop_deviation, enabled flag) and exchange guardrails (kill switch, notional cap, coin allowlist).

## State File

Location: `~/.hermes/strategies/mean-reversion/state.json`

```json
{
  "strategy": "mean-reversion",
  "version": "1.0.0",
  "coins": ["BTC", "ETH"],
  "lookback_periods": 20,
  "candle_interval": "1h",
  "entry_deviation": 2.0,
  "exit_deviation": 0.5,
  "stop_deviation": 3.0,
  "notional_per_trade_usd": 100,
  "max_positions": 3,
  "max_loss_usd": 25,
  "network": "testnet",
  "enabled": true,
  "positions": {},
  "stats": {
    "total_trades": 0,
    "wins": 0,
    "losses": 0,
    "total_pnl_usd": 0,
    "avg_hold_hours": 0
  },
  "history": []
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `coins` | string[] | Coins to scan for mean reversion setups |
| `lookback_periods` | number | Number of candles for MA calculation (default: 20) |
| `candle_interval` | string | Candle interval: `"1h"`, `"4h"`, `"1d"` |
| `entry_deviation` | number | Enter when price is this many std devs from MA |
| `exit_deviation` | number | Exit when price reverts to within this many std devs |
| `stop_deviation` | number | Stop loss at this many std devs (wider than entry) |
| `notional_per_trade_usd` | number | Position size per trade |
| `max_positions` | number | Max concurrent mean reversion positions |

## Execution Flow

### Step 1 — Load State

Read state file. Stop if missing or disabled.

### Step 2 — Compute Bands for Each Coin

For each coin in `coins`:

1. Fetch candles via `hyperliquid_info`:
   ```json
   {
     "query": "candles_snapshot",
     "coin": "<coin>",
     "interval": "<candle_interval>",
     "start_time_ms": <now - lookback_periods * interval_ms>,
     "end_time_ms": <now>
   }
   ```

2. Compute using `execute_code`:
   ```python
   import statistics
   closes = [candle["c"] for candle in candles]
   ma = statistics.mean(closes)
   std = statistics.stdev(closes)
   upper_entry = ma + entry_deviation * std
   lower_entry = ma - entry_deviation * std
   upper_stop = ma + stop_deviation * std
   lower_stop = ma - stop_deviation * std
   ```

3. Get current price from `hyperliquid_info` `query="all_mids"`.

### Step 3 — Check Existing Positions

For each open position in `state.positions`:

**Exit conditions:**
- Price has reverted to within `exit_deviation` of MA → **take profit**
- Unrealized loss exceeds `max_loss_usd` → **stop loss**
- Price has moved beyond `stop_deviation` → **stop loss**

To exit: `hyperliquid_trade` `action="market_close"`. Dry-run first.

Update stats and history.

### Step 4 — Scan for New Entries

For each coin without an open position:

| Condition | Action |
|---|---|
| `current_price >= upper_entry` (overbought) | Open **short** — expect reversion down |
| `current_price <= lower_entry` (oversold) | Open **long** — expect reversion up |
| Price between bands | No trade — wait for deviation |

**Before entering, check:**
- Active positions < `max_positions`
- Not entering the same direction as a recently stopped-out position (cooldown: 3 candle periods)

### Step 5 — Execute Entry

1. Dry-run via `hyperliquid_trade`:
   ```json
   {
     "action": "market_open",
     "coin": "<coin>",
     "is_buy": true,
     "notional_usd": <notional_per_trade_usd>,
     "dry_run": true
   }
   ```

2. If dry-run passes, execute live.

3. Record in `state.positions`:
   ```json
   {
     "coin": "ETH",
     "side": "long",
     "entry_price": 3650,
     "entry_time": "2026-03-15T10:00:00Z",
     "ma_at_entry": 3750,
     "std_at_entry": 50,
     "target_price": 3725,
     "stop_price": 3600
   }
   ```

### Step 6 — Report

```
Mean Reversion Report
═════════════════════
BTC — MA(20,1h): $97,200 | Std: $800 | Price: $97,050
  Bands: [$95,600 — $98,800] | Status: within range — no signal

ETH — MA(20,1h): $3,750 | Std: $50 | Price: $3,645
  Bands: [$3,650 — $3,850] | Status: OVERSOLD — long entry triggered
  Position: LONG @ $3,645 | Target: $3,725 | Stop: $3,600

Active: 1/3 positions | Win rate: 65% (13/20) | Net PnL: +$85.40
```

---

## Cronjob Setup

```
cronjob(
  action="create",
  name="mean-reversion",
  schedule="every 15m",
  skills=["trading/hyperliquid", "trading/mean-reversion"],
  prompt="Run mean reversion scan: compute bands, check exits, scan entries, report.",
  deliver="origin"
)
```

Match frequency to candle interval — for 1h candles, checking every 15m is sufficient.

---

## Safety

- Counter-trend by nature — includes explicit stop loss at `stop_deviation`
- Max concurrent positions limit
- Cooldown after stop-outs prevents revenge trading
- Dry-run before every trade
- Full Hyperliquid guardrail stack
- Computable edge: bands are derived from actual volatility, not arbitrary levels
