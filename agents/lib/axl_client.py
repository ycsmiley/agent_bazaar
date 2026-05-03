"""Gensyn AXL transport client.

AXL is Gensyn's encrypted P2P transport. The official node exposes a local
HTTP API:

    GET  /topology                         # local node + known peers
    POST /send + X-Destination-Peer-Id     # raw bytes to one peer
    GET  /recv                             # 204 or one raw inbound body

This client hides that detail behind three verbs:

    await axl.broadcast(message)        # RFQ → everyone
    await axl.send(peer_id, message)    # Quote / Delivery → one peer
    async for msg in axl.inbox():       # receive everything

The local hackathon demo still uses ``scripts/axl_mock_node.py``. Select that
compatibility mode with ``api_mode="mock"``; use ``api_mode="gensyn"`` for the
official Gensyn AXL node API.
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

AxlApiMode = str


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
        api_mode: AxlApiMode = "gensyn",
        timeout_secs: float = 10.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.peer_id = peer_id
        if api_mode not in {"gensyn", "mock"}:
            raise ValueError("api_mode must be 'gensyn' or 'mock'")
        self.api_mode = api_mode
        self._http = httpx.AsyncClient(base_url=self.endpoint, timeout=timeout_secs)
        self._inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._poll_task: asyncio.Task[None] | None = None

    async def topology(self) -> list[AxlPeer]:
        """Return every peer the local AXL node knows about (minus self)."""
        resp = await self._http.get("/topology")
        resp.raise_for_status()
        data = resp.json()
        peers: list[AxlPeer] = []
        for raw in _iter_topology_peers(data):
            pid = _extract_peer_id(raw)
            if pid and pid != self.peer_id:
                peers.append(AxlPeer(peer_id=pid, multiaddr=_extract_multiaddr(raw)))
        return peers

    async def send(self, peer_id: str, message: dict[str, Any]) -> None:
        """Unicast an encrypted payload to a single peer."""
        if self.api_mode == "mock":
            resp = await self._http.post(
                f"/send/{peer_id}",
                json={"payload": message, "from": self.peer_id},
            )
        else:
            outbound = dict(message)
            outbound["_axl_sender_peer_id"] = self.peer_id
            resp = await self._http.post(
                "/send",
                content=json.dumps(outbound, sort_keys=True, separators=(",", ":")).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-Destination-Peer-Id": peer_id,
                },
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
                if self.api_mode == "mock":
                    await self._poll_mock_once()
                else:
                    await self._poll_gensyn_once()
                backoff = 1.0
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                log.warning("recv failed (%s) - retrying in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15.0)

    async def _poll_mock_once(self) -> None:
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

    async def _poll_gensyn_once(self) -> None:
        resp = await self._http.get("/recv")
        if resp.status_code == 204:
            await asyncio.sleep(0.2)
            return
        resp.raise_for_status()
        raw = resp.content
        if not raw:
            await asyncio.sleep(0.2)
            return
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, dict):
            from_peer_id = resp.headers.get("X-From-Peer-Id")
            if from_peer_id:
                payload["_axl_from_peer_id"] = from_peer_id
            await self._inbox.put(payload)

    async def aclose(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
        await self._http.aclose()


def _iter_topology_peers(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_peers = data.get("peers", [])
    if not isinstance(raw_peers, list):
        return []
    return [p for p in raw_peers if isinstance(p, dict)]


def _extract_peer_id(raw: dict[str, Any]) -> str | None:
    for key in ("peer_id", "peerId", "id", "public_key", "publicKey"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_multiaddr(raw: dict[str, Any]) -> str | None:
    for key in ("multiaddr", "addr", "address"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            return value
    return None
