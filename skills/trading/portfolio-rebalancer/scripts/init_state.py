#!/usr/bin/env python3
"""Initialize Portfolio Rebalancer strategy state file."""

import argparse
import json
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".hermes" / "strategies" / "portfolio-rebalancer"
STATE_FILE = STATE_DIR / "state.json"


def main():
    parser = argparse.ArgumentParser(description="Initialize Portfolio Rebalancer strategy")
    parser.add_argument("--equity", type=float, required=True, help="Target total equity USD")
    parser.add_argument("--allocations", required=True, help='JSON object: {"BTC":0.4,"ETH":0.3,"SOL":0.2,"HYPE":0.1}')
    parser.add_argument("--drift-threshold", type=float, default=5, help="Rebalance drift threshold %% (default: 5)")
    parser.add_argument("--min-trade", type=float, default=10, help="Min trade size USD (default: 10)")
    parser.add_argument("--mode", choices=["threshold", "calendar"], default="threshold", help="Rebalance mode")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        allocations = json.loads(args.allocations)
    except json.JSONDecodeError:
        parser.error("--allocations must be valid JSON")

    total_weight = sum(allocations.values())
    if abs(total_weight - 1.0) > 0.01:
        parser.error(f"Allocations must sum to 1.0, got {total_weight}")

    if STATE_FILE.exists() and not args.force:
        print(f"State file already exists: {STATE_FILE}\nUse --force to overwrite.")
        sys.exit(1)

    state = {
        "strategy": "portfolio-rebalancer",
        "version": "1.0.0",
        "target_equity_usd": args.equity,
        "allocations": {k.upper(): v for k, v in allocations.items()},
        "drift_threshold_pct": args.drift_threshold,
        "min_trade_usd": args.min_trade,
        "rebalance_mode": args.mode,
        "side": "long",
        "network": args.network,
        "enabled": True,
        "last_rebalance": None,
        "stats": {"rebalances_executed": 0, "total_trades": 0, "total_volume_usd": 0, "max_drift_seen_pct": 0},
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
