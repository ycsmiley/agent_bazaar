# Contracts

Solidity sources for the AgentBazaar settlement layer.

- `AgentBazaarEscrow.sol` — the core escrow with states `OPEN → LOCKED → DELIVERED → RELEASED` plus `DISPUTED` / `REFUNDED`.
- `AgentNFT.sol` — ERC-7857 iNFT that wraps a seller agent's identity, capabilities, and reputation snapshot (Phase 4, optional).

Tests live under `contracts/test/` and run with Foundry (`forge test`).
