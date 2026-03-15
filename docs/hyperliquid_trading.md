# Hyperliquid Trading Integration

This document captures the implementation contract for Hermes Hyperliquid tools.

## Scope

- Markets: Perps + Spot
- Integration style: Official `hyperliquid-python-sdk`
- Tools:
  - `hyperliquid_info` (read-only)
  - `hyperliquid_trade` (guarded write actions)

## Endpoint model

Hyperliquid has two primary API paths:
- `POST /info` for reads
- `POST /exchange` for signed writes

The SDK abstracts nonce/signing and action encoding for write actions.

## Query contract (`hyperliquid_info`)

### Market data (no address needed)

| Query | Required params | SDK call |
|---|---|---|
| `all_mids` | - | `Info.all_mids()` |
| `l2_snapshot` | `coin` | `Info.l2_snapshot(coin)` |
| `candles_snapshot` | `coin, interval, start_time_ms, end_time_ms` | `Info.candles_snapshot(...)` |
| `meta_perp` | - | `Info.meta()` |
| `meta_spot` | - | `Info.spot_meta()` |
| `meta_and_asset_ctxs` | - | `Info.meta_and_asset_ctxs()` |
| `spot_meta_and_asset_ctxs` | - | `Info.spot_meta_and_asset_ctxs()` |
| `perp_dexs` | - | `Info.perp_dexs()` |
| `funding_history` | `coin, start_time_ms` | `Info.funding_history(...)` |
| `predicted_fundings` | - | `Info.post("/info", {"type": "predictedFundings"})` |

### User account (address required)

| Query | Required params | SDK call |
|---|---|---|
| `user_state` | `address` (or env fallback) | `Info.user_state(address)` |
| `spot_user_state` | `address` (or env fallback) | `Info.spot_user_state(address)` |
| `open_orders` | `address` (or env fallback) | `Info.open_orders(address)` |
| `frontend_open_orders` | `address` | `Info.frontend_open_orders(address)` |
| `order_status_oid` | `address, oid` | `Info.query_order_by_oid(address, oid)` |
| `order_status_cloid` | `address, cloid` | `Info.query_order_by_cloid(address, Cloid)` |
| `historical_orders` | `address` | `Info.historical_orders(address)` |
| `user_fills` | `address` | `Info.user_fills(address)` |
| `user_fills_by_time` | `address, start_time_ms` | `Info.user_fills_by_time(address, start, end?, aggregate?)` |
| `user_twap_slice_fills` | `address` | `Info.user_twap_slice_fills(address)` |
| `user_funding` | `address, start_time_ms` | `Info.user_funding_history(address, start, end?)` |
| `user_fees` | `address` | `Info.user_fees(address)` |
| `user_rate_limit` | `address` | `Info.user_rate_limit(address)` |
| `portfolio` | `address` | `Info.portfolio(address)` |
| `user_non_funding_ledger` | `address, start_time_ms` | `Info.user_non_funding_ledger_updates(address, start, end?)` |
| `query_sub_accounts` | `address` | `Info.query_sub_accounts(address)` |
| `extra_agents` | `address` | `Info.extra_agents(address)` |
| `referral_state` | `address` | `Info.query_referral_state(address)` |
| `user_vault_equities` | `address` | `Info.user_vault_equities(address)` |
| `user_staking_summary` | `address` | `Info.user_staking_summary(address)` |
| `user_staking_delegations` | `address` | `Info.user_staking_delegations(address)` |
| `user_staking_rewards` | `address` | `Info.user_staking_rewards(address)` |

## Action contract (`hyperliquid_trade`)

### Order management

| Action | Required params | SDK call |
|---|---|---|
| `order` | `coin,is_buy,size,price,tif` | `Exchange.order(...)` |
| `bulk_orders` | `order_requests[], grouping?` | `Exchange.bulk_orders(requests, grouping)` |
| `modify` | `oid,coin,is_buy,size,price,tif` | `Exchange.modify_order(...)` |
| `bulk_modify` | `order_requests[]` (each with oid) | `Exchange.bulk_modify_orders_new(...)` |
| `market_open` | `coin,is_buy,size` OR `coin,is_buy,notional_usd` | `Exchange.market_open(...)` |
| `market_close` | `coin` | `Exchange.market_close(...)` |

