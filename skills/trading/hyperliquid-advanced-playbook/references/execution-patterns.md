# Execution Patterns

## Order type selection

- Limit (`Gtc`): default for controlled entries and reduced slippage.
- IOC (`Ioc`): for immediate execution when momentum matters.
- ALO (`Alo`): maker-only behavior where queue priority is acceptable.

## Perp-specific notes

- Review funding context before directional swings.
- Use reduce-only for defensive exits when appropriate.
- Treat market close as a high-slippage event during thin liquidity.

## Spot-specific notes

- Prefer limit entries in low-liquidity pairs.
- Confirm quote/base symbol semantics before submission.

## Slippage heuristics

- Calm market: 5 to 15 bps
- Moderate volatility: 15 to 35 bps
- High volatility: 35+ bps (or avoid market entry)

## Execution playbook

1. Build intended action as a dry-run.
2. Verify preflight notional and guardrail pass.
3. Verify orderbook support (`l2_snapshot`) near entry.
4. Submit live only with explicit user authorization.
5. Monitor post-fill status and adjust exits.

## Failure handling

If any write action is rejected:
- report exact error code
- identify whether it is guardrail, validation, or exchange-side rejection
- provide a corrected follow-up action
