#!/usr/bin/env bash
# End-to-end demo: fires one RFQ, matches a quote, runs the full settlement path.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a; source .env; set +a

python -m agents.seller_agent &
SELLER_PID=$!
sleep 2

python -m agents.buyer_agent \
  --task "fetch ETH/USDC spot" \
  --budget 500000 \
  --require-tee

trap "kill $SELLER_PID" EXIT
wait
