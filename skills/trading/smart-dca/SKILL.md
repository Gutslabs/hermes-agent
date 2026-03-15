---
name: smart-dca
description: Volatility-adjusted DCA strategy on Hyperliquid. Increases buy size during high volatility (dips) and decreases during low volatility (calm). Smarter capital deployment than fixed-amount DCA. Use this skill when the user wants intelligent DCA, volatility-weighted accumulation, or adaptive dollar-cost averaging.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, dca, volatility, automation, strategy]
---

# Smart DCA Strategy

Enhanced DCA that adapts buy size based on market conditions. Buys more aggressively during high-volatility dips (better prices) and reduces size during calm/elevated periods (preserves capital for better entries).

## Tools Required

- `hyperliquid_info` — candles, prices, positions
- `hyperliquid_trade` — market orders
- `read_file` / `write_file` — state persistence
- `execute_code` — volatility calculations

## Autonomous Execution

This skill runs autonomously via cron. **Do NOT ask for user confirmation.** After a successful dry-run, proceed directly to live execution without waiting for YES/NO. Safety is enforced by state-level limits (max_total_usd, max_buys, min/max amount clamps, enabled flag) and exchange guardrails (kill switch, notional cap, coin allowlist).

## State File

Location: `~/.hermes/strategies/smart-dca/state.json`

```json
{
  "strategy": "smart-dca",
  "version": "1.0.0",
  "coin": "BTC",
  "base_amount_usd": 50,
  "min_amount_usd": 10,
  "max_amount_usd": 200,
  "volatility_lookback": 24,
  "candle_interval": "1h",
  "vol_multiplier_low": 0.5,
  "vol_multiplier_high": 3.0,
  "fear_greed_mode": true,
  "max_total_usd": 10000,
  "max_buys": 200,
  "network": "testnet",
  "enabled": true,
  "stats": {
    "total_invested_usd": 0,
    "total_size": 0.0,
    "avg_entry_price": 0,
    "buy_count": 0,
    "capital_efficiency": 0,
    "last_buy_at": null,
    "last_price": null,
    "last_amount_usd": null,
    "last_volatility": null
  },
  "history": []
}
```

### Parameters

| Field | Type | Description |
|---|---|---|
| `coin` | string | Target coin |
| `base_amount_usd` | number | Baseline USD amount (adjusted by volatility) |
| `min_amount_usd` | number | Floor — never buy less than this |
| `max_amount_usd` | number | Ceiling — never buy more than this |
| `volatility_lookback` | number | Hours of candle data for vol calculation |
| `vol_multiplier_low` | number | Multiplier when vol is low (< 1 = buy less) |
| `vol_multiplier_high` | number | Multiplier when vol is high (> 1 = buy more) |
| `fear_greed_mode` | boolean | If true, also adjusts for price position relative to recent range |

## Execution Flow

### Step 1 — Load State

Read state file. Stop if missing or disabled.
Check `total_invested_usd < max_total_usd` and `buy_count < max_buys`.

### Step 2 — Compute Volatility

Fetch candles via `hyperliquid_info`:
```json
{
  "query": "candles_snapshot",
  "coin": "<coin>",
  "interval": "<candle_interval>",
  "start_time_ms": "<lookback_start>",
  "end_time_ms": "<now>"
}
```

Compute via `execute_code`:
```python
import statistics

closes = [c["c"] for c in candles]
returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]

# Realized volatility (annualized)
hourly_vol = statistics.stdev(returns)
annual_vol = hourly_vol * (8760 ** 0.5) * 100  # as percentage

# Percentile within recent history
vol_avg = statistics.mean([abs(r) for r in returns])
vol_recent = statistics.mean([abs(r) for r in returns[-6:]])
vol_ratio = vol_recent / max(vol_avg, 0.0001)

# Classify
if vol_ratio > 1.5:
    vol_regime = "high"
elif vol_ratio < 0.7:
    vol_regime = "low"
else:
    vol_regime = "normal"
```

### Step 3 — Compute Buy Amount

```python
# Base adjustment from volatility
if vol_regime == "high":
    vol_mult = vol_multiplier_high  # buy more during volatility (dips)
elif vol_regime == "low":
    vol_mult = vol_multiplier_low   # buy less during calm
else:
    vol_mult = 1.0

amount = base_amount_usd * vol_mult

# Fear/greed adjustment (optional)
if fear_greed_mode:
    high = max(c["h"] for c in candles)
    low = min(c["l"] for c in candles)
    current = closes[-1]
    range_position = (current - low) / max(high - low, 0.01)
    # 0 = at range low (fear), 1 = at range high (greed)
    # Buy more at range low, less at range high
    fear_mult = 1 + (1 - range_position)  # 1.0 to 2.0
    amount *= fear_mult

# Clamp
amount = max(min_amount_usd, min(amount, max_amount_usd))
```

### Step 4 — Execute Buy

1. Dry-run: `hyperliquid_trade` with `action="market_open"`, `notional_usd=<amount>`, `dry_run=true`
2. Execute live if passed
3. Update state with actual fill

### Step 5 — Compute Capital Efficiency

Compare smart DCA avg entry vs what fixed DCA would have achieved:
```python
# Capital efficiency = how much better/worse than fixed DCA
# If smart_avg < fixed_avg for longs → positive efficiency
fixed_avg = sum(h["price"] for h in history) / len(history)
smart_avg = stats["avg_entry_price"]
efficiency = (fixed_avg - smart_avg) / fixed_avg * 100
```

### Step 6 — Report

```
Smart DCA Buy #12
═════════════════
Coin: BTC | Price: $94,200
Volatility: HIGH (2.3x avg) | Range position: 0.22 (fear zone)
Adjustment: base $50 × 3.0 (vol) × 1.78 (fear) = $267 → capped at $200

Bought: 0.00212 BTC ($200)
Avg Entry: $96,150 | Total: $1,450 / $10,000
Capital efficiency: +2.3% vs fixed DCA
Network: testnet
```

---

## Cronjob Setup

```
cronjob(
  action="create",
  name="smart-dca-btc",
  schedule="every 4h",
  skills=["trading/hyperliquid", "trading/smart-dca"],
  prompt="Execute smart DCA: compute volatility, adjust buy size, execute, report with efficiency comparison.",
  deliver="origin"
)
```

---

## Comparison: Smart DCA vs Regular DCA

| Aspect | Regular DCA | Smart DCA |
|---|---|---|
| Buy amount | Fixed | Volatility-adjusted |
| Dip behavior | Same amount | Buys 2-3x more |
| Calm market | Same amount | Buys 0.5x (preserves capital) |
| Range bottom | Same amount | Fear multiplier adds more |
| Capital efficiency | Baseline | Typically +2-5% better avg entry |

---

## Safety

- `min_amount_usd` / `max_amount_usd` hard clamps prevent extreme sizing
- `max_total_usd` and `max_buys` strategy-level limits
- Full Hyperliquid guardrails on every trade
- Dry-run before every live execution
- Only buys — never shorts, never sells (accumulation only)
- Strategy kill switch
