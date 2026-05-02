#!/usr/bin/env bash
# Start two mock AXL nodes (buyer :9001, seller :9002) for local development.
# Uses scripts/axl_mock_node.py — no external Gensyn binary needed.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}

echo "▶ Starting AXL buyer  node on :9001"
PYTHONPATH=. $PYTHON scripts/axl_mock_node.py --port 9001 --name buyer \
    --peers http://localhost:9002 &
BUYER_PID=$!

sleep 0.5

echo "▶ Starting AXL seller node on :9002"
PYTHONPATH=. $PYTHON scripts/axl_mock_node.py --port 9002 --name seller \
    --peers http://localhost:9001 &
SELLER_PID=$!

echo "✓ Both AXL nodes up (buyer PID=$BUYER_PID, seller PID=$SELLER_PID)"
echo "  Topology:  http://localhost:9001/topology"
echo "  Health:    http://localhost:9001/health"

trap "echo 'stopping AXL nodes…'; kill $BUYER_PID $SELLER_PID 2>/dev/null || true" EXIT
wait
