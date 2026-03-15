#!/usr/bin/env python3
"""Initialize Smart DCA (volatility-adjusted) strategy state file."""

import argparse
import json
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "smart-dca"
STATE_FILE = STATE_DIR / "state.json"


def main():
    parser = argparse.ArgumentParser(description="Initialize Smart DCA strategy")
    parser.add_argument("--coin", required=True, help="Target coin (e.g., BTC)")
    parser.add_argument("--base-amount", type=float, default=50, help="Base USD per buy (default: 50)")
    parser.add_argument("--min-amount", type=float, default=10, help="Min USD per buy (default: 10)")
    parser.add_argument("--max-amount", type=float, default=200, help="Max USD per buy (default: 200)")
    parser.add_argument("--vol-lookback", type=int, default=24, help="Volatility lookback hours (default: 24)")
    parser.add_argument("--interval", default="1h", help="Candle interval (default: 1h)")
    parser.add_argument("--vol-low", type=float, default=0.5, help="Low vol multiplier (default: 0.5)")
    parser.add_argument("--vol-high", type=float, default=3.0, help="High vol multiplier (default: 3.0)")
    parser.add_argument("--fear-greed", action="store_true", default=True, help="Enable fear/greed adjustment")
    parser.add_argument("--no-fear-greed", dest="fear_greed", action="store_false")
    parser.add_argument("--max-total", type=float, default=10000, help="Max total investment (default: 10000)")
    parser.add_argument("--max-buys", type=int, default=200, help="Max buy count (default: 200)")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}\nUse --force to overwrite.")
        sys.exit(1)

    state = {
        "strategy": "smart-dca",
        "version": "1.0.0",
        "coin": args.coin.upper(),
        "base_amount_usd": args.base_amount,
        "min_amount_usd": args.min_amount,
        "max_amount_usd": args.max_amount,
        "volatility_lookback": args.vol_lookback,
        "candle_interval": args.interval,
        "vol_multiplier_low": args.vol_low,
        "vol_multiplier_high": args.vol_high,
        "fear_greed_mode": args.fear_greed,
        "max_total_usd": args.max_total,
        "max_buys": args.max_buys,
        "network": args.network,
        "enabled": True,
        "stats": {
            "total_invested_usd": 0, "total_size": 0.0, "avg_entry_price": 0,
            "buy_count": 0, "capital_efficiency": 0,
            "last_buy_at": None, "last_price": None,
            "last_amount_usd": None, "last_volatility": None,
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
