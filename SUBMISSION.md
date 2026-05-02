# AgentBazaar Submission Guide

## Summary

AgentBazaar is a decentralized spot market for AI agents. A buyer agent broadcasts an RFQ over Gensyn AXL, sellers return signed quotes, the buyer ranks them by price, confidence, and reputation, then payment is locked in escrow until the buyer verifies the delivered content hash.

The core problem is the x402-style trust gap: pay-before-delivery works poorly when the seller is an autonomous agent. AgentBazaar turns the trade into a small settlement protocol with lock, delivery, dispute, release, and refund paths.

## Demo Paths

- Offline demo: `PYTHONPATH=. python scripts/run_demo.py`
- AXL P2P demo: `PYTHONPATH=. python scripts/run_axl_demo.py`
- Live/testnet setup:
  1. Copy `.env.example` to `.env` and fill wallet/RPC/sponsor settings.
  2. Deploy contracts with `bash scripts/deploy_contracts.sh`.
  3. For MockUSDC demos, fund and approve with `bash scripts/prepare_testnet_funds.sh`.
  4. Start AXL nodes, then run `bash scripts/run_demo.sh --live`.

The offline demo is deterministic and uses stub transaction hashes for recording. The live/testnet path is the credibility path: deployed escrow, real wallets, real RPC, and real sponsor endpoints where configured.

## Sponsor Usage

| Sponsor | What AgentBazaar Uses |
| --- | --- |
| Gensyn AXL | RFQ broadcast, signed quote return, locked trigger, and delivery payloads across buyer/seller agent nodes. |
| KeeperHub | Reliable onchain execution for lock, optimistic release, and timeout refund workflows. |
| Uniswap | Buyer-side token conversion into USDC before escrow settlement; repo includes `FEEDBACK.md` for API builder feedback. |
| ENS | Optional identity/discovery layer for replacing raw seller addresses with agent names and metadata. |

## Deployment Addresses

- Network: Base Sepolia
- MockUSDC: `0x8F8De0c9885267F715673F8932482981a98405f8`
- AgentBazaarEscrow: `0x03C71Cf61c066479904A1800e2DCaf832ba59B1E`
- MockUSDC deploy tx: `0x15323003c14d5bf8a1ce1374c3ee407cca1428795861c0a70fbea7cc9da295a1`
- Escrow deploy tx: `0x14794536036e8180c440420f3b04750cf8f7985075b2b135ba230826ee725601`
- Buyer funding tx: `0x7a2335c2438dbec675131129f46f8624bca4b747457ef9abf6270ff8055e3be9`
- Escrow approval tx: `0xe720235638ffd01f0ee263350d9549036d17cc0f3dff742feff6d593cbe4e149`

## KeeperHub Test Runs

- Lock workflow: execution `ibah7qj9w7hhbrgho35az`, RFQ `0xa98c4345f5ec4ddfb36d7d3bdcf16c8000000000000000000000000000000000`, final state `LOCKED`.
- Optimistic release workflow: execution `s7h6f1ovv98tt113gq7d5`, same RFQ, final state `RELEASED`.
- Timeout refund workflow: execution `mekgig98lj7vbumrmqiph`, RFQ `0x455580e9c59b49f0bfa6936af3bd078800000000000000000000000000000000`, final state `REFUNDED`.

## What Judges Should Look For

- AXL is used for inter-agent communication, not as a cosmetic log line.
- Escrow state transitions encode the trust guarantees: `LOCKED`, `DELIVERED`, `RELEASED`, `DISPUTED`, and `REFUNDED`.
- Buyer verification is simple and inspectable: canonical JSON content hash must match the seller's onchain commitment.
- KeeperHub removes the need for buyer/seller agents to stay online for every settlement edge case.
- Uniswap makes payment denomination flexible while escrow remains USDC-denominated.

## Test Commands

```bash
PYTHONPATH=. python -m pytest tests/ -q
forge test -q
PYTHONPATH=. python scripts/run_demo.py
PYTHONPATH=. python scripts/run_axl_demo.py
```

## Submission Checklist

- Public GitHub repository with setup instructions.
- Contract deployment addresses for `AgentBazaarEscrow` and demo USDC/token.
- Demo video under three minutes.
- Live demo link or reproducible local/testnet command.
- Team member names and contact info.
- Sponsor explanation and feedback artifacts.
