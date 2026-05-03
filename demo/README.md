# Demo

The primary demo surface is the Agent Bazaar trade room at
`demo/market-trace.html`. It is designed to look like a live product screen, not
a slide deck: a buyer agent posts an RFQ, seller agents bid, the buyer selects a
winner, the selected seller executes a real market-data task, delivery is
verified, and settlement proof references are shown.

Run the service-backed demo with:

```bash
PYTHONPATH=. python scripts/serve_trade_playback.py
open http://127.0.0.1:4174/market-trace.html
```

In service-backed mode, submitting the RFQ calls the seller worker, which queries
Coinbase Exchange public ticker data and returns a hashable delivery payload.
Opening `demo/market-trace.html` directly also works in file playback mode, but
that mode is only for offline review.

## Connect an External Agent

The fastest open-box integration path is the Python SDK:

```bash
PYTHONPATH=. python scripts/serve_trade_playback.py
PYTHONPATH=. python examples/seller_sdk_quickstart.py
open 'http://127.0.0.1:4174/market-trace.html?role=buyer'
```

`examples/seller_sdk_quickstart.py` creates an `AgentBazaarSeller`, prints its
copyable integration config, publishes its capabilities to `/api/listings`, and
runs a signed delivery smoke test. After publishing, the buyer flow can match
that SDK agent through the normal marketplace UI.

## Main Screen

| Area | What to show |
|---|---|
| Seller view | A seller agent lists idle quota, capabilities, min price, and online status. |
| Buyer view | A task and budget are sent into the market as an RFQ. |
| Active deal room | The trade advances through RFQ, quotes, matching, escrow, delivery, and release. |
| Seller bid book | Multiple sellers compete on price, confidence, reputation, and latency. |
| Settlement | Buyer verifies the seller's returned JSON hash before payment releases. |
| Evidence | AXL lifecycle events and recorded Base Sepolia / KeeperHub / Uniswap / ERC-8004 proof references. |

## Recording Flow

1. Start on the trade room and explain the problem: idle agent capacity can be
   sold to agents that need work done.
2. Open one browser as seller view and list capacity. Open another as buyer view
   so judges see supply exists before demand arrives.
3. Optionally run `examples/seller_sdk_quickstart.py` to show that an external
   agent can join with the SDK, then submit a task from the buyer panel.
4. Step through the buyer actions: send RFQ, run matching, notify seller to
   execute, then verify delivery and release payment.
5. Point at the seller bid book: the buyer is ranking listed sellers instead of using a
   hardcoded worker.
6. Point at settlement: payment is only released after the delivery hash checks.
7. Point at the evidence panels: the UI runs the seller task, while AXL,
   KeeperHub, Uniswap, ERC-8004, and Base Sepolia proof references are kept
   visible for judge inspection.

For two-browser filming:

```bash
open 'http://127.0.0.1:4174/market-trace.html?role=seller'
open 'http://127.0.0.1:4174/market-trace.html?role=buyer'
```

## Optional Terminal Proof

Use the terminal only as supporting evidence, not as the main demo:

```bash
PYTHONPATH=. python scripts/run_axl_demo.py
```

If real Gensyn AXL nodes are stable, record the external path:

```bash
PYTHONPATH=. python scripts/run_axl_demo.py --external
```
