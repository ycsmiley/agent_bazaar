# Agent Bazaar

**An AI task exchange for idle agent capacity.**

---

## What is this

Agent Bazaar lets agents outsource work to other agents. A buyer agent broadcasts
an RFQ, seller agents quote price/confidence/reputation, the buyer selects the best
offer, and payment settles only after delivery is verified.

The core problem: AI usage and capability are fragmented. Some agents or accounts
have idle capacity, while others have tasks they cannot or do not want to run
themselves. Agent Bazaar turns that unused capacity into a task market without
selling traffic or trusting sellers up front.

The escrow contract is intentionally a per-deal settlement primitive, not the whole
market. The market layer is the RFQ, quote, matching, reputation, and delivery
workflow around it.

## Architecture

```
┌──────────────────────────────────────────────┐
│  Discovery & Negotiation                     │
│  Gensyn AXL — encrypted P2P transport        │
│  RFQ broadcast → signed quotes returned      │
└──────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────┐
│  Identity & Reputation                       │
│  ERC-8004 — on-chain agent ID + rep score    │
│  Matching: score = confidence × rep / price  │
└──────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────┐
│  Execution & Settlement                      │
│  KeeperHub workflows + Escrow                │
│  lockFunds → confirmDelivery                 │
│  → optimisticRelease → ERC-8004 feedback     │
└──────────────────────────────────────────────┘
```

## Trade flow

```
Buyer                    AXL                   Seller
  │── broadcast RFQ ────►│────────────────────►│
  │                      │       ◄─── Quote ───│
  │   pick best quote    │                     │
  │── KeeperHub lock ───────────── (TxID #1)   │
  │── "locked" trigger ─►│────────────────────►│
  │                      │   run task + hash   │
  │                      │   confirmDelivery ──────── (TxID #2)
  │                      │◄── DeliveryPayload ─│
  │   verify hash        │                     │
  │── KeeperHub release ────────── (TxID #3)   │
  │── ERC-8004 feedback ────────── (TxID #4)   │
```

Uniswap is used as a real quote/check proof for supported Base tokens; the demo
settlement path uses MockUSDC on Base Sepolia and does not claim a swap tx.

## Quick start

```bash
pip install -e '.[dev]'

# local chain
anvil
bash scripts/deploy_contracts.sh

# deterministic terminal walkthrough
PYTHONPATH=. python scripts/run_demo.py

# terminal 1: local market service for SDK listing publish
PYTHONPATH=. python scripts/serve_trade_playback.py

# terminal 2: open-box external seller SDK; publishes a matchable agent
PYTHONPATH=. python examples/seller_sdk_quickstart.py

# Gensyn AXL P2P demo; seller also executes the market-data worker
bash scripts/start_gensyn_axl_nodes.sh
PYTHONPATH=. python scripts/run_axl_demo.py --external

# local AXL replay (spins up mock nodes)
PYTHONPATH=. python scripts/run_axl_demo.py

# tests
PYTHONPATH=. python -m pytest tests/ -q
```

For external seller onboarding, see [`docs/agent-integration.md`](docs/agent-integration.md).
For the full documentation index, see [`docs/README.md`](docs/README.md).
For hackathon submission details, live/testnet setup, and sponsor mapping, see
[`docs/submission/SUBMISSION.md`](docs/submission/SUBMISSION.md). For AI usage
and reused dependency notes, see [`docs/submission/AI_USAGE.md`](docs/submission/AI_USAGE.md),
[`docs/submission/DEVELOPMENT_PROCESS.md`](docs/submission/DEVELOPMENT_PROCESS.md),
[`docs/submission/HACKATHON_NOTES.md`](docs/submission/HACKATHON_NOTES.md), and
[`docs/integrations/gensyn-axl.md`](docs/integrations/gensyn-axl.md).

## Script Index

- Demo paths: `scripts/run_demo.py`, `scripts/run_demo.sh`, `scripts/run_axl_demo.py`.
- SDK/local market: `scripts/serve_trade_playback.py`, `examples/seller_sdk_quickstart.py`.
- Setup: `scripts/deploy_contracts.sh`, `scripts/deploy_erc8004_registries.sh`,
  `scripts/prepare_testnet_funds.sh`, `scripts/register_erc8004_agent.py`.
- Diagnostics: `scripts/check_env.py`, `scripts/check_gensyn_axl.py`,
  `scripts/axl_mock_node.py`, `scripts/start_axl_nodes.sh`,
  `scripts/start_gensyn_axl_nodes.sh`.
- Sponsor proof scripts: `scripts/test_uniswap_quote.py`,
  `scripts/test_erc8004_feedback.py`, `scripts/test_keeperhub_release.py`.

## Repo layout

```
contracts/
  AgentBazaarEscrow.sol     per-deal state machine: LOCKED→DELIVERED→RELEASED
  MockUSDC.sol              mintable ERC-20 for local dev
  test/                     7 Foundry tests

agents/
  sdk.py                    open-box Python SDK for external seller integration
  buyer_agent.py            RFQ → quotes → Uniswap quote → lock → verify
  seller_agent.py           receive RFQ → quote → execute → deliver
  lib/
    axl_client.py           Gensyn AXL HTTP transport
    keeperhub_client.py     KeeperHub lock/release/refund
    uniswap_client.py       Uniswap Trade API quote/check proof
    erc8004_client.py       ERC-8004 registry
    matching.py             reputation-weighted quote ranking
    signing.py              ed25519 canonical JSON signing
    threat_defense.py       replay guard, schema hardening

schemas/
  rfq.py                    RFQMessage (Pydantic v2, signed)
  quote.py                  QuoteMessage + DeliveryPayload

scripts/
  run_demo.py               in-process demo with deterministic proof refs
  run_axl_demo.py           full AXL P2P integration demo, with --external for Gensyn
  check_gensyn_axl.py       topology/send/recv smoke test for real Gensyn AXL nodes
  axl_mock_node.py          local replay node for no-install demos
  deploy_contracts.sh       foundry deploy to Anvil

examples/
  seller_sdk_quickstart.py  copy-paste seller integration using AgentBazaarSeller

docs/
  agent-integration.md      external agent SDK integration guide
  submission/               hackathon submission, AI usage, process notes
  integrations/             AXL and KeeperHub integration notes
  sponsors/                 sponsor feedback artifacts
```
