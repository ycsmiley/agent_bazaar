#!/usr/bin/env bash
# Mint MockUSDC to the buyer and approve the escrow for demo settlement.
# Use this only when USDC_ADDRESS points at the deployed MockUSDC contract.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example and fill deployment settings first." >&2
  exit 1
fi

eval "$(python scripts/export_env.py .env)"

: "${RPC_URL:?RPC_URL is required}"
: "${BUYER_PRIVATE_KEY:?BUYER_PRIVATE_KEY is required}"
: "${ESCROW_ADDRESS:?ESCROW_ADDRESS is required}"
: "${USDC_ADDRESS:?USDC_ADDRESS is required}"

BUYER_ADDRESS="${BUYER_ADDRESS:-$(cast wallet address --private-key "$BUYER_PRIVATE_KEY")}"
MINT_AMOUNT="${MINT_AMOUNT:-10000000}" # 10 USDC with 6 decimals
APPROVE_AMOUNT="${APPROVE_AMOUNT:-10000000}"

echo "Buyer:        $BUYER_ADDRESS"
echo "MockUSDC:     $USDC_ADDRESS"
echo "Escrow:       $ESCROW_ADDRESS"
echo "Mint amount:  $MINT_AMOUNT"
echo "Approve amt:  $APPROVE_AMOUNT"
echo

echo "Minting MockUSDC to buyer..."
cast send "$USDC_ADDRESS" \
  "mint(address,uint256)" "$BUYER_ADDRESS" "$MINT_AMOUNT" \
  --rpc-url "$RPC_URL" \
  --private-key "$BUYER_PRIVATE_KEY"

echo
echo "Approving escrow..."
cast send "$USDC_ADDRESS" \
  "approve(address,uint256)" "$ESCROW_ADDRESS" "$APPROVE_AMOUNT" \
  --rpc-url "$RPC_URL" \
  --private-key "$BUYER_PRIVATE_KEY"

echo
echo "Ready: buyer has MockUSDC and escrow allowance for the live/testnet demo."
