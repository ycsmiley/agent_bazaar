# Uniswap Trade API — Integration Feedback

_Required submission artefact for the Uniswap hackathon track._

## What we built with it

AgentBazaar uses the Uniswap Trade API as its **multi-token payment bridge**. Two flows:

1. **Pre-lock swap** — the buyer agent frequently holds ETH (or another base token) but our escrow only accepts USDC. Before firing the KeeperHub `lock` workflow, the buyer calls `UniswapClient.bridge_to_usdc`, which runs `/check_approval → /quote → /swap`. The returned `transactionHash` is the TxID bound into the rest of the deal.
2. **Post-release swap** — sellers declare a `preferred_token` in their ERC-8004 agent card. If it's not USDC, the KeeperHub release workflow chains a second `UniswapClient.bridge_from_usdc` call after `optimisticRelease`, so the seller ends up with DAI (or whatever) without touching USDC.

Both paths live in [`agents/lib/uniswap_client.py`](agents/lib/uniswap_client.py:1) and are wired from the buyer/seller agents.

## What worked well

- **Permit2 approval check** in a single call is a huge ergonomic win. We only bother the buyer for an approval tx when `check_approval.approval != null`, so a warm wallet goes quote→swap in two round-trips.
- **EXACT_INPUT quotes** mean we can size the ETH→USDC swap to exactly the escrow lock amount plus a small buffer, instead of having to solve the inverse.
- **Real TxID on `/swap`** — no intermediate tx-relay step. This matters for our demo because we list five visible TxIDs and Uniswap provides the first one.

## Friction / suggestions

1. **Quote ID vs. route reuse.** When the quote is older than ~15s by the time the wallet signs the Permit2, we occasionally get a stale-price revert on `/swap`. A flag like `allowPriceDriftBps` or a server-side auto-requote when the drift is under slippage tolerance would smooth this out for agent flows that incur a signing round-trip.
2. **Gas fee field units.** `gasFee` comes back as a string of wei, but the surrounding `amount` fields are sometimes the input-token atomic unit and sometimes wei. Normalising this (or tagging each with `currency`) would prevent accidental unit mixing in agent code.
3. **Batching across chains.** Our sellers occasionally want USDC on Base but the release happens on a different EVM. Right now we handle this ourselves. A `chainId` pair on `/quote` with a bridging route would let us drop ~100 LoC.
4. **MCP wrapper.** We built our own async wrapper because the Python SDK is thin. A first-class MCP server exposing `quote` / `swap` / `check_approval` directly would let us skip the HTTP layer entirely and chain into KeeperHub workflows natively.

## Scorecard

| Dimension         | Rating |
|-------------------|--------|
| Docs quality      | 8/10   |
| API stability     | 9/10   |
| Time to first TxID| 10/10  |
| Agent-friendliness| 7/10   |

Overall the Trade API was the least-painful sponsor integration in this submission. Shipping ETH→USDC→lock in a single afternoon is exactly the kind of velocity that lets an agent protocol compose at the settlement layer.
