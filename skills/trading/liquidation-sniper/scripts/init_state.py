#!/usr/bin/env python3
"""Initialize Liquidation Sniper strategy state file."""

import argparse
import json
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "liquidation-sniper"
STATE_FILE = STATE_DIR / "state.json"


def main():
    parser = argparse.ArgumentParser(description="Initialize Liquidation Sniper strategy")
    parser.add_argument("--coins", nargs="+", default=["BTC", "ETH", "SOL"], help="Coins to monitor")
    parser.add_argument("--interval", default="5m", help="Candle interval (default: 5m)")
    parser.add_argument("--drop-pct", type=float, default=2.0, help="Min price drop %% for cascade (default: 2.0)")
    parser.add_argument("--vol-spike", type=float, default=3.0, help="Volume spike multiplier (default: 3.0)")
    parser.add_argument("--cooldown", type=int, default=3, help="Cooldown candles after cascade (default: 3)")
    parser.add_argument("--tp-pct", type=float, default=1.5, help="Take profit %% (default: 1.5)")
    parser.add_argument("--sl-pct", type=float, default=1.0, help="Stop loss %% (default: 1.0)")
    parser.add_argument("--notional", type=float, default=100, help="USD per trade (default: 100)")
    parser.add_argument("--max-concurrent", type=int, default=2, help="Max concurrent positions (default: 2)")
    parser.add_argument("--max-daily", type=int, default=5, help="Max trades per day (default: 5)")
    parser.add_argument("--entry-mode", choices=["market", "limit_wick"], default="limit_wick")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}\nUse --force to overwrite.")
        sys.exit(1)

    state = {
        "strategy": "liquidation-sniper",
        "version": "1.0.0",
        "coins": [c.upper() for c in args.coins],
        "candle_interval": args.interval,
        "cascade_threshold": {
            "price_drop_pct": args.drop_pct,
            "volume_spike_x": args.vol_spike,
            "lookback_candles": 6,
        },
        "cooldown_candles": args.cooldown,
        "entry_mode": args.entry_mode,
        "tp_pct": args.tp_pct,
        "sl_pct": args.sl_pct,
        "notional_per_trade_usd": args.notional,
        "max_concurrent": args.max_concurrent,
        "max_trades_per_day": args.max_daily,
        "network": args.network,
        "enabled": True,
        "positions": {},
        "daily_stats": {"date": None, "trades_today": 0, "pnl_today": 0},
        "stats": {
            "cascades_detected": 0, "entries_taken": 0, "wins": 0,
            "losses": 0, "total_pnl_usd": 0, "avg_bounce_pct": 0,
        },
        "history": [],
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)
    print(json.dumps(state, indent=2))
    print(f"\nState written to: {STATE_FILE}")


if __name__ == "__main__":
    main()
