#!/usr/bin/env python3
"""
Hyperliquid tools for market/account reads and guarded trading actions.

This module registers two tools:
- hyperliquid_info: Read-only queries against Hyperliquid Info API.
- hyperliquid_trade: Trading actions with strict guardrails and live confirmation.
"""

import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from tools.registry import registry

TESTNET_API_URL = "https://api.hyperliquid-testnet.xyz"
MAINNET_API_URL = "https://api.hyperliquid.xyz"
LIVE_CONFIRM_TOKEN = "EXECUTE_LIVE_TRADE"
DEFAULT_MAX_NOTIONAL_USD = 1000.0
VALID_TIFS = {"Gtc", "Ioc", "Alo"}
VALID_GROUPINGS = {"na", "normalTpsl", "positionTpsl"}


def _sdk_available() -> bool:
    try:
        import eth_account  # noqa: F401
        from hyperliquid.exchange import Exchange  # noqa: F401
        from hyperliquid.info import Info  # noqa: F401
        return True
    except Exception:
        return False


def check_hyperliquid_requirements() -> bool:
    """Hyperliquid tools require the Python SDK and its signing deps."""
    return _sdk_available()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _network_config() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (network_name, base_url, error_message)."""
    network = (os.getenv("HYPERLIQUID_NETWORK") or "testnet").strip().lower()
    if network == "testnet":
        return network, TESTNET_API_URL, None
    if network == "mainnet":
        return network, MAINNET_API_URL, None
    return None, None, "HYPERLIQUID_NETWORK must be 'testnet' or 'mainnet'"


def _default_account_address() -> Optional[str]:
    value = (os.getenv("HYPERLIQUID_ACCOUNT_ADDRESS") or "").strip()
    return value if value else None


def _allowed_coins() -> Set[str]:
    raw = (os.getenv("HYPERLIQUID_ALLOWED_COINS") or "").strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _max_notional_limit() -> float:
    parsed = _safe_float(os.getenv("HYPERLIQUID_MAX_NOTIONAL_USD"))
    if parsed is None or parsed <= 0:
        return DEFAULT_MAX_NOTIONAL_USD
    return parsed


_INFO_CLIENTS: Dict[str, Any] = {}


def _get_info_client(base_url: str):
    if base_url in _INFO_CLIENTS:
        return _INFO_CLIENTS[base_url]
    from hyperliquid.info import Info

    client = Info(base_url, skip_ws=True)
    _INFO_CLIENTS[base_url] = client
    return client


def _create_exchange(base_url: str):
    secret_key = (os.getenv("HYPERLIQUID_SECRET_KEY") or "").strip()
    if not secret_key:
        raise ValueError("HYPERLIQUID_SECRET_KEY is required for live trading")

    import eth_account
    from hyperliquid.exchange import Exchange

    wallet = eth_account.Account.from_key(secret_key)
    account_address = _default_account_address() or wallet.address
    vault_address = (os.getenv("HYPERLIQUID_VAULT_ADDRESS") or "").strip() or None
    return Exchange(
        wallet=wallet,
        base_url=base_url,
        account_address=account_address,
        vault_address=vault_address,
    )


def _response(
    *,
    success: bool,
    network: str,
    mode: str,
    action_or_query: str,
    data: Optional[dict] = None,
    error: Optional[str] = None,
    guardrail: Optional[dict] = None,
) -> str:
    payload = {
        "success": success,
        "network": network,
        "mode": mode,
        "action_or_query": action_or_query,
        "data": data,
        "error": error,
        "guardrail": guardrail or {},
    }
    return json.dumps(payload, ensure_ascii=False)


def _guardrail_error(
    *,
    network: str,
    mode: str,
    action_or_query: str,
    code: str,
    message: str,
    extras: Optional[dict] = None,
) -> str:
    guardrail = {"passed": False, "error_code": code}
    if extras:
        guardrail.update(extras)
    return _response(
        success=False,
        network=network,
        mode=mode,
        action_or_query=action_or_query,
        error=message,
        guardrail=guardrail,
    )


def _validate_coin_allowlist(coin: str, allowed: Set[str]) -> bool:
    if not allowed:
        return True
    if coin in allowed:
        return True
    return coin.upper() in {x.upper() for x in allowed}


def _validate_positive_number(value: Any) -> Optional[float]:
    parsed = _safe_float(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _estimate_mid_price(info_client, coin: str) -> Optional[float]:
    try:
        mids = info_client.all_mids()
        canonical = info_client.name_to_coin.get(coin, coin)
        if canonical in mids:
            return _safe_float(mids[canonical])
        if coin in mids:
            return _safe_float(mids[coin])
        for key in (coin, canonical):
            key_lower = str(key).lower()
            for mid_key, mid_val in mids.items():
                if str(mid_key).lower() == key_lower:
                    return _safe_float(mid_val)
    except Exception:
        return None
    return None


def _estimate_position_size(info_client, address: str, coin: str) -> Optional[float]:
    try:
        state = info_client.user_state(address)
        for item in state.get("assetPositions", []):
            position = item.get("position", {})
            if position.get("coin") != coin:
                continue
            szi = _safe_float(position.get("szi"))
            if szi is None:
                continue
            return abs(szi)
    except Exception:
        return None
    return None


def _build_preflight(
    action: str,
    args: Dict[str, Any],
    info_client,
    address: Optional[str],
) -> Tuple[Optional[float], Optional[str], Dict[str, Any]]:
    """Return (estimated_notional, error_code, details)."""
    details: Dict[str, Any] = {}

    if action in {"order", "modify"}:
        size = _validate_positive_number(args.get("size"))
        price = _validate_positive_number(args.get("price"))
        if size is None or price is None:
            return None, "invalid_notional_inputs", details
        notional = abs(size * price)
        details["size"] = size
        details["price"] = price
        return notional, None, details

    if action == "market_open":
        size = _validate_positive_number(args.get("size"))
        if size is None:
            return None, "invalid_size", details
        est_price = _validate_positive_number(args.get("price"))
        if est_price is None:
            est_price = _estimate_mid_price(info_client, str(args.get("coin", "")))
        if est_price is None:
            return None, "unable_to_estimate_notional", details
        notional = abs(size * est_price)
        details["size"] = size
        details["price"] = est_price
        return notional, None, details

    if action == "market_close":
        size = _validate_positive_number(args.get("size"))
        if size is None:
            if not address:
                return None, "missing_account_address", details
            size = _estimate_position_size(info_client, address, str(args.get("coin", "")))
        if size is None or size <= 0:
            return None, "unable_to_estimate_notional", details

        est_price = _validate_positive_number(args.get("price"))
        if est_price is None:
            est_price = _estimate_mid_price(info_client, str(args.get("coin", "")))
        if est_price is None:
            return None, "unable_to_estimate_notional", details

        notional = abs(size * est_price)
        details["size"] = size
        details["price"] = est_price
        return notional, None, details

    if action == "bulk_orders":
        order_requests = args.get("order_requests") or []
        total_notional = 0.0
        for req in order_requests:
            sz = _validate_positive_number(req.get("size"))
            px = _validate_positive_number(req.get("price"))
            if sz is not None and px is not None:
                total_notional += abs(sz * px)
            elif sz is not None:
                coin_name = str(req.get("coin", ""))
                mid = _estimate_mid_price(info_client, coin_name)
                if mid:
                    total_notional += abs(sz * mid)
        if total_notional > 0:
            details["total_notional"] = total_notional
            return total_notional, None, details

    if action == "twap_order":
        size = _validate_positive_number(args.get("size"))
        if size is not None:
            coin_name = str(args.get("coin", ""))
            est_price = _estimate_mid_price(info_client, coin_name)
            if est_price:
                notional = abs(size * est_price)
                details["size"] = size
                details["price"] = est_price
                return notional, None, details

    return None, None, details


def _compute_tpsl_pnl(
    order_requests: List[Dict[str, Any]], grouping: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Estimate PnL for TP/SL grouped bulk_orders.

    Returns dict with tp_pnl_usd, sl_pnl_usd, risk_reward_ratio when
    the grouping is normalTpsl or positionTpsl and the orders contain
    a recognisable entry + TP/SL structure.
    """
    if grouping not in ("normalTpsl", "positionTpsl"):
        return None
    if not order_requests or len(order_requests) < 2:
        return None

    # First order is the entry
    entry = order_requests[0]
    entry_price = _safe_float(entry.get("price"))
    entry_size = _safe_float(entry.get("size"))
    is_buy = entry.get("is_buy")

    if entry_price is None or entry_size is None or is_buy is None:
        return None

    result: Dict[str, Any] = {
        "entry_price": entry_price,
        "entry_size": entry_size,
        "entry_notional_usd": round(entry_price * entry_size, 2),
        "is_long": bool(is_buy),
    }

    for req in order_requests[1:]:
        tpsl = req.get("tpsl")
        trigger_px = _safe_float(req.get("trigger_px")) or _safe_float(req.get("price"))
        if trigger_px is None or tpsl not in ("tp", "sl"):
            continue

        if is_buy:
            pnl = (trigger_px - entry_price) * entry_size
        else:
            pnl = (entry_price - trigger_px) * entry_size

        if tpsl == "tp":
            result["tp_price"] = trigger_px
            result["tp_pnl_usd"] = round(pnl, 2)
        elif tpsl == "sl":
            result["sl_price"] = trigger_px
            result["sl_pnl_usd"] = round(pnl, 2)

    if "tp_pnl_usd" in result and "sl_pnl_usd" in result and result["sl_pnl_usd"] != 0:
        result["risk_reward_ratio"] = round(
            abs(result["tp_pnl_usd"] / result["sl_pnl_usd"]), 2,
        )

    return result


