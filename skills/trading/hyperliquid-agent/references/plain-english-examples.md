# Plain-English Examples (Hyperliquid Agent)

Use these as user prompts with `/hyperliquid-agent`.

## Read-only

- "Show my current Hyperliquid account state and open orders."
- "What is my available balance and current BTC mid price?"

## Open position

- "Open a 20 dollar BTC long on mainnet."
- "Open a 50 dollar ETH short with 10x leverage."
- "Buy 0.0002 BTC now with market order. Dry run first."

## Mainnet confirmation style

- "YES"
- "NO"

## Close / cancel / modify

- "Close my BTC position at market."
- "Cancel BTC order 123456."
- "Set BTC leverage to 5x cross."

## Spot examples

- "Buy 25 dollars of PURR/USDC on spot, dry run first."
- "Sell my PURR/USDC spot position at market, dry run first."

## Recommended style for users

When asking for execution, include:
- side (`long/short` or `buy/sell`)
- coin (`BTC`, `ETH`, `HYPE`, or pair like `PURR/USDC`)
- notional in USD or explicit size
- leverage if needed
- "dry run first"

Example:
- "Open a 30 dollar BTC long at 5x, dry run first, then ask me for live confirmation."

For mainnet default flow:
- "Open a 30 dollar BTC long at 5x. Show summary, then ask YES/NO and execute on YES."
