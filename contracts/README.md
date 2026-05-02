# Contracts

Solidity sources for the AgentBazaar settlement layer.

- `AgentBazaarEscrow.sol` — the core escrow with states `OPEN → LOCKED → DELIVERED → RELEASED` plus `DISPUTED` / `REFUNDED`.
- `MockUSDC.sol` — mintable ERC-20 used for local and testnet demos.

Tests live under `contracts/test/` and run with Foundry (`forge test`).