def _build_order_type(req: Dict[str, Any]) -> dict:
    """Convert a flat order request dict into SDK order_type structure."""
    tpsl = req.get("tpsl")
    if tpsl in ("tp", "sl"):
        trigger_px = _safe_float(req.get("trigger_px")) or _safe_float(req.get("price"))
        is_market = req.get("is_market_trigger", True)
        return {"trigger": {"triggerPx": float(trigger_px), "isMarket": bool(is_market), "tpsl": tpsl}}
    tif = req.get("tif", "Gtc")
    return {"limit": {"tif": tif}}


# ---------------------------------------------------------------------------
# Address-required info query helper
# ---------------------------------------------------------------------------

def _require_address(network, query, resolved_address):
    if not resolved_address:
        return _response(
            success=False,
            network=network,
            mode="read_only",
            action_or_query=query,
            error="address is required (or set HYPERLIQUID_ACCOUNT_ADDRESS)",
            guardrail={"passed": False, "error_code": "missing_address"},
        )
    return None


# ===========================================================================
# INFO TOOL
# ===========================================================================

def hyperliquid_info(
    query: str,
    coin: Optional[str] = None,
    interval: Optional[str] = None,
    start_time_ms: Optional[int] = None,
    end_time_ms: Optional[int] = None,
    address: Optional[str] = None,
    oid: Optional[int] = None,
    cloid: Optional[str] = None,
    aggregate_by_time: Optional[bool] = None,
    task_id: Optional[str] = None,
) -> str:
    del task_id
    network, base_url, net_err = _network_config()
    if net_err:
        return _response(
            success=False,
            network="invalid",
            mode="read_only",
            action_or_query=query or "unknown",
            error=net_err,
            guardrail={"passed": False, "error_code": "invalid_network"},
        )

    try:
        info_client = _get_info_client(base_url)
        resolved_address = address or _default_account_address()

        # -- Market data (no address needed) --------------------------------
        if query == "all_mids":
            data = info_client.all_mids()
        elif query == "l2_snapshot":
            if not coin:
                return _response(
                    success=False, network=network, mode="read_only",
                    action_or_query=query, error="coin is required for l2_snapshot",
                    guardrail={"passed": False, "error_code": "missing_coin"},
                )
            data = info_client.l2_snapshot(coin)
        elif query == "candles_snapshot":
            if not coin or start_time_ms is None or end_time_ms is None or not interval:
                return _response(
                    success=False, network=network, mode="read_only",
                    action_or_query=query,
                    error="coin, interval, start_time_ms, end_time_ms are required",
                    guardrail={"passed": False, "error_code": "missing_params"},
                )
            data = info_client.candles_snapshot(coin, interval, int(start_time_ms), int(end_time_ms))
        elif query == "meta_perp":
            data = info_client.meta()
        elif query == "meta_spot":
            data = info_client.spot_meta()
        elif query == "meta_and_asset_ctxs":
            data = info_client.meta_and_asset_ctxs()
        elif query == "spot_meta_and_asset_ctxs":
            data = info_client.spot_meta_and_asset_ctxs()
        elif query == "perp_dexs":
            data = info_client.perp_dexs()
        elif query == "funding_history":
            if not coin or start_time_ms is None:
                return _response(
                    success=False, network=network, mode="read_only",
                    action_or_query=query,
                    error="coin and start_time_ms are required",
                    guardrail={"passed": False, "error_code": "missing_params"},
                )
            data = info_client.funding_history(coin, int(start_time_ms), int(end_time_ms) if end_time_ms else None)
        elif query == "predicted_fundings":
            data = info_client.post("/info", {"type": "predictedFundings"})

        # -- User account queries (address required) ------------------------
        elif query == "user_state":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_state(resolved_address)
        elif query == "spot_user_state":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.spot_user_state(resolved_address)
        elif query == "open_orders":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.open_orders(resolved_address)
        elif query == "frontend_open_orders":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.frontend_open_orders(resolved_address)
        elif query == "order_status_oid":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            if oid is None:
                return _response(
                    success=False, network=network, mode="read_only",
                    action_or_query=query, error="oid is required",
                    guardrail={"passed": False, "error_code": "missing_params"},
                )
            data = info_client.query_order_by_oid(resolved_address, int(oid))
        elif query == "order_status_cloid":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            if not cloid:
                return _response(
                    success=False, network=network, mode="read_only",
                    action_or_query=query, error="cloid is required",
                    guardrail={"passed": False, "error_code": "missing_params"},
                )
            from hyperliquid.utils.types import Cloid as HlCloid
            data = info_client.query_order_by_cloid(resolved_address, HlCloid.from_str(cloid))
        elif query == "user_fills":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_fills(resolved_address)
        elif query == "user_fills_by_time":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            if start_time_ms is None:
                return _response(
                    success=False, network=network, mode="read_only",
                    action_or_query=query, error="start_time_ms is required",
                    guardrail={"passed": False, "error_code": "missing_params"},
                )
            data = info_client.user_fills_by_time(
                resolved_address, int(start_time_ms),
                int(end_time_ms) if end_time_ms else None,
                bool(aggregate_by_time) if aggregate_by_time else False,
            )
        elif query == "user_funding":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            if start_time_ms is None:
                return _response(
                    success=False, network=network, mode="read_only",
                    action_or_query=query, error="start_time_ms is required",
                    guardrail={"passed": False, "error_code": "missing_params"},
                )
            data = info_client.user_funding_history(
                resolved_address, int(start_time_ms),
                int(end_time_ms) if end_time_ms else None,
            )
        elif query == "user_fees":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_fees(resolved_address)
        elif query == "user_rate_limit":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_rate_limit(resolved_address)
        elif query == "historical_orders":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.historical_orders(resolved_address)
        elif query == "user_twap_slice_fills":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_twap_slice_fills(resolved_address)
        elif query == "portfolio":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.portfolio(resolved_address)
        elif query == "query_sub_accounts":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.query_sub_accounts(resolved_address)
        elif query == "extra_agents":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.extra_agents(resolved_address)
        elif query == "referral_state":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.query_referral_state(resolved_address)
        elif query == "user_non_funding_ledger":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            if start_time_ms is None:
                return _response(
                    success=False, network=network, mode="read_only",
                    action_or_query=query, error="start_time_ms is required",
                    guardrail={"passed": False, "error_code": "missing_params"},
                )
            data = info_client.user_non_funding_ledger_updates(
                resolved_address, int(start_time_ms),
                int(end_time_ms) if end_time_ms else None,
            )
        elif query == "user_vault_equities":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_vault_equities(resolved_address)
        elif query == "user_staking_summary":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_staking_summary(resolved_address)
        elif query == "user_staking_delegations":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_staking_delegations(resolved_address)
        elif query == "user_staking_rewards":
            err = _require_address(network, query, resolved_address)
            if err:
                return err
            data = info_client.user_staking_rewards(resolved_address)
        else:
            return _response(
                success=False, network=network, mode="read_only",
                action_or_query=query or "unknown",
                error=f"Unknown query: {query}",
                guardrail={"passed": False, "error_code": "unknown_query"},
            )

        return _response(
            success=True, network=network, mode="read_only",
            action_or_query=query, data=data, guardrail={"passed": True},
        )
    except Exception as exc:
        return _response(
            success=False, network=network or "unknown", mode="read_only",
            action_or_query=query or "unknown",
            error=f"Info query failed: {type(exc).__name__}: {exc}",
            guardrail={"passed": False, "error_code": "query_failed"},
        )


