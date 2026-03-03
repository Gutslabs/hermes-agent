"""Tests for tools/hyperliquid_tool.py."""

import json

from tools import hyperliquid_tool as hlt


class DummyInfo:
    def __init__(self):
        self.name_to_coin = {"ETH": "ETH", "PURR/USDC": "PURR/USDC"}

    def all_mids(self):
        return {"ETH": "2500", "PURR/USDC": "0.20"}

    def user_state(self, address):
        del address
        return {
            "assetPositions": [
                {"position": {"coin": "ETH", "szi": "1.2"}},
            ]
        }

    def spot_user_state(self, address):
        del address
        return {"balances": []}

    def meta(self):
        return {"universe": [{"name": "ETH"}]}

    def spot_meta(self):
        return {"universe": []}

    def meta_and_asset_ctxs(self):
        return [{"universe": []}, []]

    def spot_meta_and_asset_ctxs(self):
        return [{"universe": []}, []]

    def l2_snapshot(self, coin):
        return {"coin": coin, "levels": []}

    def candles_snapshot(self, coin, interval, start, end):
        return [{"t": start, "o": "100"}]

    def open_orders(self, address):
        del address
        return []

    def frontend_open_orders(self, address):
        del address
        return []

    def query_order_by_oid(self, address, oid):
        return {"order": {"oid": oid}}

    def query_order_by_cloid(self, address, cloid):
        return {"order": {"cloid": str(cloid)}}

    def funding_history(self, coin, start, end=None):
        return [{"coin": coin, "time": start}]

    def user_fills(self, address):
        del address
        return [{"coin": "ETH", "sz": "0.1"}]

    def user_fills_by_time(self, address, start, end=None, aggregate=False):
        del address
        return [{"coin": "ETH", "time": start}]

    def user_funding_history(self, address, start, end=None):
        del address
        return [{"time": start}]

    def user_fees(self, address):
        del address
        return {"dailyUserVlm": "1000"}

    def user_rate_limit(self, address):
        del address
        return {"cumVlm": "500", "nRequestsUsed": 10}

    def historical_orders(self, address):
        del address
        return [{"oid": 1}]

    def user_twap_slice_fills(self, address):
        del address
        return []

    def portfolio(self, address):
        del address
        return {"portfolio": {}}

    def query_sub_accounts(self, address):
        del address
        return []

    def extra_agents(self, address):
        del address
        return []

    def query_referral_state(self, address):
        del address
        return {"referrer": None}

    def user_non_funding_ledger_updates(self, address, start, end=None):
        del address
        return [{"time": start}]

    def user_vault_equities(self, address):
        del address
        return []

    def user_staking_summary(self, address):
        del address
        return {"delegated": "0", "undelegating": "0"}

    def user_staking_delegations(self, address):
        del address
        return []

    def user_staking_rewards(self, address):
        del address
        return []

    def perp_dexs(self):
        return []

    def post(self, path, body):
        return [{"asset": 0, "fundingRate": "0.0001"}]

    def name_to_asset(self, coin):
        return 0


