---
name: hyperliquid
description: Trade perpetual futures and spot on Hyperliquid using plain English. Use this skill whenever the user mentions Hyperliquid, wants to open/close positions, place limit orders, check balances, manage leverage, transfer funds, stake HYPE, or do anything related to Hyperliquid DEX trading. Also use when the user wants a structured trading workflow with risk planning, position sizing, and post-trade review on Hyperliquid.
version: 3.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, execution, perps, spot, risk-management, guardrails]
---

# Hyperliquid Trading Skill

Turn plain-English trade requests into guarded Hyperliquid tool calls. This skill handles everything from quick "open a $50 BTC long" execution to disciplined multi-step trading workflows with thesis validation, risk budgeting, and post-trade review.

Two modes depending on user needs:

- **Quick Execution** — parse intent, dry-run preview, confirm, execute. Minimal friction.
- **Advisory Playbook** — structured workflow for thesis building, risk planning, execution design, and post-trade journaling. Triggers when the user asks for analysis, a trade plan, position sizing help, or says anything like "walk me through this trade."

Both modes share the same safety guarantees: every live action requires a dry-run preview first, then a single YES/NO confirmation.

## Tools

Only two tools exist for all Hyperliquid operations:

- `hyperliquid_info` — read-only queries (prices, positions, balances, orderbooks, metadata, funding, staking)
- `hyperliquid_trade` — write actions (orders, cancels, transfers, leverage, staking) with built-in dry-run support

Never use `execute_code` or Python wrappers. Always call these tools directly.

## Safety Architecture

Every trade flows through multiple guardrail layers before reaching the exchange.

**Dry-run first, always.** Call `hyperliquid_trade` with `dry_run=true` before any live action. Works on both testnet and mainnet. Returns preflight checks including notional value, guardrail pass/fail, and for bracket orders, estimated TP/SL PnL.

**Single confirmation flow.** After the dry-run, present one concise summary and ask YES/NO. On YES, set `dry_run=false` and `confirm_execution="EXECUTE_LIVE_TRADE"` internally. Never ask the user to type the confirmation token.

**Guardrail layers** (all configurable via environment):

| Guardrail | Default | Purpose |
|---|---|---|
| Kill switch (`HYPERLIQUID_KILL_SWITCH`) | `true` | Blocks all live actions when enabled |
| Max notional (`HYPERLIQUID_MAX_NOTIONAL_USD`) | `$1000` | Per-action USD cap |
| Coin allowlist (`HYPERLIQUID_ALLOWED_COINS`) | empty (all allowed) | Restrict tradeable symbols |
| Network (`HYPERLIQUID_NETWORK`) | `testnet` | Testnet-first by default |
| Mainnet dry-run (`HYPERLIQUID_MAINNET_ALLOW_DRY_RUN`) | `false` | Controls dry-run on mainnet |

When a guardrail blocks an action, explain which guardrail fired and propose a safe alternative. Never force execution past a guardrail.

## Core Rules

1. `size` = base asset quantity (e.g., BTC `size=0.0001`), never USD. For USD-denominated requests ("open $50 BTC long"), use `notional_usd`. Never send both together.
2. All coins on Hyperliquid are tradeable by default. No allowlist needed unless the user explicitly restricts.
3. For `grouping=normalTpsl` bracket orders, TP and SL sizes must match entry size (entry-linked bracket). Do not enlarge TP/SL to "full position" unless user explicitly requests it.
4. CLOID is optional. If used: `0x` + 32 hex chars. Default to `oid` for tracking/cancellation.
5. Query only data you need. "Close my ETH" needs `user_state`. "Open $50 BTC long" needs `all_mids` + `user_state`. Do not query everything for every request.

## Coin Conventions

- Bare symbol (ETH, BTC, HYPE) → **perp**
- Pair form (PURR/USDC) → **spot**
- Default to perp unless user explicitly says "spot"
- Always uppercase

## Capabilities

When user asks "what can you do on Hyperliquid?", respond with plain-text summary (no tool calls):

