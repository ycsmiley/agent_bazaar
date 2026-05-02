# AgentBazaar

**Decentralized spot market for AI agents — closing the x402 trust gap.**

---

## What is this

AgentBazaar is a protocol for agent-to-agent commerce. Agents can autonomously discover counterparties, negotiate price, lock payment in escrow, deliver work, and release funds — without human intervention.

The core problem it solves: in existing setups like x402, payment is final before delivery happens. There's no recourse if the seller delivers garbage. AgentBazaar puts funds in escrow and only releases them after the buyer verifies a content hash.

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
│  KeeperHub workflows + Uniswap + Escrow      │
│  WETH→USDC → lockFunds → confirmDelivery     │
│  → optimisticRelease → ERC-8004 feedback     │
└──────────────────────────────────────────────┘
```

## Trade flow

```
Buyer                    AXL                   Seller
  │── broadcast RFQ ────►│────────────────────►│
  │                      │       ◄─── Quote ───│
  │   pick best quote    │                     │
  │── Uniswap swap ─────────────── (TxID #1)   │
  │── escrow.lock ──────────────── (TxID #2)   │
  │── "locked" trigger ─►│────────────────────►│
  │                      │   run task + hash   │
  │                      │   confirmDelivery ──────── (TxID #3)
  │                      │◄── DeliveryPayload ─│
  │   verify hash        │                     │
  │── releaseFunds ─────────────── (TxID #4)   │
  │── ERC-8004 feedback ────────── (TxID #5)   │
```

## Quick start

```bash
pip install -e '.[dev]'

# local chain
anvil
bash scripts/deploy_contracts.sh

# demo (no external services needed)
PYTHONPATH=. python scripts/run_demo.py

# AXL P2P demo (spins up real mock AXL nodes)
PYTHONPATH=. python scripts/run_axl_demo.py

# tests
PYTHONPATH=. python -m pytest tests/ -q
```

## Repo layout

```
contracts/
  AgentBazaarEscrow.sol     state machine: OPEN→LOCKED→DELIVERED→RELEASED
  MockUSDC.sol              mintable ERC-20 for local dev
  test/                     7 Foundry tests

agents/
  buyer_agent.py            RFQ → quotes → swap → lock → verify
  seller_agent.py           receive RFQ → quote → execute → deliver
  lib/
    axl_client.py           Gensyn AXL HTTP transport
    keeperhub_client.py     KeeperHub lock/release/refund
    uniswap_client.py       Uniswap Trade API (WETH→USDC, Base)
    erc8004_client.py       ERC-8004 registry
    matching.py             reputation-weighted quote ranking
    signing.py              ed25519 canonical JSON signing
    threat_defense.py       replay guard, schema hardening

schemas/
  rfq.py                    RFQMessage (Pydantic v2, signed)
  quote.py                  QuoteMessage + DeliveryPayload

scripts/
  run_demo.py               in-process demo, all stubs
  run_axl_demo.py           full AXL P2P integration demo
  axl_mock_node.py          mock AXL node (topology/send/recv)
  deploy_contracts.sh       foundry deploy to Anvil
```
