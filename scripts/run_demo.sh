#!/usr/bin/env bash
# End-to-end demo: fires one RFQ, matches a quote, runs the full settlement path.
#
# Two modes:
#   ./run_demo.sh          — in-process demo (no sponsor APIs needed, good for video)
#   ./run_demo.sh --live   — real buyer + seller against live endpoints in .env
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--live" ]]; then
  if [[ ! -f .env ]]; then
    echo "Missing .env. Copy .env.example and fill live/testnet settings first." >&2
    exit 1
  fi
  eval "$(python scripts/export_env.py .env)"
  : "${RPC_URL:?RPC_URL is required}"
  : "${ESCROW_ADDRESS:?ESCROW_ADDRESS is required}"
  : "${USDC_ADDRESS:?USDC_ADDRESS is required}"
  : "${BUYER_PRIVATE_KEY:?BUYER_PRIVATE_KEY is required}"
  : "${SELLER_PRIVATE_KEY:?SELLER_PRIVATE_KEY is required}"
  : "${BUYER_AXL_ENDPOINT:?BUYER_AXL_ENDPOINT is required}"
  : "${SELLER_AXL_ENDPOINT:?SELLER_AXL_ENDPOINT is required}"

  python -m agents.seller_agent &
  SELLER_PID=$!
  trap "kill $SELLER_PID 2>/dev/null || true" EXIT
  sleep 2
  python -m agents.buyer_agent --task "fetch ETH/USDC spot" --budget 500000
  wait
else
  python scripts/run_demo.py
fi