# ===========================================================================
# TRADE TOOL
# ===========================================================================

def hyperliquid_trade(
    action: str,
    coin: Optional[str] = None,
    is_buy: Optional[bool] = None,
    size: Optional[float] = None,
    notional_usd: Optional[float] = None,
    price: Optional[float] = None,
    tif: Optional[str] = None,
    oid: Optional[int] = None,
    cloid: Optional[str] = None,
    cancel_requests: Optional[List[Dict[str, Any]]] = None,
    order_requests: Optional[List[Dict[str, Any]]] = None,
    grouping: Optional[str] = None,
    leverage: Optional[int] = None,
    is_cross: Optional[bool] = None,
    cancel_time_ms: Optional[int] = None,
    slippage_bps: Optional[float] = None,
    dry_run: bool = True,
    confirm_execution: Optional[str] = None,
    reduce_only: bool = False,
    address: Optional[str] = None,
    # Transfer params
    amount: Optional[float] = None,
    destination: Optional[str] = None,
    token: Optional[str] = None,
    to_perp: Optional[bool] = None,
    # Sub-account params
    sub_account_name: Optional[str] = None,
    sub_account_user: Optional[str] = None,
    is_deposit: Optional[bool] = None,
    # Vault params
    vault_address: Optional[str] = None,
    # Margin params
    margin_amount: Optional[float] = None,
    # TWAP params
    duration_minutes: Optional[int] = None,
    randomize: Optional[bool] = None,
    twap_id: Optional[int] = None,
    # Agent/builder params
    builder: Optional[str] = None,
    max_fee_rate: Optional[str] = None,
    # Referral
    referral_code: Optional[str] = None,
    # Staking
    validator: Optional[str] = None,
    wei: Optional[int] = None,
    is_undelegate: Optional[bool] = None,
    task_id: Optional[str] = None,
) -> str:
    del task_id

    network, base_url, net_err = _network_config()
    mode = "dry_run" if dry_run else "live"
    if net_err:
        return _guardrail_error(
            network="invalid", mode=mode,
            action_or_query=action or "unknown",
            code="invalid_network", message=net_err,
        )

    kill_switch = _env_bool("HYPERLIQUID_KILL_SWITCH", True)
    allowed = _allowed_coins()
    max_notional = _max_notional_limit()
    resolved_address = address or _default_account_address()
    action = (action or "").strip()
    effective_size: Optional[float] = size
    market_open_notional_usd: Optional[float] = None

    if not action:
        return _guardrail_error(
            network=network, mode=mode,
            action_or_query="unknown",
            code="missing_action", message="action is required",
        )

    supported = {
        # Order management
        "order", "bulk_orders", "modify", "bulk_modify",
        "market_open", "market_close",
        "cancel", "cancel_by_cloid", "bulk_cancel", "bulk_cancel_by_cloid",
        "schedule_cancel",
        # TWAP
        "twap_order", "twap_cancel",
        # Leverage & margin
        "update_leverage", "update_isolated_margin",
        # Transfers
        "usd_transfer", "spot_transfer", "usd_class_transfer", "withdraw",
        # Sub-accounts
        "create_sub_account", "sub_account_transfer", "sub_account_spot_transfer",
        # Vault
        "vault_transfer",
        # Agent / builder
        "approve_agent", "approve_builder_fee",
        # Referral & staking
        "set_referrer", "token_delegate",
    }
    if action not in supported:
        return _guardrail_error(
            network=network, mode=mode, action_or_query=action,
            code="unknown_action", message=f"Unknown action: {action}",
        )

    if not dry_run:
        if confirm_execution != LIVE_CONFIRM_TOKEN:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_confirm",
                message="Live execution requires confirm_execution to be set. Did you forget to include it?",
            )
        if kill_switch:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="kill_switch_on",
                message="HYPERLIQUID_KILL_SWITCH is enabled; live execution is blocked",
            )

    # -- Coin allowlist for actions that need a coin -----------------------
    coin_required_actions = {
        "order", "market_open", "market_close", "cancel", "cancel_by_cloid",
        "modify", "update_leverage", "update_isolated_margin", "twap_order", "twap_cancel",
    }
    if action in coin_required_actions:
        if not coin:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_coin", message=f"coin is required for action {action}",
            )
        if not _validate_coin_allowlist(coin, allowed):
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="coin_not_allowed",
                message=f"coin '{coin}' is not in HYPERLIQUID_ALLOWED_COINS",
                extras={"allowed_coins": sorted(list(allowed))},
            )

    # Perp-only actions reject spot pairs
    if action in {"market_open", "market_close", "update_leverage", "twap_order"} and coin and "/" in coin:
        return _guardrail_error(
            network=network, mode=mode, action_or_query=action,
            code="invalid_market_type",
            message=f"action '{action}' is perp-only; use perp symbol like 'ETH' or 'BTC' (not spot pair '{coin}')",
        )

    # -- bulk_cancel validation --------------------------------------------
    if action == "bulk_cancel":
        if not cancel_requests or not isinstance(cancel_requests, list):
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_cancel_requests",
                message="cancel_requests must be a non-empty list",
            )
        for req in cancel_requests:
            req_coin = str(req.get("coin", "")).strip()
            req_oid = _safe_int(req.get("oid"))
            if not req_coin or req_oid is None or req_oid <= 0:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_cancel_request",
                    message="each cancel request must include coin and positive oid",
                )
            if not _validate_coin_allowlist(req_coin, allowed):
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="coin_not_allowed",
                    message=f"coin '{req_coin}' is not in HYPERLIQUID_ALLOWED_COINS",
                    extras={"allowed_coins": sorted(list(allowed))},
                )

    # -- bulk_cancel_by_cloid validation -----------------------------------
    if action == "bulk_cancel_by_cloid":
        if not cancel_requests or not isinstance(cancel_requests, list):
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_cancel_requests",
                message="cancel_requests must be a non-empty list (each with coin and cloid)",
            )
        for req in cancel_requests:
            if not req.get("coin") or not req.get("cloid"):
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_cancel_request",
                    message="each cancel request must include coin and cloid",
                )

    # -- order / modify validation -----------------------------------------
    if action in {"order", "modify"}:
        if is_buy is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_is_buy", message=f"is_buy is required for action {action}",
            )
        if _validate_positive_number(size) is None or _validate_positive_number(price) is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_size_or_price",
                message="size and price must be positive numbers",
            )
        if action == "modify":
            if _safe_int(oid) is None or int(oid) <= 0:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_oid",
                    message="oid must be a positive integer for modify",
                )
        if not tif or tif not in VALID_TIFS:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_tif",
                message=f"tif must be one of {sorted(VALID_TIFS)}",
            )

    # -- bulk_orders validation --------------------------------------------
    if action == "bulk_orders":
        if not order_requests or not isinstance(order_requests, list):
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_order_requests",
                message="order_requests must be a non-empty list",
            )
        if grouping and grouping not in VALID_GROUPINGS:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_grouping",
                message=f"grouping must be one of {sorted(VALID_GROUPINGS)}",
            )
        for i, req in enumerate(order_requests):
            req_coin = str(req.get("coin", "")).strip()
            if not req_coin:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_order_request",
                    message=f"order_requests[{i}]: coin is required",
                )
            if not _validate_coin_allowlist(req_coin, allowed):
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="coin_not_allowed",
                    message=f"coin '{req_coin}' is not in HYPERLIQUID_ALLOWED_COINS",
                )
            if req.get("is_buy") is None:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_order_request",
                    message=f"order_requests[{i}]: is_buy is required",
                )
            if _validate_positive_number(req.get("size")) is None:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_order_request",
                    message=f"order_requests[{i}]: size must be a positive number",
                )
            if _validate_positive_number(req.get("price")) is None:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_order_request",
                    message=f"order_requests[{i}]: price must be a positive number",
                )

    # -- bulk_modify validation --------------------------------------------
    if action == "bulk_modify":
        if not order_requests or not isinstance(order_requests, list):
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_order_requests",
                message="order_requests must be a non-empty list (each with oid and order params)",
            )

    # -- market_open validation --------------------------------------------
    if action == "market_open":
        if is_buy is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_is_buy", message="is_buy is required for market_open",
            )
        parsed_size = _validate_positive_number(size) if size is not None else None
        parsed_notional = _validate_positive_number(notional_usd) if notional_usd is not None else None
        if size is not None and parsed_size is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_size", message="size must be a positive number when provided",
            )
        if notional_usd is not None and parsed_notional is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_notional_usd",
                message="notional_usd must be a positive number when provided",
            )
        if parsed_size is None and parsed_notional is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_size_or_notional",
                message="market_open requires either positive size or positive notional_usd",
            )
        if parsed_size is not None and parsed_notional is not None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="conflicting_size_and_notional",
                message="Provide either size or notional_usd for market_open, not both",
            )
        effective_size = parsed_size
        market_open_notional_usd = parsed_notional

    # -- cancel / cancel_by_cloid validation -------------------------------
    if action == "cancel":
        if _safe_int(oid) is None or int(oid) <= 0:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_oid", message="oid must be a positive integer for cancel",
            )

    if action == "cancel_by_cloid":
        if not cloid:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_cloid", message="cloid is required for cancel_by_cloid",
            )

    # -- update_leverage validation ----------------------------------------
    if action == "update_leverage":
        parsed_leverage = _safe_int(leverage)
        if parsed_leverage is None or parsed_leverage < 1 or parsed_leverage > 100:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_leverage",
                message="leverage must be an integer between 1 and 100",
            )

    # -- update_isolated_margin validation ---------------------------------
    if action == "update_isolated_margin":
        if margin_amount is None or _safe_float(margin_amount) is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_margin_amount",
                message="margin_amount is required (positive to add, negative to remove)",
            )

    # -- schedule_cancel validation ----------------------------------------
    if action == "schedule_cancel":
        if cancel_time_ms is not None:
            parsed_cancel_time = _safe_int(cancel_time_ms)
            if parsed_cancel_time is None or parsed_cancel_time <= 0:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_cancel_time",
                    message="cancel_time_ms must be a positive integer or null",
                )

    # -- twap_order validation ---------------------------------------------
    if action == "twap_order":
        if is_buy is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_is_buy", message="is_buy is required for twap_order",
            )
        if _validate_positive_number(size) is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_size", message="size must be a positive number",
            )
        parsed_duration = _safe_int(duration_minutes)
        if parsed_duration is None or parsed_duration < 1:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_duration",
                message="duration_minutes must be a positive integer",
            )

    if action == "twap_cancel":
        if twap_id is None or _safe_int(twap_id) is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_twap_id", message="twap_id is required for twap_cancel",
            )

    # -- Transfer validations ----------------------------------------------
    if action in {"usd_transfer", "usd_class_transfer", "withdraw"}:
        parsed_amount = _validate_positive_number(amount)
        if parsed_amount is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_amount", message="amount must be a positive number",
            )

    if action in {"usd_transfer", "withdraw"}:
        if not destination:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_destination", message="destination address is required",
            )

    if action == "spot_transfer":
        if not destination or not token:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_params",
                message="destination and token are required for spot_transfer",
            )
        parsed_amount = _validate_positive_number(amount)
        if parsed_amount is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_amount", message="amount must be a positive number",
            )

    if action == "usd_class_transfer":
        if to_perp is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_to_perp",
                message="to_perp is required (true=spot→perp, false=perp→spot)",
            )

    # -- Sub-account validations -------------------------------------------
    if action == "create_sub_account":
        if not sub_account_name:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_sub_account_name",
                message="sub_account_name is required",
            )

    if action in {"sub_account_transfer", "sub_account_spot_transfer"}:
        if not sub_account_user:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_sub_account_user",
                message="sub_account_user address is required",
            )
        if is_deposit is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_is_deposit",
                message="is_deposit is required (true=deposit to sub, false=withdraw from sub)",
            )
        parsed_amount = _validate_positive_number(amount)
        if parsed_amount is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_amount", message="amount must be a positive number",
            )
        if action == "sub_account_spot_transfer" and not token:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_token", message="token is required for sub_account_spot_transfer",
            )

    # -- Vault validation --------------------------------------------------
    if action == "vault_transfer":
        if not vault_address:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_vault_address", message="vault_address is required",
            )
        if is_deposit is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_is_deposit",
                message="is_deposit is required (true=deposit, false=withdraw)",
            )
        parsed_amount = _validate_positive_number(amount)
        if parsed_amount is None:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_amount", message="amount must be a positive number",
            )

    # -- approve_builder_fee validation ------------------------------------
    if action == "approve_builder_fee":
        if not builder or not max_fee_rate:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_params",
                message="builder address and max_fee_rate are required",
            )

    # -- set_referrer validation -------------------------------------------
    if action == "set_referrer":
        if not referral_code:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_referral_code", message="referral_code is required",
            )

    # -- token_delegate validation -----------------------------------------
    if action == "token_delegate":
        if not validator:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="missing_validator", message="validator address is required",
            )
        if wei is None or _safe_int(wei) is None or int(wei) <= 0:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_wei", message="wei must be a positive integer",
            )

    # -- Slippage validation (shared) --------------------------------------
    parsed_slippage_bps: Optional[float] = None
    if slippage_bps is not None:
        parsed_slippage_bps = _safe_float(slippage_bps)
        if parsed_slippage_bps is None or parsed_slippage_bps < 0 or parsed_slippage_bps > 1000:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="invalid_slippage_bps",
                message="slippage_bps must be between 0 and 1000",
            )

    # ======================================================================
    # Preflight & execution
    # ======================================================================
    try:
        info_client = _get_info_client(base_url)

        # -- market_open notional→size conversion --------------------------
        if action == "market_open" and effective_size is None:
            est_price = _validate_positive_number(price)
            if est_price is None:
                est_price = _estimate_mid_price(info_client, str(coin or ""))
            if est_price is None:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="unable_to_estimate_notional",
                    message="Unable to estimate price to convert notional_usd into size",
                )
            if market_open_notional_usd is None:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_size_or_notional",
                    message="market_open requires either size or notional_usd",
                )
            effective_size = market_open_notional_usd / est_price
            if effective_size <= 0:
                return _guardrail_error(
                    network=network, mode=mode, action_or_query=action,
                    code="invalid_size_or_notional",
                    message="Derived size from notional_usd is invalid",
                )

        # -- Preflight notional check --------------------------------------
        estimated_notional, preflight_err, details = _build_preflight(
            action=action,
            args={
                "coin": coin,
                "size": effective_size,
                "price": price,
                "order_requests": order_requests,
            },
            info_client=info_client,
            address=resolved_address,
        )
        if preflight_err:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code=preflight_err,
                message=f"Preflight failed: {preflight_err}",
                extras={"preflight": details},
            )
        if estimated_notional is not None and estimated_notional > max_notional:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="notional_limit_exceeded",
                message=(
                    f"Estimated notional {estimated_notional:.4f} exceeds "
                    f"HYPERLIQUID_MAX_NOTIONAL_USD={max_notional:.4f}"
                ),
                extras={
                    "estimated_notional_usd": estimated_notional,
                    "max_notional_usd": max_notional,
                },
            )

        preflight = {
            "estimated_notional_usd": estimated_notional,
            "max_notional_usd": max_notional,
            "details": details,
        }
        if action == "market_open":
            preflight["requested_notional_usd"] = market_open_notional_usd
            preflight["effective_size"] = effective_size

        # -- TP/SL PnL estimate for bulk_orders ----------------------------
        if action == "bulk_orders" and order_requests:
            tpsl_est = _compute_tpsl_pnl(order_requests, grouping)
            if tpsl_est:
                preflight["tpsl_estimates"] = tpsl_est

        # -- Dry-run response ----------------------------------------------
        if dry_run:
            would_execute: Dict[str, Any] = {"action": action}
            # Include all relevant params for the action
            for key, val in [
                ("coin", coin), ("is_buy", is_buy),
                ("size", effective_size), ("notional_usd", market_open_notional_usd),
                ("price", price), ("tif", tif), ("oid", oid), ("cloid", cloid),
                ("order_requests", order_requests), ("grouping", grouping),
                ("cancel_requests", cancel_requests),
                ("leverage", leverage), ("is_cross", is_cross),
                ("cancel_time_ms", cancel_time_ms),
                ("slippage_bps", slippage_bps), ("reduce_only", reduce_only),
                ("amount", amount), ("destination", destination),
                ("token", token), ("to_perp", to_perp),
                ("sub_account_name", sub_account_name),
                ("sub_account_user", sub_account_user),
                ("is_deposit", is_deposit), ("vault_address", vault_address),
                ("margin_amount", margin_amount),
                ("duration_minutes", duration_minutes),
                ("randomize", randomize), ("twap_id", twap_id),
                ("builder", builder), ("max_fee_rate", max_fee_rate),
                ("referral_code", referral_code),
                ("validator", validator), ("wei", wei),
                ("is_undelegate", is_undelegate),
            ]:
                if val is not None:
                    would_execute[key] = val

            return _response(
                success=True, network=network, mode=mode,
                action_or_query=action,
                data={
                    "dry_run": True,
                    "would_execute": would_execute,
                    "preflight": preflight,
                    "next_step": (
                        "Show the user a concise summary and ask YES/NO. "
                        "On YES, re-call with dry_run=false and "
                        "confirm_execution=EXECUTE_LIVE_TRADE. "
                        "Do NOT show the token to the user."
                    ),
                },
                guardrail={"passed": True},
            )

        # ==================================================================
        # LIVE EXECUTION
        # ==================================================================
        exchange = _create_exchange(base_url)
        slippage = (parsed_slippage_bps / 10000.0) if parsed_slippage_bps is not None else None
        execution_result: Any = None

        # -- Cloid helper --------------------------------------------------
        hl_cloid = None
        if cloid:
            from hyperliquid.utils.types import Cloid as HlCloid
            hl_cloid = HlCloid.from_str(cloid)

        # -- Order management ----------------------------------------------
        if action == "order":
            execution_result = exchange.order(
                coin, bool(is_buy), float(size), float(price),
                {"limit": {"tif": tif}},
                reduce_only=bool(reduce_only),
                cloid=hl_cloid,
            )
        elif action == "bulk_orders":
            sdk_requests = []
            for req in order_requests:
                sdk_req: Dict[str, Any] = {
                    "coin": req["coin"],
                    "is_buy": bool(req["is_buy"]),
                    "sz": float(req["size"]),
                    "limit_px": float(req["price"]),
                    "order_type": _build_order_type(req),
                    "reduce_only": bool(req.get("reduce_only", False)),
                }
                if req.get("cloid"):
                    from hyperliquid.utils.types import Cloid as HlCloid
                    sdk_req["cloid"] = HlCloid.from_str(req["cloid"])
                sdk_requests.append(sdk_req)
            execution_result = exchange.bulk_orders(
                sdk_requests,
                grouping=grouping or "na",
            )
        elif action == "modify":
            execution_result = exchange.modify_order(
                int(oid), coin, bool(is_buy), float(size), float(price),
                {"limit": {"tif": tif}},
                reduce_only=bool(reduce_only),
                cloid=hl_cloid,
            )
        elif action == "bulk_modify":
            sdk_modify_requests = []
            for req in order_requests:
                mod_req = {
                    "oid": int(req["oid"]) if "oid" in req else req.get("cloid"),
                    "order": {
                        "coin": req["coin"],
                        "is_buy": bool(req["is_buy"]),
                        "sz": float(req["size"]),
                        "limit_px": float(req["price"]),
                        "order_type": _build_order_type(req),
                        "reduce_only": bool(req.get("reduce_only", False)),
                    },
                }
                sdk_modify_requests.append(mod_req)
            execution_result = exchange.bulk_modify_orders_new(sdk_modify_requests)

        # -- Market orders -------------------------------------------------
        elif action == "market_open":
            kwargs: Dict[str, Any] = {}
            if price is not None:
                kwargs["px"] = float(price)
            if slippage is not None:
                kwargs["slippage"] = float(slippage)
            if hl_cloid is not None:
                kwargs["cloid"] = hl_cloid
            execution_result = exchange.market_open(
                coin, bool(is_buy), float(effective_size), **kwargs,
            )
        elif action == "market_close":
            kwargs = {}
            if size is not None:
                kwargs["sz"] = float(size)
            if price is not None:
                kwargs["px"] = float(price)
            if slippage is not None:
                kwargs["slippage"] = float(slippage)
            if hl_cloid is not None:
                kwargs["cloid"] = hl_cloid
            execution_result = exchange.market_close(coin, **kwargs)

        # -- Cancels -------------------------------------------------------
        elif action == "cancel":
            execution_result = exchange.cancel(coin, int(oid))
        elif action == "cancel_by_cloid":
            from hyperliquid.utils.types import Cloid as HlCloid
            execution_result = exchange.cancel_by_cloid(coin, HlCloid.from_str(cloid))
        elif action == "bulk_cancel":
            normalized = [{"coin": r["coin"], "oid": int(r["oid"])} for r in cancel_requests]
            execution_result = exchange.bulk_cancel(normalized)
        elif action == "bulk_cancel_by_cloid":
            from hyperliquid.utils.types import Cloid as HlCloid
            normalized = [{"coin": r["coin"], "cloid": HlCloid.from_str(r["cloid"])} for r in cancel_requests]
            execution_result = exchange.bulk_cancel_by_cloid(normalized)
        elif action == "schedule_cancel":
            execution_result = exchange.schedule_cancel(int(cancel_time_ms) if cancel_time_ms is not None else None)

        # -- TWAP ----------------------------------------------------------
        elif action == "twap_order":
            asset_id = info_client.name_to_asset(coin)
            twap_action = {
                "type": "twapOrder",
                "twap": {
                    "a": asset_id,
                    "b": bool(is_buy),
                    "s": str(float(size)),
                    "r": bool(reduce_only),
                    "m": int(duration_minutes),
                    "t": bool(randomize) if randomize is not None else True,
                },
            }
            execution_result = exchange._post_action(
                twap_action,
                signature=None,
                nonce=exchange._timestamp(),
            )
        elif action == "twap_cancel":
            asset_id = info_client.name_to_asset(coin)
            twap_cancel_action = {
                "type": "twapCancel",
                "a": asset_id,
                "t": int(twap_id),
            }
            execution_result = exchange._post_action(
                twap_cancel_action,
                signature=None,
                nonce=exchange._timestamp(),
            )

        # -- Leverage & margin ---------------------------------------------
        elif action == "update_leverage":
            execution_result = exchange.update_leverage(
                int(leverage), coin,
                is_cross=True if is_cross is None else bool(is_cross),
            )
        elif action == "update_isolated_margin":
            execution_result = exchange.update_isolated_margin(
                float(margin_amount), coin,
            )

        # -- Transfers -----------------------------------------------------
        elif action == "usd_transfer":
            execution_result = exchange.usd_transfer(float(amount), destination)
        elif action == "spot_transfer":
            execution_result = exchange.spot_transfer(float(amount), destination, token)
        elif action == "usd_class_transfer":
            execution_result = exchange.usd_class_transfer(float(amount), bool(to_perp))
        elif action == "withdraw":
            execution_result = exchange.withdraw_from_bridge(float(amount), destination)

        # -- Sub-accounts --------------------------------------------------
        elif action == "create_sub_account":
            execution_result = exchange.create_sub_account(sub_account_name)
        elif action == "sub_account_transfer":
            execution_result = exchange.sub_account_transfer(
                sub_account_user, bool(is_deposit), int(float(amount)),
            )
        elif action == "sub_account_spot_transfer":
            execution_result = exchange.sub_account_spot_transfer(
                sub_account_user, bool(is_deposit), token, float(amount),
            )

        # -- Vault ---------------------------------------------------------
        elif action == "vault_transfer":
            execution_result = exchange.vault_usd_transfer(
                vault_address, bool(is_deposit), int(float(amount)),
            )

        # -- Agent / builder -----------------------------------------------
        elif action == "approve_agent":
            execution_result = exchange.approve_agent()
        elif action == "approve_builder_fee":
            execution_result = exchange.approve_builder_fee(builder, max_fee_rate)

        # -- Referral & staking --------------------------------------------
        elif action == "set_referrer":
            execution_result = exchange.set_referrer(referral_code)
        elif action == "token_delegate":
            execution_result = exchange.token_delegate(
                validator, int(wei),
                is_undelegate=bool(is_undelegate) if is_undelegate is not None else False,
            )
        else:
            return _guardrail_error(
                network=network, mode=mode, action_or_query=action,
                code="unknown_action", message=f"Unknown action: {action}",
            )

        if execution_result is None:
            return _response(
                success=False, network=network, mode=mode,
                action_or_query=action,
                error="Exchange returned empty response (no state change confirmed)",
                guardrail={"passed": False, "error_code": "empty_exchange_response"},
            )

        return _response(
            success=True, network=network, mode=mode,
            action_or_query=action,
            data={"result": execution_result, "preflight": preflight},
            guardrail={"passed": True},
        )
    except Exception as exc:
        return _response(
            success=False, network=network or "unknown", mode=mode,
            action_or_query=action,
            error=f"Trade action failed: {type(exc).__name__}: {exc}",
            guardrail={"passed": False, "error_code": "trade_failed"},
        )


