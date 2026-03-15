#!/usr/bin/env python3
"""Initialize Trailing Stop strategy state file."""

import argparse
import json
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "trailing-stop"
STATE_FILE = STATE_DIR / "state.json"


def main():
    parser = argparse.ArgumentParser(description="Initialize Trailing Stop strategy")
    parser.add_argument("--trail-pct", type=float, default=2.0, help="Trail distance %% (default: 2.0)")
    parser.add_argument("--activation-pct", type=float, default=1.0, help="Activate after this %% profit (default: 1.0)")
    parser.add_argument("--update-threshold", type=float, default=0.5, help="Min %% move to update stop (default: 0.5)")
    parser.add_argument("--coins", nargs="*", default=None, help="Coins to trail (default: all positions)")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}\nUse --force to overwrite.")
        sys.exit(1)

    state = {
        "strategy": "trailing-stop",
        "version": "1.0.0",
        "trail_pct": args.trail_pct,
        "activation_pct": args.activation_pct,
        "min_trail_distance_usd": 5,
        "update_threshold_pct": args.update_threshold,
        "coins": [c.upper() for c in args.coins] if args.coins else None,
        "network": args.network,
        "enabled": True,
        "tracked": {},
        "stats": {"stops_placed": 0, "stops_updated": 0, "stops_triggered": 0, "total_saved_pnl_usd": 0},
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)
    print(json.dumps(state, indent=2))
    print(f"\nState written to: {STATE_FILE}")


if __name__ == "__main__":
    main()
