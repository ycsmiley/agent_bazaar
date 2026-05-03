"""KeeperHub MCP client.

Three workflows power Agent Bazaar's settlement guarantees:

  lock      — buyer → escrow.lockFunds()         (webhook-triggered)
  release   — escrow.optimisticRelease()         (scheduled, every 30s)
  refund    — escrow.claimRefund()               (scheduled, delivery timeout)

KeeperHub owns retries, gas pricing, and audit logs, so the agent code just
has to hand off `trigger_workflow(id, args)` and watch the tx hash come back.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowRun:
    run_id: str
    workflow_id: str
    status: str
    tx_hash: str | None
    block_number: int | None
    error: str | None


class KeeperHubClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        *,
        timeout_secs: float = 30.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self.endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_secs,
        )

    async def trigger_workflow(
        self,
        workflow_id_or_webhook_url: str,
        args: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> WorkflowRun:
        """Kick off a workflow run. `idempotency_key` should be the rfq_id so a
        re-fired webhook can't double-lock or double-release.
        """
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        if workflow_id_or_webhook_url.startswith(("http://", "https://")):
            resp = await self._http.post(
                workflow_id_or_webhook_url,
                json=args,
                headers=headers,
            )
        else:
            resp = await self._http.post(
                f"/workflows/{workflow_id_or_webhook_url}/runs",
                json={"inputs": args},
                headers=headers,
            )
        resp.raise_for_status()
        return self._parse_run(resp.json())

    async def get_run(self, run_id: str) -> WorkflowRun:
        resp = await self._http.get(f"/runs/{run_id}")
        resp.raise_for_status()
        return self._parse_run(resp.json())

    async def wait_for_tx(
        self,
        run_id: str,
        *,
        poll_interval_secs: float = 2.0,
        timeout_secs: float = 120.0,
    ) -> WorkflowRun:
        """Poll the run until KeeperHub reports a tx hash or a terminal error."""
        import asyncio

        elapsed = 0.0
        while elapsed < timeout_secs:
            run = await self.get_run(run_id)
            if run.tx_hash or run.status in {"failed", "cancelled"}:
                return run
            await asyncio.sleep(poll_interval_secs)
            elapsed += poll_interval_secs
        raise TimeoutError(f"KeeperHub run {run_id} did not produce a tx within {timeout_secs}s")

    # ───── convenience helpers matching the three Agent Bazaar workflows ───

    async def fire_lock(
        self,
        lock_workflow_id: str,
        *,
        rfq_id: str,
        seller: str,
        amount: int,
        token: str,
        delivery_window_secs: int = 600,
        dispute_window_secs: int = 300,
    ) -> WorkflowRun:
        return await self.trigger_workflow(
            lock_workflow_id,
            {
                "rfqId": rfq_id,
                "seller": seller,
                "amount": str(amount),
                "token": token,
                "deliveryWindowSecs": delivery_window_secs,
                "disputeWindowSecs": dispute_window_secs,
            },
            idempotency_key=rfq_id,
        )

    async def fire_optimistic_release(
        self,
        release_workflow_id: str,
        *,
        rfq_id: str,
    ) -> WorkflowRun:
        # The release workflow is normally schedule-triggered, but we expose a
        # manual trigger so the demo can show the tx fire on command.
        return await self.trigger_workflow(
            release_workflow_id,
            {"rfqId": rfq_id},
            idempotency_key=f"{rfq_id}:release",
        )

    async def fire_refund(
        self,
        refund_workflow_id: str,
        *,
        rfq_id: str,
    ) -> WorkflowRun:
        return await self.trigger_workflow(
            refund_workflow_id,
            {"rfqId": rfq_id},
            idempotency_key=f"{rfq_id}:refund",
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    def _parse_run(self, data: dict[str, Any]) -> WorkflowRun:
        return WorkflowRun(
            run_id=data.get("run_id") or data.get("id") or data.get("executionId", ""),
            workflow_id=data.get("workflow_id", ""),
            status=data.get("status", "unknown"),
            tx_hash=data.get("tx_hash") or (data.get("result") or {}).get("txHash"),
            block_number=data.get("block_number"),
            error=data.get("error"),
        )