**Trading** — Market orders (long/short), limit orders (GTC/IOC/ALO), bracket orders with TP/SL, TWAP orders, modify/cancel orders, bulk operations.

**Account** — Positions, balances, open orders, order history, fills, funding payments, PnL, leverage management (cross/isolated), margin adjustments, fee tier, rate limits.

**Transfers** — Send USDC or spot tokens to any address, move funds between perp and spot wallets, bridge withdrawals.

**Sub-accounts** — Create named sub-accounts, transfer USD or spot tokens between main and subs.

**Vaults & Staking** — Deposit/withdraw to vaults, stake/unstake HYPE, view staking summary, delegations, and rewards.

**Market Data** — Live mid prices, orderbook snapshots, OHLCV candles, current and predicted funding rates, perp and spot metadata.

## Intent Mapping

### Orders & Positions

| User says | Action | Key params |
|---|---|---|
| "open long" / "buy" | `market_open` | `is_buy=true` |
| "open short" / "sell" | `market_open` | `is_buy=false` |
| "close position" | `market_close` | `coin` |
| "limit buy at $X" | `order` | `is_buy=true, price=X, tif=Gtc` |
| "modify order 123" | `modify` | `oid=123` |
| "buy ETH at 1900 with TP 2100 SL 1800" | `bulk_orders` | `grouping=normalTpsl` |
| "TWAP buy 1 ETH over 30 min" | `twap_order` | `duration_minutes=30` |
| "cancel TWAP 42" | `twap_cancel` | `twap_id=42` |

### Cancels

| User says | Action | Key params |
|---|---|---|
| "cancel order 123" | `cancel` | `oid=123` |
| "cancel by cloid" | `cancel_by_cloid` | `cloid` |
| "cancel all" | `schedule_cancel` | — |
| "cancel multiple" | `bulk_cancel` | `cancel_requests[]` |

### Leverage & Margin

| User says | Action | Key params |
|---|---|---|
| "set leverage 5x" | `update_leverage` | `leverage=5` |
| "add 50 margin to ETH" | `update_isolated_margin` | `margin_amount=50` |

### Transfers

| User says | Action | Key params |
|---|---|---|
| "transfer 100 USDC to 0x..." | `usd_transfer` | `amount=100, destination` |
| "send 10 PURR to 0x..." | `spot_transfer` | `amount, destination, token` |
| "move 500 to spot" | `usd_class_transfer` | `to_perp=false` |
| "move 500 to perp" | `usd_class_transfer` | `to_perp=true` |
| "withdraw 100 USDC" | `withdraw` | `amount, destination` |

### Sub-accounts

| User says | Action | Key params |
|---|---|---|
| "create sub trading-bot" | `create_sub_account` | `sub_account_name` |
| "deposit 100 to sub" | `sub_account_transfer` | `is_deposit=true` |
| "send PURR to sub" | `sub_account_spot_transfer` | `token, is_deposit=true` |

### Vaults & Staking

| User says | Action | Key params |
|---|---|---|
| "deposit 100 to vault 0x..." | `vault_transfer` | `vault_address, is_deposit=true` |
| "stake 1000 HYPE" | `token_delegate` | `validator, wei` |
| "unstake HYPE" | `token_delegate` | `is_undelegate=true` |

### Account Management

| User says | Action | Key params |
|---|---|---|
| "approve API agent" | `approve_agent` | — |
| "approve builder fee" | `approve_builder_fee` | `builder, max_fee_rate` |
| "set referral code" | `set_referrer` | `referral_code` |

### Info Queries

