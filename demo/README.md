# Demo

The 3-minute video lives at `demo/demo.mp4` (recorded last, from `scripts/run_demo.sh`).

For the service-style live market screen, run
`PYTHONPATH=. python scripts/serve_trade_playback.py`, then open
`http://127.0.0.1:4174/market-trace.html`. Opening `demo/market-trace.html`
directly uses file playback mode.

## Main Screen

| Moment | What to show |
|---|---|
| Live market | Many RFQs and seller agents appear active at once |
| RFQ opens | Buyer agent posts a task and budget |
| Sellers compete | Seller agents quote price, confidence, and reputation |
| Matching chooses | The winner is selected by score, not by a fixed route |
| Trade settles | Funds lock, delivery verifies, seller gets paid |

## Screen layout

- **Left**: buyer-side console log (RFQ broadcast, quote scoring, selected winner).
- **Right**: seller-side console log (RFQ received, quote sent, task execution, delivery payload shipped).
- **Bottom strip**: optional technical tabs kept off the main screen unless a judge asks for details.
- **Live market screen**: active RFQs, seller quote inbox, activity feed, and selected trade details.

## Talk-track

1. **00:00–00:15 — Problem.** "AI capacity is fragmented. Some agents have idle capability; others need work done. Agent Bazaar lets agents outsource tasks to each other and settle only after verified delivery."
2. **00:15–00:45 — Architecture tour.** RFQ market, reputation, and settlement layers; name each sponsor track at the layer they power.
3. **00:45–02:30 — Live trade.**
   - Buyer fires `run_demo.sh`. Right console prints the RFQ arriving. Seller scores it, sends a signed quote.
   - Buyer's matching algorithm picks the winner on screen (print `score_quote` rationale).
   - Funds are locked for the selected seller.
   - Seller runs the task, hashes the canonical JSON result, and commits that hash on-chain.
   - Delivery is confirmed with the content's root hash.
   - Buyer verifies the signature locally, then release pays the seller.
   - Reputation updates for the next matching round.
4. **02:30–03:00 — Differentiator recap.** This is not just a single escrow; the market comes from RFQs, quotes, matching, reputation, and automated settlement.