class DummyExchange:
    def __init__(self):
        self.calls = []

    def order(self, *args, **kwargs):
        self.calls.append(("order", args, kwargs))
        return {"status": "ok", "action": "order"}

    def modify_order(self, *args, **kwargs):
        self.calls.append(("modify_order", args, kwargs))
        return {"status": "ok", "action": "modify_order"}

    def cancel(self, *args, **kwargs):
        self.calls.append(("cancel", args, kwargs))
        return {"status": "ok", "action": "cancel"}

    def cancel_by_cloid(self, *args, **kwargs):
        self.calls.append(("cancel_by_cloid", args, kwargs))
        return {"status": "ok", "action": "cancel_by_cloid"}

    def market_open(self, *args, **kwargs):
        self.calls.append(("market_open", args, kwargs))
        return {"status": "ok", "action": "market_open"}

    def market_close(self, *args, **kwargs):
        self.calls.append(("market_close", args, kwargs))
        return {"status": "ok", "action": "market_close"}

    def bulk_orders(self, *args, **kwargs):
        self.calls.append(("bulk_orders", args, kwargs))
        return {"status": "ok", "action": "bulk_orders"}

    def bulk_cancel(self, *args, **kwargs):
        self.calls.append(("bulk_cancel", args, kwargs))
        return {"status": "ok", "action": "bulk_cancel"}

    def bulk_cancel_by_cloid(self, *args, **kwargs):
        self.calls.append(("bulk_cancel_by_cloid", args, kwargs))
        return {"status": "ok", "action": "bulk_cancel_by_cloid"}

    def bulk_modify_orders_new(self, *args, **kwargs):
        self.calls.append(("bulk_modify_orders_new", args, kwargs))
        return {"status": "ok", "action": "bulk_modify"}

    def update_leverage(self, *args, **kwargs):
        self.calls.append(("update_leverage", args, kwargs))
        return {"status": "ok", "action": "update_leverage"}

    def update_isolated_margin(self, *args, **kwargs):
        self.calls.append(("update_isolated_margin", args, kwargs))
        return {"status": "ok", "action": "update_isolated_margin"}

    def schedule_cancel(self, *args, **kwargs):
        self.calls.append(("schedule_cancel", args, kwargs))
        return {"status": "ok", "action": "schedule_cancel"}

    def usd_transfer(self, *args, **kwargs):
        self.calls.append(("usd_transfer", args, kwargs))
        return {"status": "ok", "action": "usd_transfer"}

    def spot_transfer(self, *args, **kwargs):
        self.calls.append(("spot_transfer", args, kwargs))
        return {"status": "ok", "action": "spot_transfer"}

    def usd_class_transfer(self, *args, **kwargs):
        self.calls.append(("usd_class_transfer", args, kwargs))
        return {"status": "ok", "action": "usd_class_transfer"}

    def withdraw_from_bridge(self, *args, **kwargs):
        self.calls.append(("withdraw_from_bridge", args, kwargs))
        return {"status": "ok", "action": "withdraw"}

    def create_sub_account(self, *args, **kwargs):
        self.calls.append(("create_sub_account", args, kwargs))
        return {"status": "ok", "action": "create_sub_account"}

    def sub_account_transfer(self, *args, **kwargs):
        self.calls.append(("sub_account_transfer", args, kwargs))
        return {"status": "ok", "action": "sub_account_transfer"}

    def sub_account_spot_transfer(self, *args, **kwargs):
        self.calls.append(("sub_account_spot_transfer", args, kwargs))
        return {"status": "ok", "action": "sub_account_spot_transfer"}

    def vault_usd_transfer(self, *args, **kwargs):
        self.calls.append(("vault_usd_transfer", args, kwargs))
        return {"status": "ok", "action": "vault_transfer"}

    def approve_agent(self, *args, **kwargs):
        self.calls.append(("approve_agent", args, kwargs))
        return {"status": "ok", "action": "approve_agent"}

    def approve_builder_fee(self, *args, **kwargs):
        self.calls.append(("approve_builder_fee", args, kwargs))
        return {"status": "ok", "action": "approve_builder_fee"}

    def set_referrer(self, *args, **kwargs):
        self.calls.append(("set_referrer", args, kwargs))
        return {"status": "ok", "action": "set_referrer"}

    def token_delegate(self, *args, **kwargs):
        self.calls.append(("token_delegate", args, kwargs))
        return {"status": "ok", "action": "token_delegate"}

    def _post_action(self, action, signature=None, nonce=None):
        self.calls.append(("_post_action", (action,), {"signature": signature, "nonce": nonce}))
        return {"status": "ok", "action": action.get("type", "unknown")}

    def _timestamp(self):
        return 1700000000000


class DummyExchangeWithEmptyClose(DummyExchange):
    def market_close(self, *args, **kwargs):
        self.calls.append(("market_close", args, kwargs))
        return None


# ===========================================================================
# INFO TOOL TESTS
# ===========================================================================

