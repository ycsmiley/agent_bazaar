# Uniswap Trade API — Integration Feedback

_Required submission artefact for the Uniswap hackathon track._

## What we built with it

Agent Bazaar uses the Uniswap Trade API as a **real quote and approval proof**
for payment-denomination flexibility. The escrow demo settles in Base Sepolia
MockUSDC, so we intentionally do not claim a Uniswap swap transaction for the
escrow path.

Current live-tested flow:

1. **Approval check** — `UniswapClient.check_approval()` calls
   `/check_approval` for the configured wallet, input token, output token, and
   chain.
2. **Quote proof** — `UniswapClient.quote()` calls `/quote` for native ETH →
   USDC on Base mainnet and returns the quote id, route, token amounts, and
   approval requirement.
3. **Agent settlement handoff** — the buyer agent records the quote id as the
   payment-route proof, then locks the escrow through KeeperHub using the
   configured settlement token.

The integration lives in [`agents/lib/uniswap_client.py`](agents/lib/uniswap_client.py:1)
and the live proof script is [`scripts/test_uniswap_quote.py`](scripts/test_uniswap_quote.py:1).

## What we actually tested

- `POST /quote` against Base mainnet (`8453`) for native ETH → USDC.
- Quote id returned: `52cdda69-9996-4b58-9101-d1451f44d8f0`.
- Route returned through V3 pool `0xb4CB800910B228ED3d0834cF79D697127BBB00e5`.
- Base Sepolia MockUSDC escrow settlement stayed separate because testnet MockUSDC is not a Uniswap liquidity route.

## Issues we hit during integration

- **No route for testnet MockUSDC.** Trying to quote against the escrow token on Base Sepolia returned no available route, which is expected but easy to mistake for a broken API key.
- **Mainnet/testnet split.** For an honest demo, we separated "real quote proof on Base mainnet" from "escrow settlement on Base Sepolia MockUSDC" instead of pretending there was a swap tx.
- **API key confusion.** It is easy to think the API key is only needed for swap execution, but quote/check endpoints also need the configured key in our client.

## What worked well

- **Permit2 approval visibility** is useful for autonomous agents. The agent can
  know whether a wallet needs approval before trying to execute a route.
- **Quote response structure** gives enough route detail to explain the payment
  path to a human judge without pretending settlement already happened.
- **Chain/token configuration** is easy to parameterize. We can keep the
  hackathon escrow on Base Sepolia while showing a real Base quote where
  production liquidity exists.

## Friction / suggestions

1. **Testnet quote availability.** Base Sepolia MockUSDC is perfect for escrow
   demos, but quotes against arbitrary testnet tokens return no route. A small
   documented sandbox token set with guaranteed liquidity would help hackathon
   builders test end-to-end without jumping between testnet settlement and
   mainnet quote proofs.
2. **Quote-only examples for agents.** Most docs naturally optimize for users
   who will swap immediately. Agent apps often need a quote as a decision input
   before a different system executes settlement. More examples for quote-only
   planning flows would be helpful.
3. **Clear units in responses.** Gas and amount fields are machine-readable but
   easy to mix up in agent code. Returning explicit unit/currency metadata next
   to every numeric field would reduce errors.
4. **MCP wrapper.** A first-class MCP server exposing `quote`,
   `check_approval`, and route explanation would let agent frameworks compose
   Uniswap directly with other tools like KeeperHub.

## Scorecard

| Dimension          | Rating |
|--------------------|--------|
| Docs quality       | 8/10   |
| API stability      | 9/10   |
| Quote ergonomics   | 9/10   |
| Agent-friendliness | 7/10   |

Overall, the Trade API was useful as a real route/approval oracle for an
agent-to-agent market. We kept the integration honest: quote proof is real,
escrow settlement is separate, and the demo does not invent a swap tx.
