---
name: portfolio-rebalancer
description: Automated portfolio rebalancing on Hyperliquid. Maintains target allocation weights across multiple coins by periodically checking drift and executing trades to rebalance. Use this skill when the user wants portfolio rebalancing, allocation management, or multi-asset weight targeting.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, portfolio, rebalancing, automation, strategy]
---

# Portfolio Rebalancer Strategy

Maintains a multi-coin portfolio at target allocation weights. Periodically measures drift from targets and executes the minimum trades needed to rebalance.

## Tools Required

- `hyperliquid_info` — positions, prices, balances
- `hyperliquid_trade` — market orders to rebalance
- `read_file` / `write_file` — state persistence
- `execute_code` — drift and trade calculations

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. Safety is enforced by state-level limits (drift_threshold_pct, min_trade_usd, target_equity_usd, enabled flag) and exchange guardrails (kill switch, notional cap, coin allowlist).

## State File

Location: `~/.hermes/strategies/portfolio-rebalancer/state.json`

```json
{
  "strategy": "portfolio-rebalancer",
  "version": "1.0.0",
  "target_equity_usd": 1000,
  "allocations": {
    "BTC": 0.40,
    "ETH": 0.30,
    "SOL": 0.20,
    "HYPE": 0.10
  },
  "drift_threshold_pct": 5,
  "min_trade_usd": 10,
  "rebalance_mode": "threshold",
  "side": "long",
  "network": "testnet",
  "enabled": true,
  "last_rebalance": null,
  "stats": {
    "rebalances_executed": 0,
    "total_trades": 0,
    "total_volume_usd": 0,
    "max_drift_seen_pct": 0
  },
  "history": []
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `target_equity_usd` | number | Total portfolio target size in USD |
| `allocations` | object | Coin → target weight (must sum to 1.0) |
| `drift_threshold_pct` | number | Rebalance when any coin drifts this % from target |
| `min_trade_usd` | number | Skip trades smaller than this to avoid dust |
| `rebalance_mode` | string | `"threshold"` (only when drift exceeds threshold) or `"calendar"` (every run) |
| `side` | string | `"long"` for long-only portfolio |

## Execution Flow

### Step 1 — Load State

Read state file. Stop if missing or disabled.

Validate `allocations` sum to 1.0 (with 0.01 tolerance).

### Step 2 — Fetch Current Portfolio

Call `hyperliquid_info`:
- `query="user_state"` — get all open perp positions with notional values
- `query="all_mids"` — current prices

Calculate current allocation:
```python
total_notional = sum(abs(pos.notional) for pos in positions)
current_weights = {
    coin: abs(pos.notional) / total_notional
    for coin, pos in positions.items()
}
# Coins with no position have weight 0
for coin in allocations:
    if coin not in current_weights:
        current_weights[coin] = 0
```

### Step 3 — Compute Drift

For each coin:
```python
target_weight = allocations[coin]
current_weight = current_weights.get(coin, 0)
drift_pct = abs(current_weight - target_weight) * 100
target_notional = target_equity_usd * target_weight
current_notional = total_notional * current_weight
trade_needed_usd = target_notional - current_notional
```

### Step 4 — Decide Whether to Rebalance

**Threshold mode:** Rebalance only if any coin's drift exceeds `drift_threshold_pct`.

**Calendar mode:** Rebalance every run regardless of drift.

If no rebalance needed:
```
Portfolio Status — No rebalance needed
══════════════════════════════════════
BTC: 41.2% (target 40%) — drift 1.2%
ETH: 29.5% (target 30%) — drift 0.5%
SOL: 19.8% (target 20%) — drift 0.2%
HYPE: 9.5% (target 10%) — drift 0.5%
Max drift: 1.2% (threshold: 5%)
```

### Step 5 — Calculate Trades

Determine trades needed to reach target weights:

```python
trades = []
for coin in allocations:
    delta = target_notional[coin] - current_notional[coin]
    if abs(delta) < min_trade_usd:
        continue  # skip dust
    if delta > 0:
        trades.append({"coin": coin, "action": "increase", "notional_usd": delta})
    else:
        trades.append({"coin": coin, "action": "decrease", "notional_usd": abs(delta)})
```

**Execution order matters:**
1. First execute **decreases** (sell/close partial positions) — frees up capital
2. Then execute **increases** (buy/open positions) — uses freed capital

### Step 6 — Execute Trades

For each trade:

**Decrease (reduce position):**
- If reducing to zero: `action="market_close"`
- If partial reduce: `action="market_open"` with `is_buy=false` (for longs), calculated size

**Increase (add to position):**
- `action="market_open"` with `is_buy=true`, `notional_usd=<delta>`

Dry-run each trade first. Execute sequentially (decreases first, then increases).

### Step 7 — Report

```
Portfolio Rebalance Executed
════════════════════════════
Trades:
  BTC: 41.2% → 40.0% | SELL $12 notional
  ETH: 29.5% → 30.0% | BUY $5 notional
  SOL: 19.8% → 20.0% | BUY $2 notional (skipped — below $10 min)
  HYPE: 9.5% → 10.0% | BUY $5 notional

Executed: 3 trades | Volume: $22
Post-rebalance drift: max 0.2%
Rebalances: #5 | Total volume: $340
```

---

## Cronjob Setup

```
cronjob(
  action="create",
  name="portfolio-rebalancer",
  schedule="0 9 * * *",
  skills=["trading/hyperliquid", "trading/portfolio-rebalancer"],
  prompt="Check portfolio drift and rebalance if threshold exceeded. Report current allocations.",
  deliver="origin"
)
```

Daily is typical for portfolio rebalancing. Weekly (`0 9 * * 1`) for lower-frequency.

---

## Strategy Management

| User says | Action |
|---|---|
| "Portfolio status" | Show current vs target weights, drift |
| "Change BTC target to 50%" | Update allocations (must still sum to 1.0) |
| "Add DOGE at 5%" | Add coin, reduce others proportionally |
| "Remove SOL" | Remove coin, redistribute weight |
| "Force rebalance" | Execute rebalance regardless of drift |
| "Set threshold to 3%" | Update `drift_threshold_pct` |

---

## Safety

- `min_trade_usd` prevents dust trades
- Drift threshold prevents unnecessary churn
- Decreases execute before increases (capital-aware ordering)
- Each individual trade goes through full guardrail stack
- Dry-run before every trade
- Target equity cap limits total portfolio size
- Allocation validation (must sum to 1.0)