class TestHyperliquidInfo:
    def test_all_mids_query(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_info(query="all_mids"))
        assert result["success"] is True
        assert result["action_or_query"] == "all_mids"
        assert "ETH" in result["data"]

    def test_missing_query_params(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_info(query="l2_snapshot"))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_coin"

    def test_unknown_query(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_info(query="nonexistent_query"))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "unknown_query"

    def test_meta_and_asset_ctxs(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_info(query="meta_and_asset_ctxs"))
        assert result["success"] is True

    def test_spot_meta_and_asset_ctxs(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_info(query="spot_meta_and_asset_ctxs"))
        assert result["success"] is True

    def test_perp_dexs(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_info(query="perp_dexs"))
        assert result["success"] is True

    def test_predicted_fundings(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_info(query="predicted_fundings"))
        assert result["success"] is True

    def test_frontend_open_orders(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="frontend_open_orders"))
        assert result["success"] is True

    def test_frontend_open_orders_requires_address(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.delenv("HYPERLIQUID_ACCOUNT_ADDRESS", raising=False)

        result = json.loads(hlt.hyperliquid_info(query="frontend_open_orders"))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_address"

    def test_user_fills(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_fills"))
        assert result["success"] is True
        assert len(result["data"]) == 1

    def test_user_fills_by_time(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(
            query="user_fills_by_time", start_time_ms=1000000,
        ))
        assert result["success"] is True

    def test_user_fills_by_time_requires_start(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_fills_by_time"))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_params"

    def test_user_funding(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(
            query="user_funding", start_time_ms=1000000,
        ))
        assert result["success"] is True

    def test_user_funding_requires_start(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_funding"))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_params"

    def test_user_fees(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_fees"))
        assert result["success"] is True

    def test_user_rate_limit(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_rate_limit"))
        assert result["success"] is True

    def test_historical_orders(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="historical_orders"))
        assert result["success"] is True

    def test_user_twap_slice_fills(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_twap_slice_fills"))
        assert result["success"] is True

    def test_portfolio(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="portfolio"))
        assert result["success"] is True

    def test_query_sub_accounts(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="query_sub_accounts"))
        assert result["success"] is True

    def test_extra_agents(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="extra_agents"))
        assert result["success"] is True

    def test_referral_state(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="referral_state"))
        assert result["success"] is True

    def test_user_non_funding_ledger(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(
            query="user_non_funding_ledger", start_time_ms=1000000,
        ))
        assert result["success"] is True

    def test_user_non_funding_ledger_requires_start(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_non_funding_ledger"))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_params"

    def test_user_vault_equities(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_vault_equities"))
        assert result["success"] is True

    def test_user_staking_summary(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_staking_summary"))
        assert result["success"] is True

    def test_user_staking_delegations(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_staking_delegations"))
        assert result["success"] is True

    def test_user_staking_rewards(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="user_staking_rewards"))
        assert result["success"] is True

    def test_order_status_oid_requires_oid(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_info(query="order_status_oid"))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_params"


# ===========================================================================
# TRADE TOOL TESTS
# ===========================================================================

class TestHyperliquidTrade:
    def test_dry_run_order_does_not_execute(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())

        def _should_not_call(*args, **kwargs):
            raise AssertionError("exchange should not be created in dry_run")

        monkeypatch.setattr(hlt, "_create_exchange", _should_not_call)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "true")

        result = json.loads(hlt.hyperliquid_trade(
            action="order",
            coin="ETH",
            is_buy=True,
            size=0.2,
            price=2400,
            tif="Gtc",
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["mode"] == "dry_run"
        assert result["data"]["dry_run"] is True

    def test_live_requires_confirmation(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="order",
            coin="ETH",
            is_buy=True,
            size=0.2,
            price=2400,
            tif="Gtc",
            dry_run=False,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_confirm"

    def test_mainnet_dry_run_works(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "mainnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="market_open",
            coin="ETH",
            is_buy=True,
            size=0.01,
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["mode"] == "dry_run"
        assert result["network"] == "mainnet"

    def test_kill_switch_blocks_live(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "true")

        result = json.loads(hlt.hyperliquid_trade(
            action="order",
            coin="ETH",
            is_buy=True,
            size=0.2,
            price=2400,
            tif="Gtc",
            dry_run=False,
            confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "kill_switch_on"

    def test_allowlist_rejects_coin(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ALLOWED_COINS", "BTC")

        result = json.loads(hlt.hyperliquid_trade(
            action="order",
            coin="ETH",
            is_buy=True,
            size=0.1,
            price=2000,
            tif="Gtc",
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "coin_not_allowed"

    def test_notional_limit_rejection(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "100")

        result = json.loads(hlt.hyperliquid_trade(
            action="order",
            coin="ETH",
            is_buy=True,
            size=1.0,
            price=2500.0,
            tif="Gtc",
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "notional_limit_exceeded"

    def test_market_open_notional_usd_derives_size_in_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "1000")

        result = json.loads(hlt.hyperliquid_trade(
            action="market_open",
            coin="ETH",
            is_buy=True,
            notional_usd=25.0,
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["data"]["would_execute"]["size"] == 0.01
        assert result["data"]["would_execute"]["notional_usd"] == 25.0
        assert result["data"]["preflight"]["effective_size"] == 0.01
        assert result["data"]["preflight"]["requested_notional_usd"] == 25.0

    def test_market_open_notional_usd_executes_live_with_derived_size(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "1000")

        result = json.loads(hlt.hyperliquid_trade(
            action="market_open",
            coin="ETH",
            is_buy=True,
            notional_usd=25.0,
            slippage_bps=20,
            dry_run=False,
            confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "market_open"
        assert exchange.calls[0][1][2] == 0.01

    def test_market_open_notional_usd_normalizes_size_to_coin_precision(self, monkeypatch):
        class PrecisionInfo(DummyInfo):
            def __init__(self):
                super().__init__()
                self.coin_to_asset = {"ETH": 0}
                self.asset_to_sz_decimals = {0: 4}

            def all_mids(self):
                return {"ETH": "2027"}

        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: PrecisionInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "1000")

        result = json.loads(hlt.hyperliquid_trade(
            action="market_open",
            coin="ETH",
            is_buy=True,
            notional_usd=30.0,
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["data"]["would_execute"]["size"] == 0.0148
        assert result["data"]["preflight"]["effective_size"] == 0.0148

    def test_market_open_rejects_conflicting_size_and_notional(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="market_open",
            coin="ETH",
            is_buy=True,
            size=0.01,
            notional_usd=25.0,
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "conflicting_size_and_notional"

    def test_market_open_rejects_spot_pair_coin(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="market_open",
            coin="ETH/USDC",
            is_buy=True,
            notional_usd=25.0,
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_market_type"

    def test_live_modify_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "5000")

        result = json.loads(hlt.hyperliquid_trade(
            action="modify",
            coin="ETH",
            oid=42,
            is_buy=False,
            size=0.4,
            price=2600,
            tif="Ioc",
            dry_run=False,
            confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert result["mode"] == "live"
        assert exchange.calls[0][0] == "modify_order"

    def test_response_shape_on_unknown_action(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(action="bad_action"))
        assert set(result.keys()) == {
            "success", "network", "mode", "action_or_query", "data", "error", "guardrail"
        }
        assert result["success"] is False

    def test_market_close_empty_exchange_response(self, monkeypatch):
        exchange = DummyExchangeWithEmptyClose()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "10000")
        monkeypatch.setenv("HYPERLIQUID_ACCOUNT_ADDRESS", "0xabc")

        result = json.loads(hlt.hyperliquid_trade(
            action="market_close",
            coin="ETH",
            size=0.1,
            dry_run=False,
            confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "empty_exchange_response"

    # -- bulk_orders tests -------------------------------------------------

    def test_bulk_orders_dry_run_with_normal_tpsl(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "100000")

        orders = [
            {"coin": "ETH", "is_buy": True, "size": 0.02, "price": 1900.0, "tif": "Gtc"},
            {"coin": "ETH", "is_buy": False, "size": 0.02, "price": 2100.0, "tpsl": "tp",
             "trigger_px": 2100.0, "reduce_only": True},
            {"coin": "ETH", "is_buy": False, "size": 0.02, "price": 1800.0, "tpsl": "sl",
             "trigger_px": 1800.0, "reduce_only": True},
        ]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders",
            order_requests=orders,
            grouping="normalTpsl",
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["mode"] == "dry_run"
        assert result["data"]["would_execute"]["grouping"] == "normalTpsl"
        assert len(result["data"]["would_execute"]["order_requests"]) == 3
        # PnL estimates
        est = result["data"]["preflight"]["tpsl_estimates"]
        assert est["entry_price"] == 1900.0
        assert est["entry_size"] == 0.02
        assert est["is_long"] is True
        assert est["tp_price"] == 2100.0
        assert est["tp_pnl_usd"] == 4.0   # (2100-1900)*0.02
        assert est["sl_price"] == 1800.0
        assert est["sl_pnl_usd"] == -2.0  # (1800-1900)*0.02
        assert est["risk_reward_ratio"] == 2.0
        assert est["entry_notional_usd"] == 38.0

    def test_bulk_orders_tpsl_short_pnl(self, monkeypatch):
        """PnL estimates for short position with TP/SL."""
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "100000")

        orders = [
            {"coin": "ETH", "is_buy": False, "size": 0.1, "price": 2000.0, "tif": "Gtc"},
            {"coin": "ETH", "is_buy": True, "size": 0.1, "price": 1800.0, "tpsl": "tp",
             "trigger_px": 1800.0, "reduce_only": True},
            {"coin": "ETH", "is_buy": True, "size": 0.1, "price": 2200.0, "tpsl": "sl",
             "trigger_px": 2200.0, "reduce_only": True},
        ]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders,
            grouping="normalTpsl", dry_run=True,
        ))
        assert result["success"] is True
        est = result["data"]["preflight"]["tpsl_estimates"]
        assert est["is_long"] is False
        assert est["tp_pnl_usd"] == 20.0   # (2000-1800)*0.1
        assert est["sl_pnl_usd"] == -20.0  # (2000-2200)*0.1
        assert est["risk_reward_ratio"] == 1.0

    def test_bulk_orders_no_tpsl_estimate_for_na_grouping(self, monkeypatch):
        """No PnL estimate for grouping='na'."""
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "100000")

        orders = [
            {"coin": "ETH", "is_buy": True, "size": 0.02, "price": 1900.0},
        ]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders,
            grouping="na", dry_run=True,
        ))
        assert result["success"] is True
        assert "tpsl_estimates" not in result["data"]["preflight"]

    def test_bulk_orders_validates_each_order(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        # Missing is_buy in second order
        orders = [
            {"coin": "ETH", "is_buy": True, "size": 0.02, "price": 1900.0},
            {"coin": "ETH", "size": 0.02, "price": 2100.0},
        ]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_order_request"
        assert "is_buy" in result["error"]

    def test_bulk_orders_validates_missing_coin(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        orders = [
            {"is_buy": True, "size": 0.02, "price": 1900.0},
        ]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_order_request"

    def test_bulk_orders_validates_invalid_size(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        orders = [
            {"coin": "ETH", "is_buy": True, "size": -1, "price": 1900.0},
        ]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_order_request"

    def test_bulk_orders_notional_check_sums_all(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "100")

        orders = [
            {"coin": "ETH", "is_buy": True, "size": 0.02, "price": 1900.0},
            {"coin": "ETH", "is_buy": False, "size": 0.02, "price": 2100.0},
            {"coin": "ETH", "is_buy": False, "size": 0.02, "price": 1800.0},
        ]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders, grouping="normalTpsl",
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "notional_limit_exceeded"

    def test_bulk_orders_empty_list_rejected(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=[], dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_order_requests"

    def test_bulk_orders_invalid_grouping(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        orders = [{"coin": "ETH", "is_buy": True, "size": 0.01, "price": 2000}]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders, grouping="invalid",
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_grouping"

    def test_bulk_orders_coin_allowlist_per_order(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_ALLOWED_COINS", "BTC")

        orders = [{"coin": "ETH", "is_buy": True, "size": 0.01, "price": 2000}]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "coin_not_allowed"

    def test_bulk_orders_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "100000")

        orders = [
            {"coin": "ETH", "is_buy": True, "size": 0.02, "price": 1900.0, "tif": "Gtc"},
        ]
        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_orders", order_requests=orders, grouping="na",
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert result["mode"] == "live"
        assert exchange.calls[0][0] == "bulk_orders"

    # -- cancel_by_cloid tests ---------------------------------------------

    def test_cancel_by_cloid_requires_cloid(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="cancel_by_cloid", coin="ETH", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_cloid"

    def test_cancel_by_cloid_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="cancel_by_cloid", coin="ETH",
            cloid="0x00000000000000000000000000000001",
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["mode"] == "dry_run"

    # -- bulk_cancel_by_cloid tests ----------------------------------------

    def test_bulk_cancel_by_cloid_requires_cancel_requests(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_cancel_by_cloid", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_cancel_requests"

    def test_bulk_cancel_by_cloid_validates_items(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_cancel_by_cloid",
            cancel_requests=[{"coin": "ETH"}],  # missing cloid
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_cancel_request"

    # -- bulk_modify tests -------------------------------------------------

    def test_bulk_modify_requires_order_requests(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="bulk_modify", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_order_requests"

    # -- twap_order tests --------------------------------------------------

    def test_twap_order_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_MAX_NOTIONAL_USD", "100000")

        result = json.loads(hlt.hyperliquid_trade(
            action="twap_order",
            coin="ETH",
            is_buy=True,
            size=1.0,
            duration_minutes=30,
            randomize=True,
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["mode"] == "dry_run"
        assert result["data"]["would_execute"]["duration_minutes"] == 30

    def test_twap_order_rejects_spot_pair(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="twap_order", coin="ETH/USDC", is_buy=True,
            size=1.0, duration_minutes=30, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_market_type"

    def test_twap_order_requires_duration(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="twap_order", coin="ETH", is_buy=True,
            size=1.0, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_duration"

    def test_twap_order_requires_is_buy(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="twap_order", coin="ETH", size=1.0,
            duration_minutes=30, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_is_buy"

    def test_twap_cancel_requires_twap_id(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="twap_cancel", coin="ETH", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_twap_id"

    # -- update_isolated_margin tests --------------------------------------

    def test_update_isolated_margin_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="update_isolated_margin", coin="ETH",
            margin_amount=50.0, dry_run=True,
        ))
        assert result["success"] is True
        assert result["data"]["would_execute"]["margin_amount"] == 50.0

    def test_update_isolated_margin_requires_amount(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="update_isolated_margin", coin="ETH", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_margin_amount"

    # -- Transfer tests ----------------------------------------------------

    def test_usd_transfer_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="usd_transfer", amount=100.0,
            destination="0x1234567890abcdef", dry_run=True,
        ))
        assert result["success"] is True
        assert result["data"]["would_execute"]["amount"] == 100.0

    def test_usd_transfer_requires_amount(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="usd_transfer", destination="0x123", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_amount"

    def test_usd_transfer_requires_destination(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="usd_transfer", amount=100.0, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_destination"

    def test_usd_transfer_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="usd_transfer", amount=100.0,
            destination="0x1234567890abcdef",
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "usd_transfer"

    def test_spot_transfer_requires_token_and_destination(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="spot_transfer", amount=10.0, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_params"

    def test_usd_class_transfer_requires_to_perp(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="usd_class_transfer", amount=500.0, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_to_perp"

    def test_usd_class_transfer_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="usd_class_transfer", amount=500.0, to_perp=False,
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["data"]["would_execute"]["to_perp"] is False

    def test_withdraw_requires_amount_and_destination(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="withdraw", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_amount"

    # -- Sub-account tests -------------------------------------------------

    def test_create_sub_account_requires_name(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="create_sub_account", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_sub_account_name"

    def test_create_sub_account_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="create_sub_account", sub_account_name="trading-bot",
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["data"]["would_execute"]["sub_account_name"] == "trading-bot"

    def test_sub_account_transfer_requires_user_and_deposit(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="sub_account_transfer", amount=100.0, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_sub_account_user"

    def test_sub_account_spot_transfer_requires_token(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="sub_account_spot_transfer",
            sub_account_user="0xsub", is_deposit=True, amount=10.0,
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_token"

    # -- Vault tests -------------------------------------------------------

    def test_vault_transfer_requires_address(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="vault_transfer", amount=100.0, is_deposit=True,
            dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_vault_address"

    def test_vault_transfer_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="vault_transfer", vault_address="0xvault",
            is_deposit=True, amount=100.0, dry_run=True,
        ))
        assert result["success"] is True

    # -- approve_builder_fee tests -----------------------------------------

    def test_approve_builder_fee_requires_params(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="approve_builder_fee", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_params"

    # -- set_referrer tests ------------------------------------------------

    def test_set_referrer_requires_code(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="set_referrer", dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_referral_code"

    def test_set_referrer_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="set_referrer", referral_code="MYCODE", dry_run=True,
        ))
        assert result["success"] is True

    # -- token_delegate tests ----------------------------------------------

    def test_token_delegate_requires_validator(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="token_delegate", wei=1000, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "missing_validator"

    def test_token_delegate_requires_valid_wei(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="token_delegate", validator="0xval", wei=-1, dry_run=True,
        ))
        assert result["success"] is False
        assert result["guardrail"]["error_code"] == "invalid_wei"

    def test_token_delegate_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="token_delegate", validator="0xval",
            wei=1000000000000000000, dry_run=True,
        ))
        assert result["success"] is True
        assert result["data"]["would_execute"]["validator"] == "0xval"

    # -- cloid on existing order/modify ------------------------------------

    def test_order_with_cloid_dry_run(self, monkeypatch):
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")

        result = json.loads(hlt.hyperliquid_trade(
            action="order", coin="ETH", is_buy=True, size=0.1,
            price=2000, tif="Gtc",
            cloid="0x00000000000000000000000000000001",
            dry_run=True,
        ))
        assert result["success"] is True
        assert result["data"]["would_execute"]["cloid"] == "0x00000000000000000000000000000001"

    # -- Live execution for new actions ------------------------------------

    def test_update_isolated_margin_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="update_isolated_margin", coin="ETH",
            margin_amount=50.0,
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "update_isolated_margin"

    def test_create_sub_account_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="create_sub_account", sub_account_name="test-bot",
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "create_sub_account"

    def test_set_referrer_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="set_referrer", referral_code="MYCODE",
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "set_referrer"

    def test_withdraw_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="withdraw", amount=50.0, destination="0xdest",
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "withdraw_from_bridge"

    def test_usd_class_transfer_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="usd_class_transfer", amount=500.0, to_perp=False,
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "usd_class_transfer"

    def test_vault_transfer_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="vault_transfer", vault_address="0xvault",
            is_deposit=True, amount=100.0,
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "vault_usd_transfer"

    def test_approve_agent_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="approve_agent",
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "approve_agent"

    def test_token_delegate_live_executes(self, monkeypatch):
        exchange = DummyExchange()
        monkeypatch.setattr(hlt, "_get_info_client", lambda base_url: DummyInfo())
        monkeypatch.setattr(hlt, "_create_exchange", lambda base_url: exchange)
        monkeypatch.setenv("HYPERLIQUID_NETWORK", "testnet")
        monkeypatch.setenv("HYPERLIQUID_KILL_SWITCH", "false")

        result = json.loads(hlt.hyperliquid_trade(
            action="token_delegate", validator="0xval",
            wei=1000000000000000000,
            dry_run=False, confirm_execution="EXECUTE_LIVE_TRADE",
        ))
        assert result["success"] is True
        assert exchange.calls[0][0] == "token_delegate"


class TestRequirements:
    def test_check_requirements_reflects_sdk_probe(self, monkeypatch):
        monkeypatch.setattr(hlt, "_sdk_available", lambda: False)
        assert hlt.check_hyperliquid_requirements() is False
        monkeypatch.setattr(hlt, "_sdk_available", lambda: True)
        assert hlt.check_hyperliquid_requirements() is True
