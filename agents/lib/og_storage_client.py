"""0G Storage client — agent persistent memory (Layer 4).

Every agent maintains three data classes on 0G Storage:

  capabilities        — KV entry:  `{agent_id}:capabilities`
                        structured capability manifest for RFQ matching.

  history             — append-only log: `{agent_id}:history`
                        one record per completed deal (rfq_id, amount,
                        delivery_ms, outcome, tx_hash). Forms the
                        tamper-evident work record the ERC-8004 reputation
                        registry can index.

  reputation cache    — KV entry:  `{agent_id}:reputation`
                        rolled-up score synced from ERC-8004; avoids
                        round-tripping chain for every RFQ.

The underlying 0G Storage SDK is a node CLI; we invoke it via HTTP against
the indexer + KV gateway instead of shelling out. `og_storage://` references
inside our schemas are of the form `0g://<root_hash>` or
`0g://kv/<namespace>/<key>`.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import httpx

log = logging.getLogger(__name__)


@dataclass
class Capabilities:
    agent_id: str
    capabilities: list[str]
    supported_task_types: list[str]
    max_budget_acceptance: int
    avg_delivery_ms: int
    preferred_token: str = "USDC"
    version: str = "1.0"


@dataclass
class HistoryRecord:
    timestamp: int
    rfq_id: str
    counterparty_agent_id: str
    task_type: str
    amount_usdc: int
    delivery_ms: int
    result_hash: str
    outcome: Literal["SUCCESS", "DISPUTE", "TIMEOUT"]
    tx_hash: str


@dataclass
class ReputationSnapshot:
    agent_id: str
    total_tasks: int
    success_rate: float
    avg_rating: float
    last_updated: int = field(default_factory=lambda: int(time.time()))
    source: str = "erc8004_reputation_registry"


class OGStorageClient:
    """Thin HTTP wrapper over the 0G Storage indexer + KV gateway."""

    def __init__(
        self,
        indexer_url: str,
        *,
        namespace: str = "agentbazaar",
        timeout_secs: float = 20.0,
    ) -> None:
        self.namespace = namespace
        self._http = httpx.AsyncClient(base_url=indexer_url.rstrip("/"), timeout=timeout_secs)

    # ───── capabilities ────────────────────────────────────────────────

    async def put_capabilities(self, caps: Capabilities) -> str:
        return await self._kv_put(f"{caps.agent_id}:capabilities", asdict(caps))

    async def get_capabilities(self, agent_id: str) -> Capabilities | None:
        raw = await self._kv_get(f"{agent_id}:capabilities")
        if raw is None:
            return None
        return Capabilities(**raw)

    # ───── history (append-only log) ───────────────────────────────────

    async def append_history(self, agent_id: str, record: HistoryRecord) -> str:
        """Append-only semantics: the 0G log returns the new tail root hash,
        which we later cite as the `og_storage_history_ref` on Quote messages.
        """
        resp = await self._http.post(
            "/log/append",
            json={
                "namespace": self.namespace,
                "key": f"{agent_id}:history",
                "record": asdict(record),
            },
        )
        resp.raise_for_status()
        return resp.json()["root_hash"]

    async def list_history(self, agent_id: str, *, limit: int = 50) -> list[HistoryRecord]:
        resp = await self._http.get(
            "/log/list",
            params={
                "namespace": self.namespace,
                "key": f"{agent_id}:history",
                "limit": limit,
            },
        )
        resp.raise_for_status()
        return [HistoryRecord(**r) for r in resp.json().get("records", [])]

    # ───── reputation cache ────────────────────────────────────────────

    async def put_reputation(self, snap: ReputationSnapshot) -> str:
        return await self._kv_put(f"{snap.agent_id}:reputation", asdict(snap))

    async def get_reputation(self, agent_id: str) -> ReputationSnapshot | None:
        raw = await self._kv_get(f"{agent_id}:reputation")
        if raw is None:
            return None
        return ReputationSnapshot(**raw)

    # ───── blob uploads (delivery payload content) ─────────────────────

    async def upload_blob(self, content: bytes) -> str:
        """Upload arbitrary bytes (e.g. the full delivery payload) and return
        the root hash so we can put it on-chain via escrow.confirmDelivery().
        """
        resp = await self._http.post("/blob/upload", content=content)
        resp.raise_for_status()
        return resp.json()["root_hash"]

    async def fetch_blob(self, root_hash: str) -> bytes:
        resp = await self._http.get(f"/blob/{root_hash}")
        resp.raise_for_status()
        return resp.content

    async def aclose(self) -> None:
        await self._http.aclose()

    # ───── internals ───────────────────────────────────────────────────

    async def _kv_put(self, key: str, value: dict[str, Any]) -> str:
        resp = await self._http.put(
            "/kv",
            json={"namespace": self.namespace, "key": key, "value": value},
        )
        resp.raise_for_status()
        return resp.json()["root_hash"]

    async def _kv_get(self, key: str) -> dict[str, Any] | None:
        resp = await self._http.get(
            "/kv", params={"namespace": self.namespace, "key": key}
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        payload = resp.json().get("value")
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None
        return payload if isinstance(payload, dict) else None
