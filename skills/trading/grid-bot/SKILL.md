---
name: grid-bot
description: Automated grid trading strategy on Hyperliquid. Places a grid of limit buy and sell orders within a defined price range and manages them as they fill. Use this skill when the user wants grid trading, range trading, or automated market making within a price band.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, grid, automation, strategy, market-making]
---

# Grid Bot Strategy

Places a ladder of limit buy orders below current price and limit sell orders above, within a defined range. As orders fill, replaces them on the opposite side to capture range-bound oscillations.

## Tools Required

- `hyperliquid_info` — prices, orderbook, open orders, positions
- `hyperliquid_trade` — limit orders, cancels, bulk operations
- `read_file` / `write_file` — state persistence

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. Safety is enforced by grid boundaries (range_low/range_high), per-grid notional cap, and exchange guardrails (kill switch, notional cap, coin allowlist).

## State File

Location: `~/.hermes/strategies/grid-bot/state.json`

```json
{
  "strategy": "grid-bot",
  "version": "1.0.0",
  "coin": "ETH",
  "range_low": 3500,
  "range_high": 4000,
  "grid_count": 10,
  "notional_per_grid_usd": 50,
  "network": "testnet",
  "enabled": true,
  "grid_lines": [],
  "active_orders": {},
  "stats": {
    "grids_filled": 0,
    "total_profit_usd": 0,
    "total_volume_usd": 0,
    "cycles_completed": 0,
    "start_time": null
  },
  "history": []
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `coin` | string | Target coin for the grid |
| `range_low` | number | Lower bound of the grid range |
| `range_high` | number | Upper bound of the grid range |
| `grid_count` | number | Number of grid levels (5-50) |
| `notional_per_grid_usd` | number | USD size per grid order |

### Grid Line Structure

Each grid line in `grid_lines`:
```json
{
  "level": 3,
  "price": 3750,
  "side": "buy",
  "status": "open",
  "oid": 123456,
  "fill_price": null,
  "fill_time": null
}
```

## Execution Flow

### Step 1 — Load State

Read state file. Stop if missing or disabled.

### Step 2 — Calculate Grid

If `grid_lines` is empty (first run), compute the grid:

```
step = (range_high - range_low) / grid_count
levels = [range_low + step * i for i in range(grid_count + 1)]
```

Fetch current price via `hyperliquid_info` `query="all_mids"`.

For each level:
- If level < current_price → place **buy** limit order
- If level > current_price → place **sell** limit order
- Level closest to current price → skip (dead zone)

### Step 3 — Check Existing Orders

Call `hyperliquid_info` with `query="frontend_open_orders"` to get all open orders.

Cross-reference with `active_orders` in state:
- **Order still open** → no action needed
- **Order missing (filled)** → mark as filled, place opposite order at the corresponding grid level

### Step 4 — Handle Filled Orders

For each filled grid order:

1. Record fill in `history`
2. Calculate grid profit: `profit = step * size` (the spread between buy and sell level)
3. Place the **opposite** order at the same level:
   - If a buy was filled → place a **sell** at the next grid level up
   - If a sell was filled → place a **buy** at the next grid level down
4. Dry-run first, then execute

### Step 5 — Range Check

If current price has moved **outside** the grid range:

- **Above range_high**: All buy orders will have filled. Report: "Price above grid range. Grid is fully bought. Consider expanding range or closing."
- **Below range_low**: All sell orders will have filled. Report: "Price below grid range. Grid is fully sold. Consider expanding range or closing."

Do NOT automatically adjust the range — flag it and let the user decide.

### Step 6 — Place Missing Orders

For any grid level that should have an order but doesn't (gaps from startup or errors):

Place the appropriate limit order via `hyperliquid_trade`:
```json
{
  "action": "order",
  "coin": "<coin>",
  "is_buy": true,
  "size": <calculated_from_notional>,
  "price": <grid_level_price>,
  "tif": "Gtc"
}
```

Use `bulk_orders` with `grouping="na"` when placing multiple orders at once for efficiency.

### Step 7 — Update State and Report

```
Grid Bot Report — ETH
═════════════════════
Range: $3,500 — $4,000 | Grid: 10 levels | Step: $50
Current Price: $3,720

Grid Status:
  $3,500 BUY  ● open
  $3,550 BUY  ● open
  $3,600 BUY  ● open
  $3,650 BUY  ● open
  $3,700 BUY  ● filled → SELL placed at $3,750
  ---- current price $3,720 ----
  $3,750 SELL ● open
  $3,800 SELL ● open
  $3,850 SELL ● open
  $3,900 SELL ● open
  $3,950 SELL ● open
  $4,000 SELL ● open

This Cycle: 1 fill | +$2.50 profit
Cumulative: 24 fills | $120.00 profit | $2,400 volume
```

---

## Cronjob Setup

```
cronjob(
  action="create",
  name="grid-bot-eth",
  schedule="every 30s",
  skills=["trading/hyperliquid", "trading/grid-bot"],
  prompt="Run grid bot cycle: check for filled orders, place replacement orders, report status.",
  deliver="local"
)
```

Run frequently (30s-2m) to quickly replace filled orders. Use `deliver="local"` to avoid noise.

---

## Strategy Management

| User says | Action |
|---|---|
| "Grid status" | Display current grid state and stats |
| "Expand grid to 3400-4100" | Update `range_low`/`range_high`, recalculate grid |
| "Stop grid" | Cancel all open orders, set `enabled=false` |
| "Close grid and flatten" | Cancel all orders, close net position |
| "Add more levels" | Increase `grid_count`, place new orders |

---

## Safety

- Each grid order is a standard limit order with full guardrail coverage
- `notional_per_grid_usd` caps per-order size
- Total exposure = `grid_count * notional_per_grid_usd` — known upfront
- Price out of range triggers a warning, not automatic adjustment
- Dry-run before every order placement
- Grid never chases price — waits for mean reversion within range
