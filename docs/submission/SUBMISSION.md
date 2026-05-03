# Agent Bazaar Submission Guide

## Summary

Agent Bazaar is an AI task exchange for idle agent capacity. A buyer agent broadcasts an RFQ over Gensyn AXL, seller agents return signed quotes, the buyer ranks them by price, confidence, and reputation, then payment is locked in escrow until the buyer verifies the delivered content hash.

The core problem is fragmented AI usage. Some agents, accounts, or operators have capacity they are not using, while other agents have tasks they need to outsource. Agent Bazaar lets agents buy and sell task execution directly, without selling traffic and without paying before delivery is verified.

The escrow contract is a per-deal settlement primitive. The market is formed by the surrounding RFQ broadcast, seller quotes, matching algorithm, ERC-8004 identity/reputation, delivery payloads, and KeeperHub settlement workflows.

## Demo Paths

- Offline demo: `PYTHONPATH=. python scripts/run_demo.py`
- Gensyn AXL P2P demo: `PYTHONPATH=. python scripts/run_axl_demo.py --external`
- Local AXL replay: `PYTHONPATH=. python scripts/run_axl_demo.py`
- Live/testnet setup:
  1. Copy `.env.example` to `.env` and fill wallet/RPC/sponsor settings.
  2. Deploy contracts with `bash scripts/deploy_contracts.sh`.
  3. For MockUSDC demos, fund and approve with `bash scripts/prepare_testnet_funds.sh`.
  4. Start Gensyn AXL nodes, set `BUYER_AXL_PEER_ID` / `SELLER_AXL_PEER_ID`,
     then run `PYTHONPATH=. python scripts/run_axl_demo.py --external`.

The offline demo is deterministic and uses stub transaction hashes for recording. The live/testnet path is the credibility path: deployed escrow, real wallets, real RPC, and real sponsor endpoints where configured.

## Sponsor Usage

| Sponsor | What Agent Bazaar Uses |
| --- | --- |
| Gensyn AXL | RFQ broadcast, signed quote return, locked trigger, and delivery payloads across buyer/seller agent nodes. |
| KeeperHub | Reliable onchain execution for lock, optimistic release, and timeout refund workflows. |
| Uniswap | Real `/check_approval` + `/quote` proof for supported Base tokens; settlement uses MockUSDC separately and does not claim a swap tx. |

## Submission Form Fields

- Project name: Agent Bazaar
- One-liner: AI task exchange for idle agent capacity.
- Repository: TODO — paste public GitHub URL after pushing.
- Live demo: `PYTHONPATH=. python scripts/run_axl_demo.py` for the local AXL replay, or `PYTHONPATH=. python scripts/run_axl_demo.py --external` when Gensyn AXL nodes are available.
- Demo video: TODO — upload 2-4 minute video in ETHGlobal dashboard.
- Team members: TODO — add names.
- Contact info: TODO — add Telegram and X handles.
- AI usage disclosure: see [`AI_USAGE.md`](AI_USAGE.md).
- New vs reused work: see [`HACKATHON_NOTES.md`](HACKATHON_NOTES.md).
- Development process and team direction: see [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md).
- Gensyn AXL notes: see [`../integrations/gensyn-axl.md`](../integrations/gensyn-axl.md).

## Deployment Addresses

- Network: Base Sepolia
- MockUSDC: `0x8F8De0c9885267F715673F8932482981a98405f8`
- AgentBazaarEscrow: `0x03C71Cf61c066479904A1800e2DCaf832ba59B1E`
- MockUSDC deploy tx: `0x15323003c14d5bf8a1ce1374c3ee407cca1428795861c0a70fbea7cc9da295a1`
- Escrow deploy tx: `0x14794536036e8180c440420f3b04750cf8f7985075b2b135ba230826ee725601`
- Buyer funding tx: `0x7a2335c2438dbec675131129f46f8624bca4b747457ef9abf6270ff8055e3be9`
- Escrow approval tx: `0xe720235638ffd01f0ee263350d9549036d17cc0f3dff742feff6d593cbe4e149`
- ERC-8004 Identity Registry: `0xD966F2F92543938e26b3376DD8c60F047F226242`
- ERC-8004 Reputation Registry: `0xEFD0c238D18188df7599E403C3DBdBba56C1e4b5`
- ERC-8004 identity deploy tx: `0x354da3eac8aeddd5dddd53d69c480b38cc2b88eb3bedaaf681f97cde42565fc8`
- ERC-8004 reputation deploy tx: `0x4d79801c887d5ae399b42e9afef7a15caf606b4775c53b039504fc81d0e50256`
- Seller agent registration tx: `0x954bcc0ac68325602cf7e41de32efbf3bd6880266818cbf63d71fac29150206c`
- Buyer feedback tx: `0x691486874b1a7b64f2ac7f337e9e97657676fe9b8bac90bec44ee72377f7d9d0`

## KeeperHub Test Runs

- Lock workflow: execution `ibah7qj9w7hhbrgho35az`, RFQ `0xa98c4345f5ec4ddfb36d7d3bdcf16c8000000000000000000000000000000000`, final state `LOCKED`.
- Optimistic release workflow: execution `s7h6f1ovv98tt113gq7d5`, same RFQ, final state `RELEASED`.
- Timeout refund workflow: execution `mekgig98lj7vbumrmqiph`, RFQ `0x455580e9c59b49f0bfa6936af3bd078800000000000000000000000000000000`, final state `REFUNDED`.

## Uniswap API Proof

- Endpoint: `POST https://trade-api.gateway.uniswap.org/v1/quote`
- Chain: Base mainnet (`8453`)
- Pair: native ETH -> USDC
- Quote id: `52cdda69-9996-4b58-9101-d1451f44d8f0`
- Route: V3 pool `0xb4CB800910B228ED3d0834cF79D697127BBB00e5`
- Note: Settlement uses Base Sepolia MockUSDC separately; we do not claim a Uniswap swap tx for the escrow path.

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
PYTHONPATH=. python scripts/check_gensyn_axl.py --role buyer
PYTHONPATH=. python scripts/run_axl_demo.py
PYTHONPATH=. python scripts/run_axl_demo.py --external
PYTHONPATH=. python scripts/test_uniswap_quote.py
PYTHONPATH=. python scripts/test_erc8004_feedback.py
```

## Submission Checklist

- Public GitHub repository with setup instructions.
- Contract deployment addresses for `AgentBazaarEscrow`, ERC-8004 registries, and demo USDC/token.
- Demo video between 2 and 4 minutes.
- Live demo link or reproducible local/testnet command.
- Team member names and contact info.
- Sponsor explanation and feedback artifacts.
