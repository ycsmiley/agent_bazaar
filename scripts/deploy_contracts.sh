#!/usr/bin/env bash
# Deploy MockUSDC + AgentBazaarEscrow to a testnet/local chain.
# Prereqs: foundry installed, .env populated with RPC_URL + BUYER_PRIVATE_KEY.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example and fill RPC_URL + BUYER_PRIVATE_KEY first." >&2
  exit 1
fi

eval "$(python scripts/export_env.py .env)"

: "${RPC_URL:?RPC_URL is required}"
: "${BUYER_PRIVATE_KEY:?BUYER_PRIVATE_KEY is required}"

deploy() {
  local target="$1"
  forge create \
    --broadcast \
    --rpc-url "$RPC_URL" \
    --private-key "$BUYER_PRIVATE_KEY" \
    "$target"
}

extract_address() {
  awk '
    /Deployed to:/ { print $3; found=1 }
    /Contract Address:/ { print $3; found=1 }
    END { if (!found) exit 1 }
  '
}

echo "Deploying MockUSDC..."
MOCK_USDC_OUTPUT="$(deploy contracts/MockUSDC.sol:MockUSDC)"
echo "$MOCK_USDC_OUTPUT"
MOCK_USDC_ADDRESS="$(printf '%s\n' "$MOCK_USDC_OUTPUT" | extract_address)"

echo
echo "Deploying AgentBazaarEscrow..."
ESCROW_OUTPUT="$(deploy contracts/AgentBazaarEscrow.sol:AgentBazaarEscrow)"
echo "$ESCROW_OUTPUT"
ESCROW_ADDRESS_OUT="$(printf '%s\n' "$ESCROW_OUTPUT" | extract_address)"

cat <<EOF

Add these to .env for the local/testnet demo:

ESCROW_ADDRESS=$ESCROW_ADDRESS_OUT
USDC_ADDRESS=$MOCK_USDC_ADDRESS

Next:
  1. Mint MockUSDC to the buyer wallet.
  2. Approve ESCROW_ADDRESS to spend the buyer's MockUSDC.
  3. Run scripts/run_demo.sh --live once AXL + KeeperHub are configured.
EOF
