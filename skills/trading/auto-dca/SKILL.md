---
name: auto-dca
description: Fully autonomous Dollar-Cost Averaging on Hyperliquid. Reads strategy parameters from a state file, executes periodic market buys, tracks cumulative stats, and respects configurable limits. Use this skill when the user wants to set up or run an automated DCA strategy on Hyperliquid.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, dca, automation, strategy]
---

# Auto-DCA Strategy Skill

Autonomous Dollar-Cost Averaging on Hyperliquid. Each cron run reads strategy config from a state file, executes one market buy, updates cumulative stats, and reports the result.

## Tools Required

- `hyperliquid_info` — fetch current price and account state
- `hyperliquid_trade` — execute market orders (with guardrails)
- `execute_code` — read/write the JSON state file
- `read_file` — read state file (alternative to execute_code)
- `write_file` — write state file (alternative to execute_code)

Never use `execute_code` for trading operations. Always call `hyperliquid_info` and `hyperliquid_trade` directly for any exchange interaction.

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. The safety layers are:
1. State-level limits (max_total_usd, max_buys, enabled flag)
2. Exchange guardrails (kill switch, notional cap, coin allowlist)
3. Dry-run preflight validation

## State File

Location: `~/.hermes/strategies/auto-dca/state.json`

```json
{
  "strategy": "auto-dca",
  "version": "1.0.0",
  "coin": "BTC",
  "amount_usd": 50,
  "max_total_usd": 5000,
  "max_buys": 100,
  "price_cap_usd": null,
  "dip_pct": null,
  "reference_price": null,
  "side": "long",
  "network": "testnet",
  "enabled": true,
  "stats": {
    "total_invested_usd": 0,
    "total_size": 0.0,
    "avg_entry_price": 0,
    "buy_count": 0,
    "last_buy_at": null,
    "last_price": null,
    "current_pnl_usd": null
  },
  "history": []
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `coin` | string | Target coin symbol (e.g., `BTC`, `ETH`) — always perp |
| `amount_usd` | number | USD amount per DCA buy |
| `max_total_usd` | number | Stop buying after total invested reaches this |
| `max_buys` | number | Stop buying after this many purchases |
| `price_cap_usd` | number or null | Only buy if current price is below this (null = no cap) |
| `dip_pct` | number or null | Only buy if price dropped this % from `reference_price` (null = disabled) |
| `reference_price` | number or null | Reference price for dip calculation (updated after each buy if dip mode is active) |
| `side` | string | `"long"` (default) or `"short"` |
| `network` | string | `"testnet"` or `"mainnet"` |
| `enabled` | boolean | Kill switch for the strategy |

### Initialization

To set up a new DCA strategy, run:

```bash
python skills/trading/auto-dca/scripts/init_state.py \
  --coin BTC \
  --amount 50 \
  --max-total 5000 \
  --max-buys 100 \
  --network testnet
```

Or instruct the agent: "Set up a DCA strategy: buy $50 of BTC every 4 hours, max $5000 total, testnet."

---

## Execution Flow

Each cron run follows these steps exactly. Do not skip or reorder.

### Step 1 — Load State

Read the state file at `~/.hermes/strategies/auto-dca/state.json` using `read_file`.

If the file does not exist, report: "No DCA state file found. Run init_state.py or ask me to set up a new strategy." and stop.

### Step 2 — Check Limits

Check these conditions. If any fails, report which limit was hit and stop without trading.

| Check | Condition | Message |
|---|---|---|
| Strategy enabled | `enabled == true` | "DCA strategy is disabled." |
| Max investment | `stats.total_invested_usd < max_total_usd` | "Max total investment reached ($X / $Y)." |
| Max buys | `stats.buy_count < max_buys` | "Max buy count reached (X / Y)." |

### Step 3 — Fetch Price

Call `hyperliquid_info` with `query="all_mids"` to get the current mid price for `coin`.

### Step 4 — Check Price Conditions

If `price_cap_usd` is set and current price > `price_cap_usd`:
- Report: "Price $X is above cap $Y. Skipping this cycle."
- Stop without trading.

If `dip_pct` is set and `reference_price` is set:
- Calculate: `drop_pct = (reference_price - current_price) / reference_price * 100`
- If `drop_pct < dip_pct`: report "Price has not dipped enough (need {dip_pct}% drop, current drop {drop_pct}%). Skipping." and stop.

### Step 5 — Dry-Run

Call `hyperliquid_trade` with:
```json
{
  "action": "market_open",
  "coin": "<coin>",
  "is_buy": true,
  "notional_usd": <amount_usd>,
  "dry_run": true
}
```

If `side == "short"`, set `is_buy` to `false`.

Verify the dry-run response:
- `success` must be `true`
- `guardrail.passed` must be `true`
- Check estimated notional is reasonable

If dry-run fails, report the error and stop.

### Step 6 — Execute Live

Call `hyperliquid_trade` with:
```json
{
  "action": "market_open",
  "coin": "<coin>",
  "is_buy": true,
  "notional_usd": <amount_usd>,
  "dry_run": false,
  "confirm_execution": "EXECUTE_LIVE_TRADE"
}
```

If execution fails, report the error. Do not update state on failure.

### Step 7 — Update State

On successful execution, update the state file:

```python
import datetime, json