# ===========================================================================
# SCHEMAS
# ===========================================================================

HYPERLIQUID_INFO_SCHEMA = {
    "name": "hyperliquid_info",
    "description": (
        "Read Hyperliquid market and account data. Supports: prices, orderbook, candles, "
        "metadata, user state, positions, fills, orders, funding, staking, sub-accounts, and more."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "enum": [
                    # Market data
                    "all_mids", "l2_snapshot", "candles_snapshot",
                    "meta_perp", "meta_spot", "meta_and_asset_ctxs",
                    "spot_meta_and_asset_ctxs", "perp_dexs",
                    "funding_history", "predicted_fundings",
                    # User account
                    "user_state", "spot_user_state",
                    "open_orders", "frontend_open_orders",
                    "order_status_oid", "order_status_cloid",
                    "historical_orders",
                    "user_fills", "user_fills_by_time",
                    "user_twap_slice_fills",
                    "user_funding", "user_fees", "user_rate_limit",
                    "portfolio",
                    "user_non_funding_ledger",
                    # Sub-accounts & agents
                    "query_sub_accounts", "extra_agents",
                    "referral_state",
                    # Vaults & staking
                    "user_vault_equities",
                    "user_staking_summary", "user_staking_delegations",
                    "user_staking_rewards",
                ],
                "description": "Info query to execute.",
            },
            "coin": {"type": "string", "description": "Asset symbol, e.g. ETH or PURR/USDC."},
            "interval": {"type": "string", "description": "Candle interval (e.g., 1m, 5m, 1h)."},
            "start_time_ms": {"type": "integer", "description": "Start timestamp in milliseconds."},
            "end_time_ms": {"type": "integer", "description": "End timestamp in milliseconds."},
            "address": {"type": "string", "description": "Wallet/account address override."},
            "oid": {"type": "integer", "description": "Order id for order_status_oid."},
            "cloid": {"type": "string", "description": "Client order id for order_status_cloid."},
            "aggregate_by_time": {"type": "boolean", "description": "Aggregate fills by time for user_fills_by_time."},
        },
        "required": ["query"],
    },
}


