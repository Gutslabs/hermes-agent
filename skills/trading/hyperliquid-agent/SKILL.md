---
name: hyperliquid-agent
description: Hyperliquid execution skill that converts plain-English trade requests into guarded tool calls with single-confirmation flow.
version: 2.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [trading, hyperliquid, execution, perps, spot, guardrails]
    related_skills: [hyperliquid-advanced-playbook]
---

# Hyperliquid Agent (Execution)

Use this skill when the user wants to trade, transfer, manage accounts, or query data on Hyperliquid in plain English.

Primary goal: turn plain-English intent into correct `hyperliquid_info` / `hyperliquid_trade` calls with minimal friction.

## Capabilities overview

When the user asks "what can you do on Hyperliquid?" or similar, respond with a plain-text summary — do NOT make tool calls. Use this list:

```
Hyperliquid Trading Capabilities:

TRADING
- Market orders (long/short) with USD or size input
- Limit orders (GTC, IOC, ALO)
- Bulk orders with TP/SL grouping (entry + take-profit + stop-loss linked)
- TWAP orders (time-weighted over N minutes)
- Modify existing orders (by oid or cloid)
- Cancel single, bulk, or all orders

ACCOUNT
- View positions, balances, open orders, order history
- View fills, funding payments, PnL
- Set/change leverage (cross or isolated)
- Adjust isolated margin
- Check fee tier and rate limits

TRANSFERS
- Send USDC to any address
- Send spot tokens to any address
- Move USDC between perp <> spot wallets
- Withdraw from bridge

SUB-ACCOUNTS
- Create named sub-accounts
- Transfer USD or spot tokens to/from subs

VAULTS & STAKING
- Deposit/withdraw to vaults
- Stake/unstake HYPE tokens
- View staking summary, delegations, rewards

MARKET DATA
- Live mid prices for all assets
- Orderbook snapshots
- Candle/OHLCV data
- Funding rates (current + predicted)
- Perp and spot metadata

SAFETY
- All trades preview first (dry-run), then confirm YES/NO
- Notional cap per trade (configurable)
- Kill switch to block all live trades
- Optional coin allowlist
- All coins on Hyperliquid are tradeable by default
```

## Core rules

1. Only use `hyperliquid_info` and `hyperliquid_trade` for exchange actions.
2. `size` = base asset quantity (e.g. BTC `size=0.0001`), NOT USD value.
3. For USD-denominated requests ("open $50 BTC long"), use `notional_usd` in `hyperliquid_trade`. Never map USD directly into `size`.
4. Do not send both `size` and `notional_usd` together.
5. Live execution requires `dry_run=false` + `confirm_execution="EXECUTE_LIVE_TRADE"`. When user says YES, set these internally. Never ask the user to type the token.
6. If guardrails fail, explain why and propose a safe alternative. Do not force execution.
7. All coins listed on Hyperliquid are tradeable by default. No need to configure an allowlist unless the user explicitly wants to restrict trading to specific coins.
8. CLOID is optional. If used, it must be valid (`0x` + 32 hex chars). Use `oid` by default unless cloid-based tracking/cancel is explicitly needed.
9. Never use `execute_code` / Python wrappers for Hyperliquid actions. Always call `hyperliquid_info` / `hyperliquid_trade` directly.
10. For `grouping=normalTpsl`, TP and SL sizes must match entry size (entry-linked bracket). Do not enlarge TP/SL to "full position" unless user explicitly requests position-level behavior.

## Intent mapping

### Orders & positions

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
| "cancel order by cloid" | `cancel_by_cloid` | `cloid` |
| "cancel all" | `schedule_cancel` | - |
| "cancel multiple orders" | `bulk_cancel` | `cancel_requests[]` |

### Leverage & margin

| User says | Action | Key params |
|---|---|---|
| "set leverage 5x" | `update_leverage` | `leverage=5` |
| "add 50 margin to ETH" | `update_isolated_margin` | `margin_amount=50` |

### Transfers

| User says | Action | Key params |
|---|---|---|
| "transfer 100 USDC to 0x..." | `usd_transfer` | `amount=100, destination` |
| "send 10 PURR to 0x..." | `spot_transfer` | `amount, destination, token` |
| "move 500 USDC to spot" | `usd_class_transfer` | `to_perp=false` |
| "move 500 USDC to perp" | `usd_class_transfer` | `to_perp=true` |
| "withdraw 100 USDC" | `withdraw` | `amount, destination` |

### Sub-accounts

| User says | Action | Key params |
|---|---|---|
| "create sub-account trading-bot" | `create_sub_account` | `sub_account_name` |
| "deposit 100 to sub" | `sub_account_transfer` | `is_deposit=true` |
| "send PURR to sub" | `sub_account_spot_transfer` | `token, is_deposit=true` |

### Vaults & staking

| User says | Action | Key params |
|---|---|---|
| "deposit 100 to vault 0x..." | `vault_transfer` | `vault_address, is_deposit=true` |
| "stake 1000 HYPE" | `token_delegate` | `validator, wei` |
| "unstake HYPE" | `token_delegate` | `is_undelegate=true` |

