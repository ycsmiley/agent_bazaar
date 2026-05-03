# Gensyn AXL Integration

Agent Bazaar uses Gensyn AXL as the buyer/seller transport layer for agent-to-agent
market messages:

- buyer -> seller: signed RFQ
- seller -> buyer: signed quote
- buyer -> seller: escrow locked trigger
- seller -> buyer: signed delivery payload

## Official API Shape

The client follows the current Gensyn AXL HTTP API:

- `GET /topology` lists the local node and known peers.
- `POST /send` sends raw bytes to `X-Destination-Peer-Id`.
- `GET /recv` returns `204 No Content` when empty, or a raw body with
  `X-From-Peer-Id` when a message is available.

Implementation: [`../../agents/lib/axl_client.py`](../../agents/lib/axl_client.py).

## Real Gensyn Mode

Run two Gensyn AXL nodes and put their local API endpoints and public keys in
`.env`:

```bash
AXL_TRANSPORT=gensyn
BUYER_AXL_ENDPOINT=http://127.0.0.1:9002
SELLER_AXL_ENDPOINT=http://127.0.0.1:9012
BUYER_AXL_PEER_ID=<buyer node our_public_key>
SELLER_AXL_PEER_ID=<seller node our_public_key>
```

This repo includes a helper for the local two-node setup:

```bash
bash scripts/start_gensyn_axl_nodes.sh
```

Check each node:

```bash
PYTHONPATH=. python scripts/check_gensyn_axl.py --role buyer
PYTHONPATH=. python scripts/check_gensyn_axl.py --role seller
```

Send a cross-node ping:

```bash
PYTHONPATH=. python scripts/check_gensyn_axl.py --role buyer --send-to "$SELLER_AXL_PEER_ID"
PYTHONPATH=. python scripts/check_gensyn_axl.py --role seller --recv
```

Run the full RFQ/quote/delivery sequence across real AXL nodes:

```bash
PYTHONPATH=. python scripts/run_axl_demo.py --external
```

## Local Replay Mode

For judges who do not have a Gensyn node installed, the repo also includes a
local mock that implements the older local-demo endpoints. This is only a
repeatable replay path; the production client defaults to `AXL_TRANSPORT=gensyn`.

```bash
PYTHONPATH=. python scripts/run_axl_demo.py
```

The local replay still uses two isolated node endpoints:

- buyer node: `http://localhost:19001`
- seller node: `http://localhost:19002`

## Demo Claim

The Gensyn claim should be:

> Agent Bazaar routes marketplace negotiation over Gensyn AXL: RFQs, quotes,
> lock triggers, and delivery payloads move between separate AXL nodes before
> KeeperHub executes escrow settlement.

Do not describe the local mock as the sponsor integration. The sponsor demo path
is `scripts/run_axl_demo.py --external` after real AXL nodes are running.
