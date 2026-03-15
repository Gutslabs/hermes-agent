---
name: liquidation-sniper
description: Detects large liquidation cascades on Hyperliquid and enters counter-trend positions after the flush, betting on a bounce. Use this skill when the user wants to trade liquidation events, buy wicks, or capitalize on cascade sell-offs.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, liquidation, automation, strategy, contrarian]
---

# Liquidation Sniper Strategy

Monitors for signs of liquidation cascades (rapid price drops + volume spikes + orderbook imbalance) and enters counter-trend positions after the flush subsides. The thesis: forced selling creates temporary dislocations that revert.

## Tools Required

- `hyperliquid_info` — candles, orderbook, prices, positions, funding
- `hyperliquid_trade` — market orders with TP/SL
- `read_file` / `write_file` — state persistence
- `execute_code` — cascade detection calculations

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. Safety is enforced by state-level limits (max_concurrent, max_trades_per_day, cooldown_candles, sl_pct, enabled flag) and exchange guardrails (kill switch, notional cap, coin allowlist).

## State File

Location: `~/.hermes/strategies/liquidation-sniper/state.json`

```json
{
  "strategy": "liquidation-sniper",
  "version": "1.0.0",
  "coins": ["BTC", "ETH", "SOL"],
  "candle_interval": "5m",
  "cascade_threshold": {
    "price_drop_pct": 2.0,
    "volume_spike_x": 3.0,
    "lookback_candles": 6
  },
  "cooldown_candles": 3,
  "entry_mode": "limit_wick",
  "tp_pct": 1.5,
  "sl_pct": 1.0,
  "notional_per_trade_usd": 100,
  "max_concurrent": 2,
  "max_trades_per_day": 5,
  "network": "testnet",
  "enabled": true,
  "positions": {},
  "daily_stats": {
    "date": null,
    "trades_today": 0,
    "pnl_today": 0
  },
  "stats": {
    "cascades_detected": 0,
    "entries_taken": 0,
    "wins": 0,
    "losses": 0,
    "total_pnl_usd": 0,
    "avg_bounce_pct": 0
  },
  "history": []
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `cascade_threshold.price_drop_pct` | number | Min % drop in lookback period to flag cascade |
| `cascade_threshold.volume_spike_x` | number | Volume must be this multiple of average |
| `cascade_threshold.lookback_candles` | number | How many candles to check for the drop |
| `cooldown_candles` | number | Wait this many candles after cascade before entering |
| `entry_mode` | string | `"market"` (immediate) or `"limit_wick"` (place limit at wick low) |
| `tp_pct` | number | Take profit target as % bounce from entry |
| `sl_pct` | number | Stop loss as % below entry |

## Execution Flow

### Step 1 — Load State

Read state file. Stop if missing or disabled. Reset daily stats if new day.

### Step 2 — Detect Cascades

For each coin, fetch recent candles:
```json
{
  "query": "candles_snapshot",
  "coin": "<coin>",
  "interval": "<candle_interval>",
  "start_time_ms": "<lookback_start>",
  "end_time_ms": "<now>"
}
```

Detect cascade using `execute_code`:
```python
recent = candles[-lookback_candles:]
price_change = (recent[-1]["c"] - recent[0]["o"]) / recent[0]["o"] * 100

recent_vol = sum(c["v"] for c in recent) / len(recent)
avg_vol = sum(c["v"] for c in candles) / len(candles)
vol_ratio = recent_vol / max(avg_vol, 1)

# Large wicks indicate forced liquidations
wick_ratios = []
for c in recent:
    body = abs(c["c"] - c["o"])
    full_range = c["h"] - c["l"]
    if full_range > 0:
        wick_ratios.append(1 - body / full_range)

avg_wick = sum(wick_ratios) / len(wick_ratios)

is_cascade = (
    price_change <= -price_drop_pct  # significant drop
    and vol_ratio >= volume_spike_x   # volume surge
    and avg_wick > 0.5                # large wicks (liquidation signature)
)

# Cascade direction
cascade_direction = "long_liquidation" if price_change < 0 else "short_liquidation"
```

### Step 3 — Check Cooldown

After cascade detection, wait `cooldown_candles` before entering:
- If cascade just detected → record timestamp, set state to "cooling"
- If cooldown elapsed → ready to enter
- If price continued dropping during cooldown → abort (cascade not over)

**Stabilization check:** Last `cooldown_candles` should show decreasing volume and smaller candle ranges.

### Step 4 — Check Existing Positions

For tracked positions via `hyperliquid_info` `query="user_state"`:
- Position gone → TP/SL triggered, record outcome
- Still open → check time. If held > 2 hours without TP, market close (bounce didn't happen)

### Step 5 — Execute Entry

If cascade detected and cooldown passed:

**Market entry mode:**
```json
{
  "action": "bulk_orders",
  "coin": "<coin>",
  "grouping": "normalTpsl",
  "order_requests": [
    {
      "coin": "<coin>",
      "is_buy": true,
      "size": "<calculated>",
      "price": "<market_price>",
      "tif": "Ioc"
    },
    {
      "coin": "<coin>",
      "is_buy": false,
      "size": "<calculated>",
      "price": "<tp_price>",
      "tif": "Gtc",
      "tpsl": "tp",
      "trigger_px": "<tp_price>",
      "reduce_only": true
    },
    {
      "coin": "<coin>",
      "is_buy": false,
      "size": "<calculated>",
      "price": "<sl_price>",
      "tif": "Gtc",
      "tpsl": "sl",
      "trigger_px": "<sl_price>",
      "reduce_only": true
    }
  ]
}
```

**Limit wick entry mode:** Place a limit buy at the wick low of the cascade candle:
```json
{
  "action": "order",
  "coin": "<coin>",
  "is_buy": true,
  "size": "<calculated>",
  "price": "<wick_low>",
  "tif": "Gtc"
}
```

Dry-run first always.

### Step 6 — Report

```
Liquidation Sniper Report
═════════════════════════
BTC — No cascade detected (drop: -0.3%, vol: 1.1x)
ETH — CASCADE DETECTED | -2.8% in 30m | Vol: 4.2x | Wicks: 0.65
  Cooling down: 2/3 candles remaining
SOL — CASCADE FIRED → LONG entry @ $168.50
  TP: $171.03 (+1.5%) | SL: $166.82 (-1.0%)

Active: 1/2 | Today: 2/5
Cascades detected: 8 | Entries: 6 | Win rate: 67% | PnL: +$95.20
```

---

## Cronjob Setup

```
cronjob(
  action="create",
  name="liquidation-sniper",
  schedule="every 2m",
  skills=["trading/hyperliquid", "trading/liquidation-sniper"],
  prompt="Scan for liquidation cascades, manage cooldowns and positions, enter on qualified bounces.",
  deliver="origin"
)
```

Needs frequent scanning (1-5m) to catch cascades in real time.

---

## Safety

- Cooldown period prevents entering during active cascade (catching falling knife)
- Stabilization check confirms cascade is subsiding before entry
- Bracket orders (TP+SL) protect every position
- Time-based exit (2h max hold) prevents bag-holding failed bounces
- Daily trade limit prevents overtrading
- Contrarian strategy only — never follows the cascade direction
- Full Hyperliquid guardrail stack