HYPERLIQUID_TRADE_SCHEMA = {
    "name": "hyperliquid_trade",
    "description": (
        "Execute guarded Hyperliquid trading and account actions. "
        "Supports: orders (limit, market, bulk with TP/SL), TWAP, cancels, leverage, margin, "
        "transfers, sub-accounts, vaults, staking, and more. "
        "WORKFLOW: 1) Call with dry_run=true to preview. "
        "2) Show user a concise summary and ask YES/NO. "
        "3) On YES, call again with dry_run=false and confirm_execution set. "
        "NEVER ask the user to type the confirmation token — handle it internally."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    # Orders
                    "order", "bulk_orders", "modify", "bulk_modify",
                    "market_open", "market_close",
                    # Cancels
                    "cancel", "cancel_by_cloid",
                    "bulk_cancel", "bulk_cancel_by_cloid",
                    "schedule_cancel",
                    # TWAP
                    "twap_order", "twap_cancel",
                    # Leverage & margin
                    "update_leverage", "update_isolated_margin",
                    # Transfers
                    "usd_transfer", "spot_transfer",
                    "usd_class_transfer", "withdraw",
                    # Sub-accounts
                    "create_sub_account", "sub_account_transfer",
                    "sub_account_spot_transfer",
                    # Vault
                    "vault_transfer",
                    # Agent / builder
                    "approve_agent", "approve_builder_fee",
                    # Other
                    "set_referrer", "token_delegate",
                ],
                "description": "Action to execute.",
            },
            "coin": {"type": "string", "description": "Asset symbol (e.g., ETH, PURR/USDC)."},
            "is_buy": {"type": "boolean", "description": "true=buy/long, false=sell/short."},
            "size": {"type": "number", "description": "Order size in base asset units."},
            "notional_usd": {"type": "number", "description": "USD notional for market_open (use this OR size)."},
            "price": {"type": "number", "description": "Limit price or trigger price."},
            "tif": {"type": "string", "enum": ["Gtc", "Ioc", "Alo"], "description": "Time-in-force."},
            "oid": {"type": "integer", "description": "Order id for cancel/modify."},
            "cloid": {"type": "string", "description": "Client order id (16-byte hex) for order/modify/cancel_by_cloid."},
            "order_requests": {
                "type": "array",
                "description": (
                    "For bulk_orders: array of orders. First order is parent for TP/SL grouping. "
                    "For bulk_modify: array of modify requests (each with oid + order params). "
                    "Each item: {coin, is_buy, size, price, tif?, reduce_only?, tpsl?, trigger_px?, is_market_trigger?, cloid?}"
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "coin": {"type": "string"},
                        "is_buy": {"type": "boolean"},
                        "size": {"type": "number"},
                        "price": {"type": "number"},
                        "tif": {"type": "string"},
                        "reduce_only": {"type": "boolean"},
                        "tpsl": {"type": "string", "enum": ["tp", "sl"], "description": "Set to 'tp' or 'sl' for trigger orders."},
                        "trigger_px": {"type": "number", "description": "Trigger price for TP/SL orders."},
                        "is_market_trigger": {"type": "boolean", "description": "True for market trigger (default), false for limit trigger."},
                        "cloid": {"type": "string"},
                        "oid": {"type": "integer", "description": "Order id (for bulk_modify)."},
                    },
                },
            },
            "grouping": {
                "type": "string", "enum": ["na", "normalTpsl", "positionTpsl"],
                "description": "Order grouping for bulk_orders. normalTpsl=entry+TP/SL linked, positionTpsl=position-level TP/SL.",
            },
            "cancel_requests": {
                "type": "array",
                "description": "For bulk_cancel (coin+oid) or bulk_cancel_by_cloid (coin+cloid).",
                "items": {
                    "type": "object",
                    "properties": {
                        "coin": {"type": "string"},
                        "oid": {"type": "integer"},
                        "cloid": {"type": "string"},
                    },
                },
            },
            "leverage": {"type": "integer", "description": "Target leverage (1-100)."},
            "is_cross": {"type": "boolean", "description": "Cross margin mode (default true)."},
            "margin_amount": {"type": "number", "description": "Margin amount for update_isolated_margin (+add, -remove)."},
            "cancel_time_ms": {"type": "integer", "description": "Future cancel-all timestamp in ms (null to clear)."},
            "slippage_bps": {"type": "number", "description": "Slippage tolerance in basis points (0-1000)."},
            # TWAP
            "duration_minutes": {"type": "integer", "description": "TWAP duration in minutes."},
            "randomize": {"type": "boolean", "description": "Randomize TWAP execution (default true)."},
            "twap_id": {"type": "integer", "description": "TWAP order id for twap_cancel."},
            # Transfers
            "amount": {"type": "number", "description": "Transfer amount (USD or token units)."},
            "destination": {"type": "string", "description": "Destination address for transfers/withdraw."},
            "token": {"type": "string", "description": "Token name for spot_transfer/sub_account_spot_transfer."},
            "to_perp": {"type": "boolean", "description": "For usd_class_transfer: true=spot→perp, false=perp→spot."},
            # Sub-accounts
            "sub_account_name": {"type": "string", "description": "Name for create_sub_account."},
            "sub_account_user": {"type": "string", "description": "Sub-account address for transfers."},
            "is_deposit": {"type": "boolean", "description": "true=deposit to sub/vault, false=withdraw from sub/vault."},
            # Vault
            "vault_address": {"type": "string", "description": "Vault address for vault_transfer."},
            # Builder
            "builder": {"type": "string", "description": "Builder address for approve_builder_fee."},
            "max_fee_rate": {"type": "string", "description": "Max fee rate string for approve_builder_fee."},
            # Referral
            "referral_code": {"type": "string", "description": "Referral code for set_referrer."},
            # Staking
            "validator": {"type": "string", "description": "Validator address for token_delegate."},
            "wei": {"type": "integer", "description": "Amount in wei for token_delegate."},
            "is_undelegate": {"type": "boolean", "description": "true=undelegate, false=delegate (default)."},
            # Execution control
            "dry_run": {
                "type": "boolean",
                "description": (
                    "Default true (preview only). Set false to execute live. "
                    "When user confirms YES, set dry_run=false and confirm_execution together."
                ),
                "default": True,
            },
            "confirm_execution": {
                "type": "string",
                "description": (
                    "Internal confirmation token. Set to EXECUTE_LIVE_TRADE when user says YES. "
                    "NEVER show this token to the user or ask them to type it."
                ),
            },
            "reduce_only": {"type": "boolean", "description": "Reduce-only flag for order/modify."},
            "address": {"type": "string", "description": "Optional account address override."},
        },
        "required": ["action"],
    },
}


