# Gensyn AXL Integration Notes

## Current State

Agent Bazaar has an AXL-shaped transport client and a two-node P2P demo:

- [`agents/lib/axl_client.py`](agents/lib/axl_client.py) wraps the control-plane
  verbs the buyer/seller agents need: topology, send, broadcast, and inbox.
- [`scripts/axl_mock_node.py`](scripts/axl_mock_node.py) runs isolated buyer and
  seller nodes with separate inboxes and peer registries.
- [`scripts/run_axl_demo.py`](scripts/run_axl_demo.py) demonstrates buyer → seller
  RFQ, seller → buyer quote, buyer → seller lock trigger, and seller → buyer
  delivery payload.

This proves the agent protocol boundary and message flow, but it is not a final
claim that the demo is running against a production Gensyn AXL deployment.

According to Gensyn's AXL overview, AXL is a standalone P2P node that exposes a
local HTTP API for messaging, topology discovery, MCP, and A2A support. Our
client intentionally follows that boundary so the mock can be replaced with a
real AXL node later without changing RFQ/quote/delivery payloads.

## Why The Mock Exists

The buyer/seller protocol only needs a few AXL-style primitives:

- discover known peers,
- send a signed JSON payload to a peer,
- receive queued messages,
- keep buyer and seller nodes isolated.

The local mock lets judges run the flow without a Gensyn node install, while the
client code keeps the transport boundary explicit.

## What To Show If Claiming Gensyn

Run:

```bash
PYTHONPATH=. python scripts/run_axl_demo.py
```

Show that the demo uses two separate node endpoints:

- buyer node: `http://localhost:19001`
- seller node: `http://localhost:19002`

Show the console sequence:

1. buyer sends RFQ,
2. seller receives RFQ,
3. seller returns signed quote,
4. buyer sends locked trigger,
5. seller returns delivery payload,
6. buyer verifies result hash.

## Remaining Risk

If the project submits for a Gensyn prize, the strongest version would replace
`scripts/axl_mock_node.py` with a real Gensyn AXL node/binary while keeping
`AxlClient` and the buyer/seller payload schema unchanged.
