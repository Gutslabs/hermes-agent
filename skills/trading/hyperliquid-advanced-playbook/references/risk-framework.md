# Risk Framework

This framework is execution-agnostic and applies to both perps and spot.

## Core limits

- Max risk per trade: 0.25% to 1.00% of equity
- Max open risk across all positions: 2.00% of equity
- Max daily drawdown: 2.00% to 3.00% of equity
- Max weekly drawdown: 5.00% of equity

If daily max drawdown is reached, stop initiating new trades.

## Position sizing logic

1. Define entry and invalidation prices.
2. Compute stop distance in price terms.
3. Convert risk budget into position size:

`size = risk_usd / abs(entry - stop)`

4. Check resulting notional:

`notional = size * entry`

5. Cap by guardrails:
- account margin constraints
- configured max notional cap
- liquidity quality (spread, depth)

## Leverage discipline

- Do not use leverage to increase risk beyond budget.
- Prefer lower leverage in volatile sessions.
- Use isolated margin when risk isolation is needed.

## Execution quality checks

- Spread is acceptable for intended size.
- Slippage estimate is realistic for market conditions.
- Funding or borrow effects are acknowledged for hold duration.

## No-trade criteria

- Invalidation is vague or too wide for budget.
- Liquidity is insufficient for planned size.
- Setup depends on "hope" rather than a testable condition.
- Recent losses hit daily risk stop.