| User says | Query |
|---|---|
| "prices" / "mids" | `all_mids` |
| "orderbook for ETH" | `l2_snapshot` |
| "ETH candles 1h" | `candles_snapshot` |
| "perp metadata" | `meta_perp` |
| "spot metadata" | `meta_spot` |
| "funding rates" | `meta_and_asset_ctxs` |
| "predicted funding" | `predicted_fundings` |
| "my positions" | `user_state` |
| "my spot balances" | `spot_user_state` |
| "my open orders" | `open_orders` or `frontend_open_orders` |
| "check order 123" | `order_status_oid` |
| "my fills today" | `user_fills_by_time` |
| "my recent fills" | `user_fills` |
| "my funding payments" | `user_funding` |
| "my fees" | `user_fees` |
| "rate limit" | `user_rate_limit` |
| "order history" | `historical_orders` |
| "my portfolio" | `portfolio` |
| "my sub-accounts" | `query_sub_accounts` |
| "approved agents" | `extra_agents` |
| "referral status" | `referral_state` |
| "deposits/withdrawals" | `user_non_funding_ledger` |
| "vault equity" | `user_vault_equities` |
| "staking summary" | `user_staking_summary` |
| "staking delegations" | `user_staking_delegations` |
| "staking rewards" | `user_staking_rewards` |
| "TWAP fills" | `user_twap_slice_fills` |

---

## Quick Execution Flow

For straightforward trade requests. Three steps.

### Step 1 — Gather context

| Situation | Query |
|---|---|
| Need balance/positions | `user_state` |
| Need spot balances | `spot_user_state` |
| Need current price | `all_mids` |
| Need open orders | `open_orders` |
| Need leverage/market info | `meta_perp` or `meta_spot` |

### Step 2 — Preview and confirm

Call `hyperliquid_trade` with `dry_run=true`, then show one summary:

```
Action: market_open ETH long
Size: 0.02 ETH (~$50)
Leverage: 10x
Network: mainnet

Execute? (YES/NO)
```

For bracket orders, include TP/SL estimates from the dry-run:

```
Action: bulk_orders ETH long + TP + SL (normalTpsl)
Entry: 0.02 ETH @ $1900 (~$38)
TP: $2100 -> +$4.00
SL: $1800 -> -$2.00
R:R = 2.0
Network: testnet

Execute? (YES/NO)
```

One summary. One YES/NO. No multi-step confirmations.

### Step 3 — Execute or stop

- **YES** → `hyperliquid_trade` with `dry_run=false, confirm_execution="EXECUTE_LIVE_TRADE"`, then `user_state` to verify.
- **NO** → stop, no trade.

### Leverage handling (perps)

- User specifies leverage → `update_leverage` before the trade
- No leverage specified → use existing from `user_state`
- Notional exceeds collateral, no leverage specified → propose 10x in summary
- Cap by coin's max from `meta_perp`

---

## Advisory Playbook Flow

For structured analysis before trading. Triggers on: "walk me through," "analyze this trade," "help me plan," "position size for," or any request implying deliberation.

### Stage 1 — Pre-trade Framing

- **Market**: perp or spot
- **Thesis**: why this direction, why now
- **Timeframe**: scalp, intraday, swing, position
- **Invalidation**: the condition that kills the thesis
- **Hold duration**: hours, days, weeks

Pull context: `all_mids`, `l2_snapshot` (orderbook depth), `candles_snapshot` (structure), `meta_and_asset_ctxs` (funding bias for perps).

### Stage 2 — Risk Plan

Position size comes from risk budget, not conviction.

**Core limits:**
- Max risk per trade: 0.25% – 1.00% of equity
- Max open risk across positions: 2.00% of equity
- Max daily drawdown: 2.00% – 3.00% of equity
- Max weekly drawdown: 5.00% of equity

If daily max drawdown is hit, stop initiating new trades.

**Position sizing formula:**

```
stop_distance = abs(entry - stop)
risk_usd = equity * (risk_pct / 100)
size = risk_usd / stop_distance
notional = size * entry
```

Then cap by: account margin constraints, configured max notional, and liquidity quality (spread + depth).

**Leverage discipline:** Do not use leverage to increase risk beyond budget. Prefer lower leverage in volatile sessions. Use isolated margin when risk isolation is needed.

### Stage 3 — Execution Design

