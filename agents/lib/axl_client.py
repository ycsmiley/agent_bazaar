"""AXL transport client.

AXL is Gensyn's encrypted P2P transport. The hackathon-friendly way to drive
it is over the HTTP control API: `GET /topology` returns known peers, and
`POST /send/{peer_id}` pushes an end-to-end-encrypted payload.

This client hides that detail behind three verbs:

    await axl.broadcast(message)        # RFQ → everyone
    await axl.send(peer_id, message)    # Quote / Delivery → one peer
    async for msg in axl.inbox():       # receive everything

For MVP we use `topology + send` instead of GossipSub — functionally the
same for a handful of peers, and avoids having to register a topic handler
inside the AXL node process.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AxlPeer:
    peer_id: str
    multiaddr: str | None = None


class AxlClient:
    def __init__(
        self,
        endpoint: str,
        *,
        peer_id: str,
        timeout_secs: float = 10.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.peer_id = peer_id
        self._http = httpx.AsyncClient(base_url=self.endpoint, timeout=timeout_secs)
        self._inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._poll_task: asyncio.Task[None] | None = None

    async def topology(self) -> list[AxlPeer]:
        """Return every peer the local AXL node knows about (minus self)."""
        resp = await self._http.get("/topology")
        resp.raise_for_status()
        peers: list[AxlPeer] = []
        for raw in resp.json().get("peers", []):
            pid = raw.get("peer_id") or raw.get("id")
            if pid and pid != self.peer_id:
                peers.append(AxlPeer(peer_id=pid, multiaddr=raw.get("multiaddr")))
        return peers

    async def send(self, peer_id: str, message: dict[str, Any]) -> None:
        """Unicast an encrypted payload to a single peer."""
        resp = await self._http.post(
            f"/send/{peer_id}",
            json={"payload": message, "from": self.peer_id},
        )
        resp.raise_for_status()

    async def broadcast(self, message: dict[str, Any]) -> int:
        """Fan out to every peer in /topology. Returns the delivery count."""
        peers = await self.topology()
        sent = 0
        for p in peers:
            try:
                await self.send(p.peer_id, message)
                sent += 1
            except httpx.HTTPError as exc:
                log.warning("broadcast to %s failed: %s", p.peer_id, exc)
        return sent

    async def inbox(self) -> AsyncIterator[dict[str, Any]]:
        """Yield messages addressed to this peer.

        AXL exposes a long-poll `/recv` endpoint; we wrap it in a background
        task so callers can treat the inbox like a queue.
        """
        if self._poll_task is None:
            self._poll_task = asyncio.create_task(self._poll_loop())
        while True:
            yield await self._inbox.get()

    async def _poll_loop(self) -> None:
        backoff = 1.0
        while True:
            try:
                resp = await self._http.get("/recv", params={"peer_id": self.peer_id})
                resp.raise_for_status()
                for raw in resp.json().get("messages", []):
                    payload = raw.get("payload")
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except json.JSONDecodeError:
                            log.warning("dropping non-json payload from %s", raw.get("from"))
                            continue
                    if isinstance(payload, dict):
                        await self._inbox.put(payload)
                backoff = 1.0
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                log.warning("recv failed (%s) — retrying in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15.0)

    async def aclose(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
        await self._http.aclose()
