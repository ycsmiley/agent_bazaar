# AgentBazaar

**Decentralized spot market protocol for AI agents — closing the x402 trust gap.**

Targeting hackathon tracks: **Gensyn AXL · KeeperHub · Uniswap · 0G Track B**

---

## 1. Positioning

AgentBazaar is a decentralized spot-market protocol for agent-to-agent commerce. It closes the trust gap in x402's "pay-then-deliver" model by letting agents autonomously discover counterparties, negotiate, pay, and verify delivery — all without human intervention.

## 2. Problem

The agent economy (projected >$600M in 2026) suffers from three structural defects:

1. **Pay-then-deliver trust cliff** — x402 is final and non-refundable; no recourse against fraud or hallucination.
2. **No dynamic negotiation layer** — existing protocols only support fixed price / subscriptions.
3. **No portable agent reputation** — ERC-8004 is live, but agent history is fragmented across centralized platforms.

## 3. Four-Layer Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: Memory & Verifiable Inference                      │
│  Powered by: 0G Storage + 0G Compute                         │
│  Agent capability registry, transaction history, TeeML proofs│
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: Discovery & Negotiation                            │
│  Powered by: Gensyn AXL                                      │
│  Encrypted P2P RFQ broadcast + quote return                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 2: Identity & Reputation                              │
│  Powered by: ERC-8004                                        │
│  On-chain agent ID + portable reputation score               │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: Execution & Settlement                             │
│  Powered by: KeeperHub Workflow + Uniswap + Escrow contract  │
│  Funds locking, conditional release, multi-token bridge      │
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

One-liner: **the only protocol that combines decentralized discovery + escrow + ERC-8004 identity + EVM-native + dynamic pricing.**

## 5. Repository Layout

```
agentbazaar/
├── contracts/                # Solidity: Escrow + iNFT (ERC-7857)
│   └── test/
├── agents/                   # Python: buyer + seller agents
│   └── lib/
│       ├── axl_client.py
│       ├── keeperhub_client.py
│       ├── uniswap_client.py
│       ├── og_storage_client.py
│       ├── og_compute_client.py
│       └── erc8004_client.py
├── schemas/                  # Pydantic schemas for RFQ / Quote / Delivery
├── scripts/                  # deploy + demo runners
└── demo/                     # 3-minute demo video
```

## 6. Sponsor Track Mapping

| Track              | Prize   | How AgentBazaar Qualifies                                                                 |
|--------------------|---------|-------------------------------------------------------------------------------------------|
| Gensyn AXL         | $5,000  | RFQ broadcast + encrypted quote return run entirely over AXL — removing it kills discovery|
| KeeperHub          | $5,500  | Three on-chain workflows (lock / optimistic-release / timeout-refund) with retry + audit  |
| Uniswap            | $5,000  | ETH→USDC pre-lock swap + seller preferred-token post-release swap, with real TxIDs        |
| 0G Track B         | $7,500  | Buyer/seller agent swarm with 0G Storage persistent memory + 0G Compute TeeML proofs       |

**Total prize pool targeted: $22,500** · Conservative take: $4,500–$8,000.

## 7. Build Timeline (10 days, solo)

| Day | Goal                            | Output                                       |
|-----|---------------------------------|----------------------------------------------|
| 1   | Environment + scaffolding       | Repo layout, deps, `.env.example`            |
| 2   | Escrow contract                 | `AgentBazaarEscrow.sol` + tests + deployment |
| 3   | AXL transport                   | RFQ broadcast + Quote return working          |
| 4   | KeeperHub workflows             | Lock + Release workflow with live TxIDs      |
| 5   | Uniswap integration             | ETH→USDC swap TxID                            |
| 6   | 0G Storage                      | Capabilities + history read/write            |
| 7   | ERC-8004 + matching algorithm   | Reputation-weighted quote selection          |
| 8   | 0G Compute                      | TeeML sealed-inference + verification        |
| 9   | iNFT + defence hardening        | ERC-7857 mint + schema validation hardened   |
| 10  | Delivery                        | Demo video, README, FEEDBACK.md              |

Hard floor: Days 1–5. Days 6–8 are scoring multipliers. Day 9 is a bonus.

## 8. Visible TxIDs During Demo

1. Uniswap ETH→USDC swap
2. `escrow.lockFunds()`
3. `escrow.confirmDelivery()`
4. `escrow.releaseFunds()` (or `optimisticRelease()` via KeeperHub)
5. `erc8004.submitFeedback()`

---

**Status:** 🚧 In active development for hackathon submission.
