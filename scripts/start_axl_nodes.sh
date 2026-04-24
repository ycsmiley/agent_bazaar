#!/usr/bin/env bash
# Start two AXL nodes (buyer + seller) for local development.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Starting AXL buyer node on :9001"
axl start --port 9001 --peer-id-file .agentbazaar/buyer.peer.json &
BUYER_PID=$!

echo "Starting AXL seller node on :9002"
axl start --port 9002 --peer-id-file .agentbazaar/seller.peer.json &
SELLER_PID=$!

trap "kill $BUYER_PID $SELLER_PID" EXIT
wait
