#!/usr/bin/env python3
"""Deterministic position size helper for advisory trade planning."""

import argparse
import json
import math


def _positive(name: str, value: float) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute risk-based position size")
    parser.add_argument("--equity", type=float, required=True, help="Account equity in USD")
    parser.add_argument("--risk-pct", type=float, default=None, help="Risk percent of equity (e.g. 0.5 for 0.5%%)")
    parser.add_argument("--risk-usd", type=float, default=None, help="Risk budget in USD (overrides risk-pct)")
    parser.add_argument("--entry", type=float, required=True, help="Entry price")
    parser.add_argument("--stop", type=float, required=True, help="Invalidation/stop price")
    parser.add_argument("--round", type=int, default=6, help="Decimal places for output size")
    args = parser.parse_args()

    equity = _positive("equity", args.equity)
    entry = _positive("entry", args.entry)
    stop = _positive("stop", args.stop)

    distance = abs(entry - stop)
    if distance == 0:
        raise ValueError("entry and stop cannot be equal")

    if args.risk_usd is not None:
        risk_usd = _positive("risk-usd", args.risk_usd)
    elif args.risk_pct is not None:
        risk_usd = equity * (_positive("risk-pct", args.risk_pct) / 100.0)
    else:
        raise ValueError("Provide either --risk-usd or --risk-pct")

    size = risk_usd / distance
    notional = size * entry

    decimals = max(0, args.round)
    factor = 10**decimals
    rounded_size = math.floor(size * factor) / factor

    payload = {
        "inputs": {
            "equity": equity,
            "risk_usd": risk_usd,
            "entry": entry,
            "stop": stop,
        },
        "outputs": {
            "size": rounded_size,
            "exact_size": size,
            "estimated_notional_usd": notional,
            "stop_distance": distance,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
