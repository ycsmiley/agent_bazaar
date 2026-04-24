#!/usr/bin/env bash
# Deploy AgentBazaarEscrow to Base Sepolia.
# Prereqs: foundry installed, .env populated with RPC_URL + BUYER_PRIVATE_KEY.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a; source .env; set +a

forge create \
  --rpc-url "$RPC_URL" \
  --private-key "$BUYER_PRIVATE_KEY" \
  contracts/AgentBazaarEscrow.sol:AgentBazaarEscrow
