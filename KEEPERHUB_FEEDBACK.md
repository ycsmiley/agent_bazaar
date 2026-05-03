# KeeperHub — Integration Feedback

_Submission artefact for the KeeperHub feedback bounty ($250 base) + merge-quality track._

## What we built with it

Agent Bazaar uses KeeperHub to remove the two weakest links in an agent-to-agent trade:

1. **Buyer stays offline after locking funds.** The `optimistic-release` workflow watches every deal that transitioned to `DELIVERED` and fires `escrow.optimisticRelease(rfqId)` once the dispute window closes. The buyer agent can crash, disconnect, or have its AXL node rebooted — the seller still gets paid.
2. **Seller never shows up.** The `timeout-refund` workflow watches every `LOCKED` deal and fires `escrow.claimRefund(rfqId)` once the delivery deadline passes. Buyers get their USDC back without having to remember to come claim it.

Plus the on-ramp workflow `lock`, which the buyer agent fires via webhook after picking the winning quote. Gas-retry + idempotency-key on `rfq_id` means a flaky webhook retry can never double-lock.

See [`keeperhub/workflows.md`](keeperhub/workflows.md) for the full per-workflow spec and [`agents/lib/keeperhub_client.py`](agents/lib/keeperhub_client.py:1) for the client that talks to the MCP endpoint.

## What we actually configured and tested

- `lockFunds(bytes32,address,uint256,address,uint64,uint64)` via KeeperHub webhook.
- `optimisticRelease(bytes32)` via KeeperHub workflow after delivery/dispute window.
- `claimRefund(bytes32)` via KeeperHub workflow after delivery timeout.
- Manual ABI import was required because the deployed Base Sepolia contract was not verified when the workflow was configured.
- Dynamic webhook inputs worked after switching fields to `Webhook.data.rfqId`, `Webhook.data.seller`, `Webhook.data.amount`, `Webhook.data.token`, `Webhook.data.deliveryWindowSecs`, and `Webhook.data.disputeWindowSecs`.
- Live test runs covered `LOCKED`, `RELEASED`, and `REFUNDED` escrow states.

## Issues we hit during integration

- **Manual ABI step.** KeeperHub could not auto-detect functions from Etherscan before verification, so we had to paste ABI manually.
- **Input typing was easy to misread.** Address fields and bytes32 fields look similar in the UI. We initially hit errors when a field was filled as a literal placeholder instead of a dynamic `Webhook.data.*` value.
- **Deadline logic is strict.** Calling release before the dispute window ends correctly reverts with `DeadlineNotPassed`; this is right protocol behavior, but it needs to be obvious in workflow setup.
- **Allowance happens outside KeeperHub.** The KeeperHub wallet must approve the escrow contract for MockUSDC before lock workflows can succeed.

## What worked well

- **Schedule + condition triggers are exactly the right primitive.** We could have written our own cron-in-a-docker, but then every judge reading the repo would worry about how we handle gas spikes, what happens if our container restarts mid-tx, etc. Routing through KeeperHub lets us delete all of that reasoning: the condition language is declarative and the retry policy is visible in the UI.
- **`web3/write-contract` action is the right abstraction.** We literally just declare the contract + function + args and let KeeperHub manage the nonce and gas. That's one less moving part in our own code.
- **Idempotency-Key header is honoured.** We derive it from `rfq_id` and have successfully re-fired the `lock` webhook during development without ever double-locking. This is exactly how agent protocols should be wired into keepers.

## Friction / suggestions

1. **Condition DSL lacks `AND` short-circuit with RPC reads.** Our optimistic-release condition effectively wants:
   ```
   deal.state == DELIVERED AND now > deal.disputeDeadline
   ```
   but both sides of the AND require a `getDeal(rfqId)` call per tick. Today we either do the full read every 30s or we index deals off-chain ourselves. A built-in primitive like `contract.eth_call(...)` memoised for the tick would halve our RPC spend.
2. **Event-triggered workflows would beat the schedule.** Right now the release workflow ticks every 30s. A reactive trigger like "run when event `DeliveryConfirmed(rfqId)` lands, then wait `disputeWindowSecs` seconds, then fire" would cut our median settlement time by ~15s. Today this requires glue outside KeeperHub.
3. **Idempotency-Key TTL.** We'd like to set a custom TTL (currently 24h by default, we think). For our RFQs the sensible window is `deliveryDeadline + disputeDeadline + 1h`; exposing a per-request TTL would let us be more precise.
4. **MCP tool surface.** We drive the API manually through `httpx`. A first-class MCP tool `keeperhub__trigger_workflow(workflow_id, inputs, idempotency_key)` would let our agents call KeeperHub the same way they call any other tool — and let Claude-backed agents discover the workflow catalogue without us having to pass ids around.
5. **Audit-trail export.** The UI view is great; an S3 / IPFS export of the per-run JSON (status, tx hash, gas spent, retries) would make it trivial to attach a full settlement trace to a PR.

## Scorecard

| Dimension              | Rating |
|------------------------|--------|
| Docs quality           | 8/10   |
| Workflow authoring UX  | 9/10   |
| Reliability            | 10/10  |
| Agent-facing ergonomics| 7/10   |

Overall KeeperHub is *the* protocol-grade keeper substrate we didn't want to build ourselves. Three workflows, ~40 LoC of client code, and we get retries + audit + scheduling for free.
