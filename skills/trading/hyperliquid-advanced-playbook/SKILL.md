---
name: hyperliquid-advanced-playbook
description: Advisory Hyperliquid trading workflow for perps and spot. Use for thesis building, risk budgeting, execution planning, and post-trade review with strict safety defaults (dry-run first, explicit live confirmation).
metadata:
  hermes:
    tags: [trading, hyperliquid, risk-management, execution]
---

# Hyperliquid Advanced Playbook (Advisory)

Use this skill when the user wants a high-discipline trading workflow on Hyperliquid.
This skill is **advisory-first**:
- default to planning and risk checks
- run execution previews in `dry_run=true`
- never suggest live submission without explicit user confirmation

## Tools to use

- `hyperliquid_info` for market/account state
- `hyperliquid_trade` for execution previews and, only with explicit consent, live actions

## Safety policy

1. Always begin with `dry_run=true` execution planning.
2. Require explicit user intent before any live execution.
3. Respect allowlist / notional / kill-switch guardrails.
4. If guardrails fail, propose safer alternatives (smaller size, different symbol, defer trade).

## Workflow

1. Pre-trade framing
- Identify market (perp or spot), timeframe, and directional thesis.
- Define invalidation, stop condition, and expected hold duration.
- Pull context with `hyperliquid_info`:
  - `all_mids`
  - `l2_snapshot` for target symbol
  - `candles_snapshot` for structure
  - `funding_history` for perp bias

2. Risk plan
- Use `references/risk-framework.md`.
- Set position size from risk budget, not conviction alone.
- Enforce max loss per trade and max daily drawdown.

3. Execution design
- Use `references/execution-patterns.md`.
- Choose order type and slippage assumptions.
- Build a dry-run with `hyperliquid_trade` and inspect preflight notional.

4. Commit decision
- If setup quality is weak or invalidation is unclear, recommend no-trade.
- If setup is valid, provide explicit entry/exit/invalidation plan.
- Use `templates/trade-plan.md` for final output.

5. Post-trade review
- Capture outcome, process quality, and deviations.
- Use `templates/post-trade-review.md`.

## Position size helper

Use `scripts/position_size.py` when the user gives:
- account equity
- risk percent or risk USD
- entry and invalidation prices

Example:

```bash
python3 SKILL_DIR/scripts/position_size.py \
  --equity 25000 \
  --risk-pct 0.5 \
  --entry 2450 \
  --stop 2390
```

## Output contract

Return concise structured output in this order:
1. Thesis
2. Trade parameters
3. Risk checks
4. Dry-run result summary
5. Next action (execute / wait / abort)

If live execution is requested, repeat the live risks and require an explicit confirmation statement first.
