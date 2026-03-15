---
name: momentum-scalper
description: Momentum-based scalping strategy on Hyperliquid. Detects strong short-term price moves via candle analysis and enters in the direction of momentum with tight stops and quick profit targets. Use this skill when the user wants momentum trading, breakout scalping, or trend-following on short timeframes.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, momentum, scalping, automation, strategy]
---

# Momentum Scalper Strategy

Detects strong directional momentum using recent candle data (volume spike + large body candles) and enters in the direction of the move. Uses tight risk:reward with quick exits.

## Tools Required

- `hyperliquid_info` — candles, prices, orderbook, positions
- `hyperliquid_trade` — market orders with TP/SL brackets
- `read_file` / `write_file` — state persistence
- `execute_code` — momentum scoring calculations

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. Safety is enforced by state-level limits (max_concurrent, max_trades_per_day, cooldown, sl_pct, enabled flag) and exchange guardrails (kill switch, notional cap, coin allowlist).

## State File

Location: `~/.hermes/strategies/momentum-scalper/state.json`

```json
{
  "strategy": "momentum-scalper",
  "version": "1.0.0",
  "coins": ["BTC", "ETH", "SOL"],
  "candle_interval": "5m",
  "lookback_candles": 12,
  "momentum_threshold": 2.0,
  "tp_pct": 0.5,
  "sl_pct": 0.25,
  "notional_per_trade_usd": 100,
  "max_concurrent": 2,
  "max_trades_per_day": 10,
  "cooldown_minutes": 15,
  "network": "testnet",
  "enabled": true,
  "positions": {},
  "daily_stats": {
    "date": null,
    "trades_today": 0,
    "pnl_today": 0
  },
  "stats": {
    "total_trades": 0,
    "wins": 0,
    "losses": 0,
    "total_pnl_usd": 0,
    "avg_hold_minutes": 0,
    "best_trade_usd": 0,
    "worst_trade_usd": 0
  },
  "history": []
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `coins` | string[] | Coins to scan for momentum |
| `candle_interval` | string | Candle size for momentum detection (`"5m"`, `"15m"`) |
| `lookback_candles` | number | How many candles to analyze |
| `momentum_threshold` | number | Minimum momentum score to trigger entry (std devs above average) |
| `tp_pct` | number | Take profit as % of entry price |
| `sl_pct` | number | Stop loss as % of entry price |
| `max_concurrent` | number | Max simultaneous scalp positions |
| `max_trades_per_day` | number | Daily trade limit (prevents overtrading) |
| `cooldown_minutes` | number | Min minutes between trades on same coin |

## Execution Flow

### Step 1 — Load State

Read state file. Stop if missing or disabled.

Reset `daily_stats` if date has changed (new day).

Check `daily_stats.trades_today < max_trades_per_day`. If limit hit, report and stop.

### Step 2 — Compute Momentum Score

For each coin, fetch recent candles via `hyperliquid_info`:
```json
{
  "query": "candles_snapshot",
  "coin": "<coin>",
  "interval": "<candle_interval>",
  "start_time_ms": "<lookback_period_start>",
  "end_time_ms": "<now>"
}
```

Compute momentum score using `execute_code`:
```python
# Body ratio: how much of the candle is body vs wick
body_ratios = [abs(c["c"] - c["o"]) / max(c["h"] - c["l"], 0.0001) for c in candles]

# Recent price change
recent_change_pct = (candles[-1]["c"] - candles[-3]["c"]) / candles[-3]["c"] * 100

# Volume surge: last 3 candles vs average
recent_vol = sum(c["v"] for c in candles[-3:]) / 3
avg_vol = sum(c["v"] for c in candles) / len(candles)
vol_ratio = recent_vol / max(avg_vol, 1)

# Directional consistency: how many of last 5 candles are same direction
last_5_dirs = [1 if c["c"] > c["o"] else -1 for c in candles[-5:]]
consistency = abs(sum(last_5_dirs)) / 5

# Composite momentum score
momentum = (abs(recent_change_pct) * vol_ratio * consistency)
direction = "long" if recent_change_pct > 0 else "short"
```

### Step 3 — Check Existing Positions

For each tracked position, call `hyperliquid_info` `query="user_state"`:

- If position no longer exists → TP or SL was triggered. Record outcome.
- If position still open and held longer than 30 minutes → consider market close (momentum likely exhausted).

### Step 4 — Entry Decision

For each coin with `momentum >= momentum_threshold`:

**Pre-checks:**
- No existing position in this coin
- Cooldown elapsed since last trade on this coin
- Active positions < `max_concurrent`
- `trades_today < max_trades_per_day`

**Entry with bracket order (TP + SL):**

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

Dry-run first. Execute if passed.

### Step 5 — Report

```
Momentum Scalper Report
═══════════════════════
Scanned: BTC, ETH, SOL

BTC — Momentum: 3.4 (STRONG BULLISH) | Vol ratio: 2.1x
  → LONG entry @ $97,500 | TP: $97,987 (+0.5%) | SL: $97,256 (-0.25%)

ETH — Momentum: 1.2 (below threshold)
  → No signal

SOL — Momentum: 0.8 (below threshold)
  → No signal

Active: 1/2 | Today: 3/10 trades | Daily PnL: +$12.40
Cumulative: 45 trades | 62% win rate | +$180.50 PnL
```

---

## Cronjob Setup

```
cronjob(
  action="create",
  name="momentum-scalper",
  schedule="every 5m",
  skills=["trading/hyperliquid", "trading/momentum-scalper"],
  prompt="Run momentum scan: score all coins, manage exits, enter qualified setups with bracket orders.",
  deliver="local"
)
```

Frequency should match `candle_interval`. For 5m candles, run every 5m.

---

## Safety

- Tight stop losses (default 0.25%) limit per-trade risk
- Bracket orders (TP+SL) placed atomically with entry — no unprotected positions
- Daily trade limit prevents overtrading
- Per-coin cooldown prevents chasing
- Max concurrent positions limit
- Momentum must clear threshold — no marginal entries
- Full Hyperliquid guardrail stack
