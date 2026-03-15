---
name: trailing-stop
description: Automated trailing stop-loss manager for Hyperliquid positions. Monitors open positions and ratchets stop-loss orders upward as price moves in favor. Use this skill when the user wants automatic trailing stops, profit protection, or dynamic stop-loss management.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, trailing-stop, risk-management, automation]
---

# Auto Trailing Stop Strategy

Monitors all open Hyperliquid positions and automatically trails stop-loss orders as price moves favorably. Protects profits without manual intervention.

## Tools Required

- `hyperliquid_info` — positions, prices, open orders
- `hyperliquid_trade` — cancel and place stop orders
- `read_file` / `write_file` — state persistence

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. Safety is enforced by trail logic (never moves stops backward, reduce_only orders) and exchange guardrails (kill switch, notional cap, coin allowlist).

## State File

Location: `~/.hermes/strategies/trailing-stop/state.json`

```json
{
  "strategy": "trailing-stop",
  "version": "1.0.0",
  "trail_pct": 2.0,
  "activation_pct": 1.0,
  "min_trail_distance_usd": 5,
  "update_threshold_pct": 0.5,
  "coins": null,
  "network": "testnet",
  "enabled": true,
  "tracked": {},
  "stats": {
    "stops_placed": 0,
    "stops_updated": 0,
    "stops_triggered": 0,
    "total_saved_pnl_usd": 0
  }
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `trail_pct` | number | Trail distance as % of current price (e.g., 2.0 = 2%) |
| `activation_pct` | number | Only start trailing after position is this % in profit |
| `min_trail_distance_usd` | number | Minimum dollar distance for stop |
| `update_threshold_pct` | number | Only update stop if it would move by at least this % |
| `coins` | string[] or null | Only trail these coins (null = all open positions) |

## Execution Flow

### Step 1 — Load State

Read `~/.hermes/strategies/trailing-stop/state.json`. Stop if missing or disabled.

### Step 2 — Fetch Positions and Prices

Call `hyperliquid_info`:
- `query="user_state"` — get all open positions with entry prices and unrealized PnL
- `query="all_mids"` — get current mid prices

### Step 3 — Process Each Position

For each open position (filtered by `coins` if set):

**Calculate key levels:**
```
entry_price = position.entry_px
current_price = mid_price
is_long = position.size > 0

# Profit calculation
if is_long:
    profit_pct = (current_price - entry_price) / entry_price * 100
    trail_stop = current_price * (1 - trail_pct / 100)
else:  # short
    profit_pct = (entry_price - current_price) / entry_price * 100
    trail_stop = current_price * (1 + trail_pct / 100)
```

**Decision logic:**

| Condition | Action |
|---|---|
| `profit_pct < activation_pct` | Skip — not yet in profit enough to trail |
| No existing stop tracked | Place new stop at `trail_stop` |
| `trail_stop` is better than existing stop AND difference > `update_threshold_pct` | Cancel old stop, place new stop |
| `trail_stop` is worse than existing stop | Keep existing stop (never move stop backward) |

### Step 4 — Place or Update Stop

To place a new stop or update an existing one:

1. If existing stop order exists, cancel it:
   `hyperliquid_trade` with `action="cancel"`, `coin`, `oid=<existing_stop_oid>`

2. Place new stop order via `hyperliquid_trade`:
```json
{
  "action": "order",
  "coin": "<coin>",
  "is_buy": false,
  "size": <position_size>,
  "price": <trail_stop>,
  "tif": "Gtc",
  "reduce_only": true,
  "tpsl": "sl",
  "trigger_px": "<trail_stop>"
}
```
For shorts, `is_buy=true` (closing a short means buying).

Dry-run first, then execute.

3. Update `tracked[coin]` with new stop price and order ID.

### Step 5 — Detect Triggered Stops

For positions that were tracked but no longer appear in `user_state`:
- The stop was likely triggered
- Update `stats.stops_triggered`
- Calculate saved PnL: difference between entry and stop price
- Move from `tracked` to history
- Log the event

### Step 6 — Update State and Report

```
Trailing Stop Report
════════════════════
Tracking: 3 positions

BTC LONG | Entry: $95,000 | Current: $98,200 (+3.4%)
  Stop: $96,236 → $96,636 (updated +0.4%)

ETH LONG | Entry: $3,700 | Current: $3,780 (+2.2%)
  Stop: $3,704 (held — below threshold)

SOL SHORT | Entry: $180 | Current: $175 (+2.8%)
  Stop: $178.50 (new — activation reached)

Stats: 12 placed | 8 updated | 3 triggered | $145.20 saved PnL
```

---

## Cronjob Setup

```
cronjob(
  action="create",
  name="trailing-stop",
  schedule="every 1m",
  skills=["trading/hyperliquid", "trading/trailing-stop"],
  prompt="Run trailing stop check: update stops on all profitable positions, report changes.",
  deliver="local"
)
```

Run frequently (every 1-5 minutes) since stop management is time-sensitive. Use `deliver="local"` to avoid notification spam — only alert on triggered stops.

---

## Safety

- **Never moves stops backward** — stops only ratchet in the favorable direction
- All stop orders use `reduce_only=true` — cannot accidentally increase position
- Activation threshold prevents placing stops on positions that haven't moved
- Update threshold prevents excessive order churn
- Dry-run before every order modification
- Full Hyperliquid guardrail stack applies