### Cancels

| Action | Required params | SDK call |
|---|---|---|
| `cancel` | `coin,oid` | `Exchange.cancel(...)` |
| `cancel_by_cloid` | `coin,cloid` | `Exchange.cancel_by_cloid(...)` |
| `bulk_cancel` | `cancel_requests[]` (coin+oid) | `Exchange.bulk_cancel(...)` |
| `bulk_cancel_by_cloid` | `cancel_requests[]` (coin+cloid) | `Exchange.bulk_cancel_by_cloid(...)` |
| `schedule_cancel` | `cancel_time_ms?` | `Exchange.schedule_cancel(...)` |

### TWAP

| Action | Required params | SDK call |
|---|---|---|
| `twap_order` | `coin,is_buy,size,duration_minutes` | Raw `_post_action(twapOrder)` |
| `twap_cancel` | `coin,twap_id` | Raw `_post_action(twapCancel)` |

### Leverage & margin

| Action | Required params | SDK call |
|---|---|---|
| `update_leverage` | `coin,leverage` | `Exchange.update_leverage(...)` |
| `update_isolated_margin` | `coin,margin_amount` | `Exchange.update_isolated_margin(...)` |

### Transfers

| Action | Required params | SDK call |
|---|---|---|
| `usd_transfer` | `amount,destination` | `Exchange.usd_transfer(...)` |
| `spot_transfer` | `amount,destination,token` | `Exchange.spot_transfer(...)` |
| `usd_class_transfer` | `amount,to_perp` | `Exchange.usd_class_transfer(...)` |
| `withdraw` | `amount,destination` | `Exchange.withdraw_from_bridge(...)` |

### Sub-accounts

| Action | Required params | SDK call |
|---|---|---|
| `create_sub_account` | `sub_account_name` | `Exchange.create_sub_account(...)` |
| `sub_account_transfer` | `sub_account_user,is_deposit,amount` | `Exchange.sub_account_transfer(...)` |
| `sub_account_spot_transfer` | `sub_account_user,is_deposit,token,amount` | `Exchange.sub_account_spot_transfer(...)` |

### Vaults

| Action | Required params | SDK call |
|---|---|---|
| `vault_transfer` | `vault_address,is_deposit,amount` | `Exchange.vault_usd_transfer(...)` |

### Agent / builder

| Action | Required params | SDK call |
|---|---|---|
| `approve_agent` | - | `Exchange.approve_agent()` |
| `approve_builder_fee` | `builder,max_fee_rate` | `Exchange.approve_builder_fee(...)` |

### Other

| Action | Required params | SDK call |
|---|---|---|
| `set_referrer` | `referral_code` | `Exchange.set_referrer(...)` |
| `token_delegate` | `validator,wei` | `Exchange.token_delegate(...)` |

## TP/SL via bulk_orders

Use `bulk_orders` with `grouping` to attach take-profit and stop-loss orders:

- `grouping="na"` — independent orders (default)
- `grouping="normalTpsl"` — first order is entry; subsequent TP/SL orders are linked
- `grouping="positionTpsl"` — TP/SL applied at position level

Each order in `order_requests` can include:
- `tpsl: "tp"` or `"sl"` — marks the order as a trigger order
- `trigger_px` — trigger price (defaults to `price` if omitted)
- `is_market_trigger` — `true` for market execution on trigger (default), `false` for limit
- `reduce_only` — should be `true` for TP/SL legs

## Coin mapping notes

- Perp examples: `BTC`, `ETH`
- Spot examples: `PURR/USDC`
- SDK resolves coin-to-asset internally (`Info.name_to_coin`, `Info.coin_to_asset`)
- Perp-only actions: `market_open`, `market_close`, `update_leverage`, `twap_order` — reject spot pairs (`invalid_market_type`)

## Guardrail model

### Defaults
- Network default: `testnet`
- `dry_run` default: `true` (works on both testnet and mainnet)
- Kill switch default: `true`
- Max notional default: `1000` USD

