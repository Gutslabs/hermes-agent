#!/usr/bin/env python3
"""
Initialize Auto-DCA strategy state file.

Usage:
    python init_state.py --coin BTC --amount 50 --max-total 5000 --network testnet
    python init_state.py --coin ETH --amount 25 --max-total 2500 --max-buys 50 --price-cap 2000
    python init_state.py --coin BTC --amount 100 --max-total 10000 --dip-pct 5 --ref-price 100000
"""

import argparse
import json
import os
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "auto-dca"
STATE_FILE = STATE_DIR / "state.json"


def build_state(args: argparse.Namespace) -> dict:
    return {
        "strategy": "auto-dca",
        "version": "1.0.0",
        "coin": args.coin.upper(),
        "amount_usd": args.amount,
        "max_total_usd": args.max_total,
        "max_buys": args.max_buys,
        "price_cap_usd": args.price_cap,
        "dip_pct": args.dip_pct,
        "reference_price": args.ref_price,
        "side": args.side,
        "network": args.network,
        "enabled": True,
        "stats": {
            "total_invested_usd": 0,
            "total_size": 0.0,
            "avg_entry_price": 0,
            "buy_count": 0,
            "last_buy_at": None,
            "last_price": None,
            "current_pnl_usd": None,
        },
        "history": [],
    }


def main():
    parser = argparse.ArgumentParser(description="Initialize Auto-DCA strategy state")
    parser.add_argument("--coin", required=True, help="Target coin symbol (e.g., BTC, ETH)")
    parser.add_argument("--amount", type=float, required=True, help="USD amount per DCA buy")
    parser.add_argument("--max-total", type=float, default=5000, help="Max total USD investment (default: 5000)")
    parser.add_argument("--max-buys", type=int, default=100, help="Max number of buys (default: 100)")
    parser.add_argument("--price-cap", type=float, default=None, help="Only buy below this price (optional)")
    parser.add_argument("--dip-pct", type=float, default=None, help="Only buy on X%% dip from reference (optional)")
    parser.add_argument("--ref-price", type=float, default=None, help="Reference price for dip mode (optional)")
    parser.add_argument("--side", choices=["long", "short"], default="long", help="DCA direction (default: long)")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet", help="Network (default: testnet)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing state file")

    args = parser.parse_args()

    if args.dip_pct is not None and args.ref_price is None:
        parser.error("--ref-price is required when using --dip-pct")

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}")
        print("Use --force to overwrite.")
        sys.exit(1)

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    state = build_state(args)

    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)

    print(json.dumps(state, indent=2))
    print(f"\nState file written to: {STATE_FILE}")
    print(f"\nNext step: create a cron job to run the strategy:")
    print(f'  cronjob(action="create", name="auto-dca-{args.coin.lower()}", '
          f'schedule="every 4h", skills=["trading/hyperliquid", "trading/auto-dca"], '
          f'prompt="Execute the next DCA buy according to the auto-dca skill.")')


if __name__ == "__main__":
    main()