price = <current_mid_price>
size = <executed_size_from_response>
notional = <actual_notional_usd>

# Update stats
stats["buy_count"] += 1
stats["total_invested_usd"] += notional
stats["total_size"] += size
stats["avg_entry_price"] = stats["total_invested_usd"] / stats["total_size"]
stats["last_buy_at"] = datetime.datetime.utcnow().isoformat() + "Z"
stats["last_price"] = price

# If dip mode, update reference price to current price after buy
if state.get("dip_pct") is not None:
    state["reference_price"] = price

# Append to history
history.append({
    "timestamp": stats["last_buy_at"],
    "price": price,
    "size": size,
    "notional_usd": notional,
    "buy_number": stats["buy_count"],
    "cumulative_invested": stats["total_invested_usd"],
    "avg_entry": stats["avg_entry_price"]
})
```

Write the updated state back to `~/.hermes/strategies/auto-dca/state.json` using `write_file`.

### Step 8 — Report

Generate a concise report:

```
DCA Buy #X completed
Coin: BTC | Side: long
Price: $97,432 | Size: 0.000513 BTC
Notional: $50.00
Avg Entry: $95,200 | Total Invested: $250 / $5,000
Network: testnet
Next buy: ~4h (cron schedule)
```

If the buy was skipped (limit hit, price condition), report why.

---

## Strategy Management Commands

The user can manage the strategy through natural language:

| User says | Action |
|---|---|
| "Pause DCA" | Set `enabled = false` in state file |
| "Resume DCA" | Set `enabled = true` in state file |
| "DCA status" | Read and display state file stats |
| "Change DCA amount to $100" | Update `amount_usd` in state file |
| "Set price cap at $90,000" | Update `price_cap_usd` in state file |
| "Remove price cap" | Set `price_cap_usd = null` |
| "Reset DCA stats" | Zero out stats and clear history |
| "Show DCA history" | Display the history array from state |

---

## Setting Up the Cronjob

After the strategy is initialized, create the cron job:

```
cronjob(
  action="create",
  name="auto-dca-<COIN>",
  schedule="every 4h",
  skills=["trading/hyperliquid", "trading/auto-dca"],
  prompt="Execute the next DCA buy according to the auto-dca skill. Read the state file, check limits and conditions, dry-run, execute if safe, update state, and report the result.",
  deliver="origin"
)
```

Adjust `schedule` based on user preference:
- `"every 1h"` — aggressive DCA
- `"every 4h"` — standard
- `"every 12h"` — conservative
- `"0 9 * * *"` — daily at 9am
- `"0 9 * * 1"` — weekly on Monday

---

## Safety Guarantees

1. **Guardrails always active** — `HYPERLIQUID_KILL_SWITCH`, `HYPERLIQUID_MAX_NOTIONAL_USD`, `HYPERLIQUID_ALLOWED_COINS` all apply to every trade
2. **Dry-run before every live trade** — never skip the dry-run step
3. **State-level limits** — `max_total_usd` and `max_buys` enforce strategy-level caps independent of exchange guardrails
4. **Price conditions** — optional `price_cap_usd` and `dip_pct` prevent buying at unfavorable prices
5. **Strategy kill switch** — `enabled` flag in state file for instant pause
6. **Network isolation** — default `testnet`, must explicitly change to `mainnet`
7. **No recursive scheduling** — cronjob tool is disabled inside cron runs
8. **State persistence** — atomic file writes, state survives crashes

## Error Recovery

| Error | Action |
|---|---|
| State file missing | Stop and report. Do not create a default state. |
| State file corrupt | Stop and report. Do not attempt to fix. |
| Exchange unreachable | Stop and report. Next cron cycle will retry. |
| Dry-run fails guardrail | Report which guardrail failed. Do not execute. |
| Live trade rejected | Report exchange error. Do not update state. |
| Insufficient balance | Report. Suggest pausing strategy or reducing amount. |