### Account management

| User says | Action | Key params |
|---|---|---|
| "approve API agent" | `approve_agent` | - |
| "approve builder fee" | `approve_builder_fee` | `builder, max_fee_rate` |
| "set referral code" | `set_referrer` | `referral_code` |

### Info queries

| User says | Query | Key params |
|---|---|---|
| "show prices" / "mids" | `all_mids` | - |
| "orderbook for ETH" | `l2_snapshot` | `coin` |
| "ETH candles 1h" | `candles_snapshot` | `coin, interval, start/end` |
| "perp metadata" | `meta_perp` | - |
| "spot metadata" | `meta_spot` | - |
| "funding rates" | `meta_and_asset_ctxs` | - |
| "predicted funding" | `predicted_fundings` | - |
| "my positions" | `user_state` | - |
| "my spot balances" | `spot_user_state` | - |
| "my open orders" | `open_orders` or `frontend_open_orders` | - |
| "check order 123" | `order_status_oid` | `oid` |
| "my fills today" | `user_fills_by_time` | `start_time_ms` |
| "my recent fills" | `user_fills` | - |
| "my funding payments" | `user_funding` | `start_time_ms` |
| "my fees" | `user_fees` | - |
| "rate limit status" | `user_rate_limit` | - |
| "order history" | `historical_orders` | - |
| "my portfolio" | `portfolio` | - |
| "my sub-accounts" | `query_sub_accounts` | - |
| "approved agents" | `extra_agents` | - |
| "referral status" | `referral_state` | - |
| "my deposits/withdrawals" | `user_non_funding_ledger` | `start_time_ms` |
| "vault equity" | `user_vault_equities` | - |
| "staking summary" | `user_staking_summary` | - |
| "staking delegations" | `user_staking_delegations` | - |
| "staking rewards" | `user_staking_rewards` | - |
| "TWAP fills" | `user_twap_slice_fills` | - |
| "available DEXes" | `perp_dexs` | - |

Coin rules:
- Bare symbol (ETH, BTC, HYPE) -> perp
- Pair form (PURR/USDC) -> spot
- Default to perp unless user explicitly says "spot"
- Always uppercase
- All coins on Hyperliquid are tradeable — no allowlist needed

## Execution flow (3 steps)

### Step 1: Gather context (only what's needed)

Query only the info you actually need for the request:

| Situation | Query |
|---|---|
| Need account balance/positions | `user_state` |
| Need spot balances | `spot_user_state` |
| Need current price | `all_mids` |
| Need open orders | `open_orders` |
| Need leverage/market info | `meta_perp` or `meta_spot` |

Do NOT run all info queries for every request. For a simple "close my ETH position", `user_state` is enough. For "open $50 BTC long", `all_mids` + `user_state` is enough.

### Step 2: Preview and confirm

Call `hyperliquid_trade` with `dry_run=true` to get the preflight check. This works on both testnet and mainnet.

Then show a single concise summary:
```
Action: market_open ETH long
Size: 0.02 ETH (~$50)
Leverage: 10x
Network: mainnet

Execute? (YES/NO)
```

For TP/SL orders, the dry-run response includes `tpsl_estimates` with estimated PnL. Always show this in the summary:
```
Action: bulk_orders ETH long + TP + SL (normalTpsl)
Entry: 0.02 ETH @ $1900 (~$38)
TP: $2100 -> +$4.00
SL: $1800 -> -$2.00
R:R = 2.0
Network: testnet

Execute? (YES/NO)
```

Do NOT ask multiple confirmation questions. One summary, one YES/NO. That's it.

### Step 3: Execute or stop

- On **YES**: call `hyperliquid_trade` with `dry_run=false, confirm_execution="EXECUTE_LIVE_TRADE"`
- On **NO**: stop, no trade
- After execution: call `user_state` to verify and summarize what changed

## Leverage handling (perp only)

- If user specifies leverage -> set it with `update_leverage` before the trade
- If user doesn't specify leverage -> check current leverage from `user_state`, use existing
- If notional exceeds available collateral and no leverage specified -> propose 10x, show it in summary
- Cap leverage by coin's max from `meta_perp`

## Error handling

When a tool returns a guardrail error, handle it directly:

| Error code | Action |
|---|---|
| `notional_limit_exceeded` | Compute smaller size from max notional, propose retry |
| `coin_not_allowed` | Show allowed coins, ask user to pick one |
| `kill_switch_on` | Tell user kill switch is on, they need to disable it for live trading |
| `missing_confirm` | This means you forgot `confirm_execution`. Retry with it set. |
| `invalid_size_or_price` | Check inputs and retry with valid values |

Never hide guardrail failures. Never retry the same failing call without fixing the cause.

## Response format

Keep responses direct and operational:

1. **Parsed intent** — what you understood
2. **Summary** — key numbers (size, notional, leverage, network)
3. **Confirmation** — single YES/NO question
4. **Result** — execution outcome or error explanation

## Plain-English examples

See: `references/plain-english-examples.md`