### Live execution gate
Live writes require:
1. `dry_run=false`
2. `confirm_execution=EXECUTE_LIVE_TRADE`
3. `HYPERLIQUID_KILL_SWITCH=false`

### Risk checks
- Symbol allowlist via `HYPERLIQUID_ALLOWED_COINS`
- Positive numeric validation for size/price/leverage
- Optional USD-notional input for `market_open` (`notional_usd`) is converted into base `size` using current mid price
- Notional preflight estimate and cap enforcement via `HYPERLIQUID_MAX_NOTIONAL_USD`
- `bulk_orders` sums notional across all orders in the array
- Transfer actions validate positive `amount`

### Guardrail coverage by action category

| Action Category | Coin allowlist | Notional check | Confirm required |
|---|---|---|---|
| `order`, `modify` | Yes | Yes | Yes |
| `bulk_orders` | Yes (each order) | Yes (sum) | Yes |
| `bulk_modify` | No | No | Yes |
| `market_open`, `market_close` | Yes | Yes | Yes |
| `cancel`, `cancel_by_cloid` | Yes | No | Yes |
| `bulk_cancel`, `bulk_cancel_by_cloid` | Yes (each) | No | Yes |
| `twap_order`, `twap_cancel` | Yes | Yes | Yes |
| `update_leverage` | Yes | No | Yes |
| `update_isolated_margin` | Yes | No | Yes |
| `usd_transfer`, `withdraw` | No | No | Yes |
| `spot_transfer` | No | No | Yes |
| `usd_class_transfer` | No | No | Yes |
| `create_sub_account` | No | No | Yes |
| `sub_account_transfer` | No | No | Yes |
| `vault_transfer` | No | No | Yes |
| `approve_agent`, `approve_builder_fee` | No | No | Yes |
| `set_referrer` | No | No | Yes |
| `token_delegate` | No | No | Yes |

### Threat model coverage
- Wrong symbol: allowlist rejection
- Oversized trade: notional limit rejection
- Wrong network default: testnet-by-default
- Confirmation bypass: explicit token required
- Emergency freeze: kill switch blocks live writes

## Environment variables

- `HYPERLIQUID_ACCOUNT_ADDRESS`
- `HYPERLIQUID_SECRET_KEY`
- `HYPERLIQUID_NETWORK` (`testnet|mainnet`)
- `HYPERLIQUID_VAULT_ADDRESS` (optional)
- `HYPERLIQUID_ALLOWED_COINS` (optional CSV)
- `HYPERLIQUID_MAX_NOTIONAL_USD` (default safe cap)
- `HYPERLIQUID_KILL_SWITCH` (default `true`)

## Response shape

All responses follow:

```json
{
  "success": true,
  "network": "testnet",
  "mode": "dry_run",
  "action_or_query": "order",
  "data": {},
  "error": null,
  "guardrail": {}
}
```

## Error codes

Guardrail and validation failures return deterministic `guardrail.error_code` values:

- `invalid_network`
- `missing_confirm`
- `kill_switch_on`
- `missing_action`
- `unknown_action`
- `unknown_query`
- `invalid_market_type`
- `coin_not_allowed`
- `missing_coin`
- `missing_is_buy`
- `invalid_tif`
- `invalid_slippage_bps`
- `invalid_size`
- `invalid_size_or_price`
- `invalid_size_or_notional`
- `invalid_notional_usd`
- `conflicting_size_and_notional`
- `invalid_leverage`
- `invalid_oid`
- `missing_cloid`
- `notional_limit_exceeded`
- `unable_to_estimate_notional`
- `missing_params`
- `missing_address`
- `missing_cancel_requests`
- `invalid_cancel_request`
- `missing_order_requests`
- `invalid_order_request`
- `invalid_grouping`
- `invalid_margin_amount`
- `invalid_duration`
- `missing_twap_id`
- `invalid_amount`
- `missing_destination`
- `missing_to_perp`
- `missing_sub_account_name`
- `missing_sub_account_user`
- `missing_is_deposit`
- `missing_token`
- `missing_vault_address`
- `missing_referral_code`
- `missing_validator`
- `invalid_wei`
- `invalid_cancel_time`
- `query_failed`
- `trade_failed`
- `empty_exchange_response`
