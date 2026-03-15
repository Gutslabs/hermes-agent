#!/usr/bin/env python3
"""Initialize Mean Reversion strategy state file."""

import argparse
import json
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "mean-reversion"
STATE_FILE = STATE_DIR / "state.json"


def main():
    parser = argparse.ArgumentParser(description="Initialize Mean Reversion strategy")
    parser.add_argument("--coins", nargs="+", default=["BTC", "ETH"], help="Coins to scan (default: BTC ETH)")
    parser.add_argument("--lookback", type=int, default=20, help="MA lookback periods (default: 20)")
    parser.add_argument("--interval", default="1h", help="Candle interval (default: 1h)")
    parser.add_argument("--entry-dev", type=float, default=2.0, help="Entry std devs (default: 2.0)")
    parser.add_argument("--exit-dev", type=float, default=0.5, help="Exit std devs (default: 0.5)")
    parser.add_argument("--stop-dev", type=float, default=3.0, help="Stop loss std devs (default: 3.0)")
    parser.add_argument("--notional", type=float, default=100, help="USD per trade (default: 100)")
    parser.add_argument("--max-positions", type=int, default=3, help="Max concurrent (default: 3)")
    parser.add_argument("--max-loss", type=float, default=25, help="Per-position max loss (default: 25)")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}\nUse --force to overwrite.")
        sys.exit(1)

    state = {
        "strategy": "mean-reversion",
        "version": "1.0.0",
        "coins": [c.upper() for c in args.coins],
        "lookback_periods": args.lookback,
        "candle_interval": args.interval,
        "entry_deviation": args.entry_dev,
        "exit_deviation": args.exit_dev,
        "stop_deviation": args.stop_dev,
        "notional_per_trade_usd": args.notional,
        "max_positions": args.max_positions,
        "max_loss_usd": args.max_loss,
        "network": args.network,
        "enabled": True,
        "positions": {},
        "stats": {"total_trades": 0, "wins": 0, "losses": 0, "total_pnl_usd": 0, "avg_hold_hours": 0},
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
