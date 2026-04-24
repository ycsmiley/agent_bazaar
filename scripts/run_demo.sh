#!/usr/bin/env bash
# End-to-end demo: fires one RFQ, matches a quote, runs the full settlement path.
#
# Two modes:
#   ./run_demo.sh          — in-process demo (no sponsor APIs needed, good for video)
#   ./run_demo.sh --live   — real buyer + seller against live endpoints in .env
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--live" ]]; then
  set -a; source .env; set +a
  python -m agents.seller_agent &
  SELLER_PID=$!
  sleep 2
  python -m agents.buyer_agent --task "fetch ETH/USDC spot" --budget 500000 --require-tee
  trap "kill $SELLER_PID" EXIT
  wait
else
  python scripts/run_demo.py
fi
