# KeeperHub Workflows

Three workflows drive every settlement path. They are defined once on the KeeperHub side (via the dashboard or `ai_generate_workflow` MCP tool) and then referenced by id from `.env`.

---

## 1. `lock` — Buyer locks funds on escrow

**Trigger:** Webhook, fired by the buyer agent after it has selected a winning quote.

**Inputs:**
```json
{
  "rfqId":              "bytes32",
  "seller":             "address",
  "amount":             "uint256 (string-encoded)",
  "token":              "address",
  "deliveryWindowSecs": "uint64",
  "disputeWindowSecs":  "uint64"
}
```

**Action:** `web3/write-contract`
- `contractAddress`: `${ESCROW_ADDRESS}`
- `functionName`: `lockFunds`
- `args`: `[rfqId, seller, amount, token, deliveryWindowSecs, disputeWindowSecs]`
- `walletId`: `${KEEPERHUB_BUYER_WALLET_ID}`
- Retry policy: 3 attempts, exponential backoff, bump gas tip 20% each retry.

**Why KeeperHub and not a plain eth_sendTransaction?** Buyers are untrusted to stay online — if the webhook fires but gas spikes, KeeperHub keeps trying. The lock workflow also produces an audit-trail entry per attempt, which is what judges will check when they look at the reliability story.

---

## 2. `optimistic-release` — Seller gets paid after buyer's dispute window

**Trigger:** Schedule, every 30 seconds.

**Condition (evaluated inside KeeperHub):**
```
deal.state == "DELIVERED" AND block.timestamp > deal.disputeDeadline
```

**Action:** `web3/write-contract`
- `functionName`: `optimisticRelease`
- `args`: `[rfqId]`

The workflow enumerates open `DELIVERED` deals from an indexed events view (KeeperHub's built-in log scanner) and fires one tx per ready deal. If the buyer calls `releaseFunds` manually first, the next keeper tick reverts cheaply (state != DELIVERED) and the workflow moves on.

---

## 3. `timeout-refund` — Buyer gets refunded when seller doesn't deliver

**Trigger:** Schedule, every 60 seconds.

**Condition:**
```
deal.state == "LOCKED" AND block.timestamp > deal.deliveryDeadline
```

**Action:** `web3/write-contract`
- `functionName`: `claimRefund`
- `args`: `[rfqId]`

Even though `claimRefund` doesn't require the buyer's signature, wiring it through KeeperHub means the buyer agent can go offline after locking funds and still get its USDC back — the refund becomes a property of the protocol, not a thing the agent has to remember.

---

## Idempotency

Every `trigger_workflow` call from `KeeperHubClient` attaches an `Idempotency-Key` header derived from the rfq_id. This prevents double-locks when a webhook is retried at the HTTP layer, and double-releases when the keeper and a manual release race.
