#!/usr/bin/env python3
"""Initialize Grid Bot strategy state file."""

import argparse
import json
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "grid-bot"
STATE_FILE = STATE_DIR / "state.json"


def main():
    parser = argparse.ArgumentParser(description="Initialize Grid Bot strategy")
    parser.add_argument("--coin", required=True, help="Target coin (e.g., ETH)")
    parser.add_argument("--range-low", type=float, required=True, help="Grid lower bound price")
    parser.add_argument("--range-high", type=float, required=True, help="Grid upper bound price")
    parser.add_argument("--grids", type=int, default=10, help="Number of grid levels (default: 10)")
    parser.add_argument("--notional", type=float, default=50, help="USD per grid order (default: 50)")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.range_low >= args.range_high:
        parser.error("--range-low must be less than --range-high")

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}\nUse --force to overwrite.")
        sys.exit(1)

    state = {
        "strategy": "grid-bot",
        "version": "1.0.0",
        "coin": args.coin.upper(),
        "range_low": args.range_low,
        "range_high": args.range_high,
        "grid_count": args.grids,
        "notional_per_grid_usd": args.notional,
        "network": args.network,
        "enabled": True,
        "grid_lines": [],
        "active_orders": {},
        "stats": {
            "grids_filled": 0,
            "total_profit_usd": 0,
            "total_volume_usd": 0,
            "cycles_completed": 0,
            "start_time": None,
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
