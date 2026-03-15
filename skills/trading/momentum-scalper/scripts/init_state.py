#!/usr/bin/env python3
"""Initialize Momentum Scalper strategy state file."""

import argparse
import json
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "momentum-scalper"
STATE_FILE = STATE_DIR / "state.json"


def main():
    parser = argparse.ArgumentParser(description="Initialize Momentum Scalper strategy")
    parser.add_argument("--coins", nargs="+", default=["BTC", "ETH", "SOL"], help="Coins to scan")
    parser.add_argument("--interval", default="5m", help="Candle interval (default: 5m)")
    parser.add_argument("--lookback", type=int, default=12, help="Lookback candles (default: 12)")
    parser.add_argument("--threshold", type=float, default=2.0, help="Momentum score threshold (default: 2.0)")
    parser.add_argument("--tp-pct", type=float, default=0.5, help="Take profit %% (default: 0.5)")
    parser.add_argument("--sl-pct", type=float, default=0.25, help="Stop loss %% (default: 0.25)")
    parser.add_argument("--notional", type=float, default=100, help="USD per trade (default: 100)")
    parser.add_argument("--max-concurrent", type=int, default=2, help="Max concurrent positions (default: 2)")
    parser.add_argument("--max-daily", type=int, default=10, help="Max trades per day (default: 10)")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}\nUse --force to overwrite.")
        sys.exit(1)

    state = {
        "strategy": "momentum-scalper",
        "version": "1.0.0",
        "coins": [c.upper() for c in args.coins],
        "candle_interval": args.interval,
        "lookback_candles": args.lookback,
        "momentum_threshold": args.threshold,
        "tp_pct": args.tp_pct,
        "sl_pct": args.sl_pct,
        "notional_per_trade_usd": args.notional,
        "max_concurrent": args.max_concurrent,
        "max_trades_per_day": args.max_daily,
        "cooldown_minutes": 15,
        "network": args.network,
        "enabled": True,
        "positions": {},
        "daily_stats": {"date": None, "trades_today": 0, "pnl_today": 0},
        "stats": {
            "total_trades": 0, "wins": 0, "losses": 0, "total_pnl_usd": 0,
            "avg_hold_minutes": 0, "best_trade_usd": 0, "worst_trade_usd": 0,
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