# ===========================================================================
# REGISTRY
# ===========================================================================

registry.register(
    name="hyperliquid_info",
    toolset="trading",
    schema=HYPERLIQUID_INFO_SCHEMA,
    handler=lambda args, **kw: hyperliquid_info(
        query=args.get("query", ""),
        coin=args.get("coin"),
        interval=args.get("interval"),
        start_time_ms=args.get("start_time_ms"),
        end_time_ms=args.get("end_time_ms"),
        address=args.get("address"),
        oid=args.get("oid"),
        cloid=args.get("cloid"),
        aggregate_by_time=args.get("aggregate_by_time"),
        task_id=kw.get("task_id"),
    ),
    check_fn=check_hyperliquid_requirements,
    requires_env=["HYPERLIQUID_ACCOUNT_ADDRESS"],
)

registry.register(
    name="hyperliquid_trade",
    toolset="trading",
    schema=HYPERLIQUID_TRADE_SCHEMA,
    handler=lambda args, **kw: hyperliquid_trade(
        action=args.get("action", ""),
        coin=args.get("coin"),
        is_buy=args.get("is_buy"),
        size=args.get("size"),
        notional_usd=args.get("notional_usd"),
        price=args.get("price"),
        tif=args.get("tif"),
        oid=args.get("oid"),
        cloid=args.get("cloid"),
        cancel_requests=args.get("cancel_requests"),
        order_requests=args.get("order_requests"),
        grouping=args.get("grouping"),
        leverage=args.get("leverage"),
        is_cross=args.get("is_cross"),
        cancel_time_ms=args.get("cancel_time_ms"),
        slippage_bps=args.get("slippage_bps"),
        dry_run=args.get("dry_run", True),
        confirm_execution=args.get("confirm_execution"),
        reduce_only=args.get("reduce_only", False),
        address=args.get("address"),
        amount=args.get("amount"),
        destination=args.get("destination"),
        token=args.get("token"),
        to_perp=args.get("to_perp"),
        sub_account_name=args.get("sub_account_name"),
        sub_account_user=args.get("sub_account_user"),
        is_deposit=args.get("is_deposit"),
        vault_address=args.get("vault_address"),
        margin_amount=args.get("margin_amount"),
        duration_minutes=args.get("duration_minutes"),
        randomize=args.get("randomize"),
        twap_id=args.get("twap_id"),
        builder=args.get("builder"),
        max_fee_rate=args.get("max_fee_rate"),
        referral_code=args.get("referral_code"),
        validator=args.get("validator"),
        wei=args.get("wei"),
        is_undelegate=args.get("is_undelegate"),
        task_id=kw.get("task_id"),
    ),
    check_fn=check_hyperliquid_requirements,
    requires_env=["HYPERLIQUID_SECRET_KEY", "HYPERLIQUID_ACCOUNT_ADDRESS"],
)
