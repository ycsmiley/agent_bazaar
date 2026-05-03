#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AXL_DIR="$ROOT/.agentbazaar/axl"
GO_BIN="${GO_BIN:-/opt/homebrew/opt/go@1.25/bin/go}"

if [[ ! -d "$AXL_DIR/.git" ]]; then
  echo "Missing $AXL_DIR. Run:"
  echo "  git clone https://github.com/gensyn-ai/axl $AXL_DIR"
  exit 1
fi

cd "$AXL_DIR"

if [[ ! -x ./node ]]; then
  if [[ ! -x "$GO_BIN" ]]; then
    GO_BIN="$(command -v go || true)"
  fi
  if [[ -z "$GO_BIN" ]]; then
    echo "Go is required. Recommended: brew install go@1.25"
    exit 1
  fi
  "$GO_BIN" build -o node ./cmd/node/
fi

if [[ ! -f buyer-private.pem ]]; then
  openssl genpkey -algorithm ed25519 -out buyer-private.pem
fi

if [[ ! -f seller-private.pem ]]; then
  openssl genpkey -algorithm ed25519 -out seller-private.pem
fi

cat > buyer-config.json <<'JSON'
{
  "PrivateKeyPath": "buyer-private.pem",
  "Listen": ["tls://127.0.0.1:9101"],
  "Peers": [],
  "api_port": 9002,
  "bridge_addr": "127.0.0.1",
  "tcp_port": 7000
}
JSON

cat > seller-config.json <<'JSON'
{
  "PrivateKeyPath": "seller-private.pem",
  "Listen": [],
  "Peers": ["tls://127.0.0.1:9101"],
  "api_port": 9012,
  "bridge_addr": "127.0.0.1",
  "tcp_port": 7000
}
JSON

./node -config buyer-config.json &
BUYER_PID=$!
sleep 1

./node -config seller-config.json &
SELLER_PID=$!
sleep 2

echo
echo "Gensyn AXL nodes are running."
echo "buyer endpoint:  http://127.0.0.1:9002"
echo "seller endpoint: http://127.0.0.1:9012"
echo
echo "Copy these peer ids into .env if they changed:"
curl -s http://127.0.0.1:9002/topology | python -m json.tool
curl -s http://127.0.0.1:9012/topology | python -m json.tool
echo
echo "Press Ctrl-C to stop both AXL nodes."

trap 'kill "$BUYER_PID" "$SELLER_PID" 2>/dev/null || true' EXIT
wait
