# AgentBazaar

**Decentralized spot market protocol for AI agents — closing the x402 trust gap.**

Targeting hackathon tracks: **Gensyn AXL · KeeperHub · Uniswap**

---

## 1. Positioning

AgentBazaar is a decentralized spot-market protocol for agent-to-agent commerce. It closes the trust gap in x402's "pay-then-deliver" model by letting agents autonomously discover counterparties, negotiate, pay, and verify delivery — all without human intervention.

## 2. Problem

The agent economy suffers from three structural defects:

1. **Pay-then-deliver trust cliff** — x402 is final and non-refundable; no recourse against fraud or hallucination.
2. **No dynamic negotiation layer** — existing protocols only support fixed price / subscriptions.
3. **No portable agent reputation** — ERC-8004 is live, but agent history is fragmented across centralized platforms.

## 3. Three-Layer Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: Discovery & Negotiation                            │
│  Powered by: Gensyn AXL                                      │
│  Encrypted P2P RFQ broadcast + signed quote return           │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 2: Identity & Reputation                              │
│  Powered by: ERC-8004                                        │
│  On-chain agent ID + portable reputation score               │
│  Reputation-weighted matching: score = confidence × rep / price│
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: Execution & Settlement                             │
│  Powered by: KeeperHub Workflow + Uniswap + Escrow contract  │
│  WETH→USDC swap · lock · confirmDelivery · optimisticRelease │
└──────────────────────────────────────────────────────────────┘
```

## 4. Differentiation

| Solution         | P2P Discovery | Escrow | ERC-8004 | EVM-native | Dynamic Pricing |
|------------------|---------------|--------|----------|------------|-----------------|
| **AgentBazaar**  | ✅ AXL        | ✅     | ✅       | ✅         | ✅              |
| x402             | ❌            | ❌     | ⚠️       | ✅         | ❌              |
| Merxex           | ❌            | ✅     | ❌       | ✅         | ❌              |
| NEAR AgentMarket | ❌            | ✅     | ❌       | ❌         | ⚠️              |
| PayCrow          | ❌            | ✅     | ❌       | ✅         | ❌              |

One-liner: **the only protocol that combines decentralized P2P discovery + escrow + ERC-8004 reputation + EVM-native + dynamic pricing.**

## 5. Quick Start

```bash
# 1. Install
pip install -e '.[dev]'

# 2. Start local Anvil chain (separate terminal)
anvil

# 3. Deploy contracts
bash scripts/deploy_contracts.sh

# 4. Run in-process demo (no sponsor APIs needed)
PYTHONPATH=. python scripts/run_demo.py

# 5. Run AXL P2P demo (exercises real Gensyn AXL transport layer)
PYTHONPATH=. python scripts/run_axl_demo.py

# 6. Run tests (35 passing)
PYTHONPATH=. python -m pytest tests/ -q
```

## 6. Repository Layout

```
agentbazaar/
├── contracts/
│   ├── AgentBazaarEscrow.sol   # State machine: OPEN→LOCKED→DELIVERED→RELEASED
│   ├── MockUSDC.sol            # Mintable ERC-20 for local dev
│   └── test/AgentBazaarEscrow.t.sol   # 7 Foundry tests
├── agents/
│   ├── buyer_agent.py          # RFQ → collect quotes → swap → lock → verify
│   ├── seller_agent.py         # Receive RFQ → quote → execute → deliver
│   └── lib/
│       ├── axl_client.py       # Gensyn AXL HTTP transport
│       ├── keeperhub_client.py # KeeperHub lock/release/refund workflows
│       ├── uniswap_client.py   # Uniswap Trade API (WETH→USDC on Base)
│       ├── erc8004_client.py   # ERC-8004 identity + reputation registry
│       ├── matching.py         # Reputation-weighted quote selection
│       ├── signing.py          # Ed25519 canonical JSON signing
│       └── threat_defense.py   # Replay guard, schema hardening
├── schemas/
│   ├── rfq.py                  # RFQMessage (Pydantic v2, signed)
│   └── quote.py                # QuoteMessage + DeliveryPayload (signed)
├── scripts/
│   ├── run_demo.py             # In-process demo (all paths stubbed)
│   ├── run_axl_demo.py         # Full AXL P2P integration demo
│   ├── axl_mock_node.py        # Mock AXL node (topology/send/recv)
│   ├── deploy_contracts.sh     # Foundry deploy to Anvil
│   └── start_axl_nodes.sh      # Start buyer+seller AXL nodes
├── FEEDBACK.md                 # Uniswap mandatory feedback
└── KEEPERHUB_FEEDBACK.md       # KeeperHub feedback bounty
```

## 7. Sponsor Track Mapping

| Track      | Prize   | Integration                                                                       |
|------------|---------|-----------------------------------------------------------------------------------|
| Gensyn AXL | $5,000  | All buyer↔seller messages travel over AXL (`axl_client.py` + `axl_mock_node.py`) |
| KeeperHub  | $5,500  | Three on-chain workflows: `lock` / `optimistic-release` / `timeout-refund`        |
| Uniswap    | $5,000  | WETH→USDC swap via Trade API before every escrow lock (`uniswap_client.py`)       |

**Total prize pool targeted: $15,500**

## 8. On-Chain Trade Flow

```
Buyer                     AXL                    Seller
  │                        │                        │
  │── broadcast RFQ ──────►│──────────────────────►│
  │                        │         ◄── Quote ─────│
  │   select_best()        │                        │
  │── Uniswap WETH→USDC ──►│  (TxID #1)             │
  │── KeeperHub lockFunds ►│  (TxID #2)             │
  │── "locked" trigger ───►│──────────────────────►│
  │                        │    run task + hash     │
  │                        │    confirmDelivery ─────│── (TxID #3)
  │                        │◄── DeliveryPayload ────│
  │   verify hash          │                        │
  │── KeeperHub release ──►│  (TxID #4)             │
  │── ERC-8004 feedback ──►│  (TxID #5)             │
```

## 9. Running the AXL Demo

```
$ PYTHONPATH=. python scripts/run_axl_demo.py

╭────────────────────────────────────────╮
│ AgentBazaar — AXL P2P Integration Demo │
╰─ Gensyn AXL transport · Uniswap swap ·─╯

→ RFQ efc618a7… broadcast (budget 500000 USDC atomic)
Seller received RFQ efc618a7…
Seller → Quote sent (price=420000)
← Quote from 0x5e5e5e5e5e  price=420000  rep=95.7%  tee=False
  Uniswap swap tx : 0x1111111111111111…
  Escrow lock tx  : 0x2222222222222222…
→ Locked trigger sent to seller
Seller received locked trigger for rfq=efc618a7…
  confirmDelivery : 0x3333333333333333…
Seller → DeliveryPayload sent hash=0x9cece92d…
← Delivery result_hash=0x9cece92d…  content keys=[…]
  Escrow release  : 0x4444444444444444…
  ERC-8004 feedback: 0x5555555555555555…

✓ Trade complete — RFQ → Quote → Lock → Deliver → Release
```

---

**Status:** ✅ All tracks implemented · 35 tests passing · Two runnable demos
