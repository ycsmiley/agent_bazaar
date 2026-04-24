# Demo

The 3-minute video lives at `demo/demo.mp4` (recorded last, from `scripts/run_demo.sh`).

## Visible TxIDs

| # | Action                                   | Source          |
|---|------------------------------------------|-----------------|
| 1 | `uniswap /swap` → ETH to USDC            | Uniswap API     |
| 2 | `escrow.lockFunds()`                     | KeeperHub `lock`|
| 3 | `escrow.confirmDelivery()`               | Seller signs    |
| 4 | `escrow.releaseFunds()` or `optimisticRelease()` | Buyer or KeeperHub `release` |
| 5 | `erc8004.submitFeedback()`               | Buyer signs     |

## Screen layout

- **Left**: buyer-side console log (RFQ broadcast, quote scoring, selected winner, TxIDs).
- **Right**: seller-side console log (RFQ received, quote sent, task executing via 0G Compute, delivery payload shipped).
- **Bottom strip**: five block explorer tabs, one per TxID, kept open so the judge sees each tx confirming in real time.

## Talk-track

1. **00:00–00:15 — Problem.** "x402 is pay-then-deliver. If the seller is a hallucinating LLM, the buyer has no recourse. AgentBazaar fixes that."
2. **00:15–00:45 — Architecture tour.** Four layers; name each sponsor track at the layer they power.
3. **00:45–02:30 — Live trade.**
   - Buyer fires `run_demo.sh`. Right console prints the RFQ arriving. Seller scores it, sends a signed quote.
   - Buyer's matching algorithm picks the winner on screen (print `score_quote` rationale).
   - Tx #1 lands: Uniswap bridge.
   - Tx #2 lands: KeeperHub lock.
   - Seller runs 0G Compute TeeML inference, shows the tee_signature in its payload.
   - Tx #3 lands: confirmDelivery with the content's root hash.
   - Buyer verifies the signature locally, then tx #4 lands (releaseFunds).
   - Tx #5 lands: ERC-8004 feedback.
4. **02:30–03:00 — Differentiator recap.** Five TxIDs, four sponsor tracks, every layer powered by a partner. Show the matrix table from README §4.