**Order type selection:**
- **Limit (GTC)**: default for controlled entries, reduced slippage
- **IOC**: immediate execution when momentum matters
- **ALO**: maker-only when queue priority is acceptable

**Slippage heuristics:**
- Calm market: 5–15 bps
- Moderate volatility: 15–35 bps
- High volatility: 35+ bps (consider avoiding market entry)

**Perp-specific:** Review funding before directional swings. Use reduce-only for defensive exits. Treat market close as high-slippage during thin liquidity.

**Spot-specific:** Prefer limit entries in low-liquidity pairs. Confirm quote/base symbol semantics.

Build a dry-run, verify preflight notional passes guardrails, check orderbook support near entry.

### Stage 4 — Commit Decision

If setup quality is weak or invalidation is unclear → recommend **no-trade**. A skipped trade is a good trade when the edge isn't there.

**No-trade criteria:**
- Invalidation is vague or too wide for budget
- Liquidity is insufficient for planned size
- Setup depends on hope rather than a testable condition
- Recent losses hit daily risk stop

If setup is valid, present the trade plan:

```
## Trade Plan
Instrument: ETH-PERP Long
Thesis: [setup type, why now, key levels]
Risk: [equity, risk budget, entry, stop, size, notional]
Execution: [order type, TIF, slippage assumption, guardrail status]
Management: [TP logic, SL logic, time exit]
Decision: Execute / Wait / Abort
```

Then dry-run, show summary, YES/NO.

### Stage 5 — Post-trade Review

After the trade closes, capture the outcome:

```
## Post-Trade Review
Symbol/Direction: ETH Long
Entry/Exit: $1900 / $2080
Realized PnL: +$3.60
Hold time: 14h

Process Quality (1-5):
  Plan: 4  |  Execution: 5  |  Risk discipline: 4

What happened: [market behavior vs expectation]
Best decision: [what went right]
Largest mistake: [what to improve]
Rule compliance: [entry rule-based? invalidation respected? impulse deviations?]

Keep: [what worked]
Change: [what to fix]
Next session focus: [one thing to improve]
```

This builds the feedback loop that separates systematic trading from gambling.

---

## Error Handling

| Error | Action |
|---|---|
| `notional_limit_exceeded` | Compute smaller size from max notional, propose retry |
| `coin_not_allowed` | Show allowed coins, ask user to pick one |
| `kill_switch_on` | Tell user kill switch is active; disable in env config |
| `missing_confirm` | You forgot `confirm_execution`. Retry with it set. |
| `invalid_size_or_price` | Check precision against `meta_perp`/`meta_spot`, retry |
| Exchange rejection | Report exact error, identify cause (validation vs liquidity), propose fix |

Never hide errors. Never retry without fixing the root cause.

## Response Format

1. **Parsed intent** — what you understood
2. **Context** — relevant numbers (price, balance, leverage)
3. **Summary** — proposed action with key parameters
4. **Confirmation** — YES/NO
5. **Result** — execution outcome or error explanation

For advisory mode, expand with thesis, risk math, and trade plan before confirmation.

## Plain-English Examples

**Read-only:**
- "Show my Hyperliquid positions and open orders."
- "What's my balance and current BTC price?"

**Open position:**
- "Open a $50 BTC long."
- "Short $100 ETH at 10x leverage."
- "Buy 0.0002 BTC at market."

**Bracket order:**
- "Buy ETH at 1900 with TP 2100 SL 1800."

**Close / cancel:**
- "Close my BTC position."
- "Cancel order 123456."
- "Cancel all open orders."

**Spot:**
- "Buy $25 of PURR/USDC on spot."

**Advisory:**
- "Walk me through a BTC long setup."
- "Help me size a position — I have $25k equity, want 0.5% risk, entry 2450, stop 2390."
- "Analyze whether I should short ETH here."

**Recommended user format for fastest execution:**
- Side (long/short or buy/sell)
- Coin (BTC, ETH, or pair like PURR/USDC)
- Notional in USD or explicit size
- Leverage if needed
