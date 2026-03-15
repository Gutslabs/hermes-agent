#!/usr/bin/env python3
"""Initialize Funding Farm strategy state file."""

import argparse
import json
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "funding-farm"
STATE_FILE = STATE_DIR / "state.json"


def main():
    parser = argparse.ArgumentParser(description="Initialize Funding Farm strategy")
    parser.add_argument("--coins", nargs="+", default=["BTC", "ETH", "SOL"], help="Coins to scan (default: BTC ETH SOL)")
    parser.add_argument("--notional", type=float, default=100, help="USD per coin position (default: 100)")
    parser.add_argument("--max-total", type=float, default=1000, help="Max total notional (default: 1000)")
    parser.add_argument("--threshold", type=float, default=5, help="Funding threshold in bps (default: 5)")
    parser.add_argument("--exit-bps", type=float, default=1, help="Exit when funding drops below (default: 1)")
    parser.add_argument("--max-loss", type=float, default=20, help="Per-position max loss USD (default: 20)")
    parser.add_argument("--max-hold", type=int, default=48, help="Max hold hours (default: 48)")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--force", action="store_true", help="Overwrite existing state")
    args = parser.parse_args()

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}\nUse --force to overwrite.")
        sys.exit(1)

    state = {
        "strategy": "funding-farm",
        "version": "1.0.0",
        "coins": [c.upper() for c in args.coins],
        "notional_per_coin_usd": args.notional,
        "max_total_notional_usd": args.max_total,
        "funding_threshold_bps": args.threshold,
        "funding_exit_bps": args.exit_bps,
        "max_loss_usd": args.max_loss,
        "max_hold_hours": args.max_hold,
        "network": args.network,
        "enabled": True,
        "positions": {},
        "stats": {
            "total_funding_collected_usd": 0,
            "total_trades": 0,
            "total_pnl_usd": 0,
            "win_count": 0,
            "loss_count": 0,
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
