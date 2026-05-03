#!/usr/bin/env bash
# Deploy Agent Bazaar's minimal ERC-8004 identity + reputation registries.
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
  shift || true
  forge create \
    --broadcast \
    --rpc-url "$RPC_URL" \
    --private-key "$BUYER_PRIVATE_KEY" \
    "$target" "$@"
}

extract_address() {
  awk '
    /Deployed to:/ { print $3; found=1 }
    /Contract Address:/ { print $3; found=1 }
    END { if (!found) exit 1 }
  '
}

echo "Deploying AgentIdentityRegistry..."
IDENTITY_OUTPUT="$(deploy contracts/AgentIdentityRegistry.sol:AgentIdentityRegistry)"
echo "$IDENTITY_OUTPUT"
IDENTITY_ADDRESS="$(printf '%s\n' "$IDENTITY_OUTPUT" | extract_address)"

echo
echo "Deploying AgentReputationRegistry..."
REPUTATION_OUTPUT="$(deploy contracts/AgentReputationRegistry.sol:AgentReputationRegistry --constructor-args "$IDENTITY_ADDRESS")"
echo "$REPUTATION_OUTPUT"
REPUTATION_ADDRESS="$(printf '%s\n' "$REPUTATION_OUTPUT" | extract_address)"

cat <<EOF

Add these to .env:

ERC8004_IDENTITY_REGISTRY=$IDENTITY_ADDRESS
ERC8004_REPUTATION_REGISTRY=$REPUTATION_ADDRESS

Next:
  1. Register the seller agent with scripts/register_erc8004_agent.py.
  2. Run a trade and buyer feedback will submit on-chain.
EOF
