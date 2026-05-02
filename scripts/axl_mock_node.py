#!/usr/bin/env python3
"""
Mock AXL Node — local stand-in for a Gensyn AXL peer.

Implements the three HTTP verbs that AxlClient uses:

    GET  /topology          → peers known to this node
    POST /send/{peer_id}    → forward payload to target peer's HTTP server
    GET  /recv              → drain this node's local inbox

Each node maintains its own state (inbox + peer registry) so multiple
nodes can run in the same process without interference.

Usage (two terminals):
    python scripts/axl_mock_node.py --port 9001 --name buyer  \\
           --peers http://localhost:9002
    python scripts/axl_mock_node.py --port 9002 --name seller \\
           --peers http://localhost:9001
"""
from __future__ import annotations

import argparse
import json
import logging
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen, Request as URLRequest

log = logging.getLogger("axl_node")


def _make_peer_id(name: str) -> str:
    import hashlib
    return hashlib.sha256(name.encode()).hexdigest()


def _http_post(url: str, body: dict[str, Any], timeout: float = 3.0) -> None:
    data = json.dumps(body).encode()
    req = URLRequest(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    urlopen(req, timeout=timeout)


class AXLNode:
    """Isolated AXL node — each instance has its own inbox and peer registry."""

    def __init__(self, *, port: int, name: str, peer_addrs: list[str]) -> None:
        self.port = port
        self.name = name
        self.peer_id = _make_peer_id(name)
        self.addr = f"http://localhost:{port}"
        self.peer_addrs = [a.rstrip("/") for a in peer_addrs]

        # Per-instance state — NOT shared across nodes
        self._inbox: deque[dict[str, Any]] = deque()
        self._peers: dict[str, dict[str, str]] = {}  # peer_id → {addr, name}
        self._lock = threading.Lock()
        self._server: HTTPServer | None = None

        # Build handler class bound to this node instance
        node = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                log.debug(fmt, *args)

            def do_GET(self) -> None:
                path = urlparse(self.path).path
                if path == "/topology":
                    self._topology()
                elif path == "/recv":
                    self._recv()
                elif path == "/health":
                    self._ok({"status": "ok", "peer_id": node.peer_id, "name": node.name})
                else:
                    self._err(404, "not found")

            def do_POST(self) -> None:
                path = urlparse(self.path).path
                if path.startswith("/send/"):
                    self._send(path[len("/send/"):])
                elif path == "/register":
                    self._register()
                elif path == "/_deliver":
                    self._deliver()
                else:
                    self._err(404, "not found")

            # ── GET /topology ─────────────────────────────────────────────────
            def _topology(self) -> None:
                with node._lock:
                    peers = [
                        {"peer_id": pid, "multiaddr": info["addr"], "name": info["name"]}
                        for pid, info in node._peers.items()
                        if pid != node.peer_id
                    ]
                self._ok({"peers": peers, "self": node.peer_id})

            # ── GET /recv ─────────────────────────────────────────────────────
            def _recv(self) -> None:
                with node._lock:
                    msgs = list(node._inbox)
                    node._inbox.clear()
                self._ok({"messages": msgs, "count": len(msgs)})

            # ── POST /_deliver ────────────────────────────────────────────────
            def _deliver(self) -> None:
                body = self._read_json()
                if body is None:
                    return
                with node._lock:
                    node._inbox.append(body)
                log.info("[%s] ← msg from %s  (depth=%d)",
                         node.name, str(body.get("from", "?"))[:16], len(node._inbox))
                self._ok({"delivered": True})

            # ── POST /send/{peer_id} ──────────────────────────────────────────
            def _send(self, target_peer_id: str) -> None:
                body = self._read_json()
                if body is None:
                    return
                envelope = {
                    "from": body.get("from", node.peer_id),
                    "to": target_peer_id,
                    "payload": body.get("payload", body),
                    "ts": int(time.time() * 1000),
                    "msg_id": str(uuid.uuid4()),
                }
                with node._lock:
                    peer_info = node._peers.get(target_peer_id)
                if peer_info is None:
                    log.warning("[%s] unknown peer %s", node.name, target_peer_id[:16])
                    self._err(404, f"unknown peer {target_peer_id}")
                    return
                target_url = f"{peer_info['addr']}/_deliver"
                try:
                    _http_post(target_url, envelope)
                    log.info("[%s] → %s", node.name, peer_info["name"])
                    self._ok({"queued": True, "msg_id": envelope["msg_id"]})
                except Exception as exc:
                    log.warning("[%s] send to %s failed: %s", node.name, peer_info["name"], exc)
                    self._err(502, str(exc))

            # ── POST /register ────────────────────────────────────────────────
            def _register(self) -> None:
                body = self._read_json()
                if body is None:
                    return
                pid  = body.get("peer_id")
                addr = body.get("addr", "").rstrip("/")
                name = body.get("name", "unknown")
                if not pid or not addr:
                    self._err(400, "peer_id and addr required")
                    return
                with node._lock:
                    already = pid in node._peers
                    node._peers[pid] = {"addr": addr, "name": name}
                log.info("[%s] registered peer '%s' @ %s", node.name, name, addr)
                self._ok({"registered": True})
                # Announce back once for mutual discovery
                if not already:
                    threading.Thread(
                        target=node._announce_once, args=(addr,), daemon=True
                    ).start()

            # ── helpers ───────────────────────────────────────────────────────
            def _read_json(self) -> dict[str, Any] | None:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    self._err(400, f"bad JSON: {exc}")
                    return None

            def _ok(self, body: dict[str, Any]) -> None:
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _err(self, code: int, msg: str) -> None:
                data = json.dumps({"error": msg}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._handler_cls = Handler

    # ── public API ─────────────────────────────────────────────────────────────

    def register_peer(self, peer_id: str, addr: str, name: str = "peer") -> None:
        """Register a peer directly (no HTTP round-trip needed)."""
        with self._lock:
            self._peers[peer_id] = {"addr": addr.rstrip("/"), "name": name}

    def start(self) -> None:
        self._server = HTTPServer(("0.0.0.0", self.port), self._handler_cls)
        log.info("AXL node '%s' :%d  peer_id=%s…", self.name, self.port, self.peer_id[:16])
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        threading.Thread(target=self._announce_all_with_retry, daemon=True).start()

    def _announce_once(self, target_addr: str) -> None:
        payload = {"peer_id": self.peer_id, "addr": self.addr, "name": self.name}
        try:
            _http_post(f"{target_addr}/register", payload)
        except Exception as exc:
            log.debug("[%s] announce to %s failed: %s", self.name, target_addr, exc)

    def _announce_all_with_retry(self) -> None:
        remaining = list(self.peer_addrs)
        for _ in range(15):
            still_pending = []
            for addr in remaining:
                try:
                    _http_post(f"{addr}/register",
                               {"peer_id": self.peer_id, "addr": self.addr, "name": self.name})
                    log.info("[%s] announced to %s", self.name, addr)
                except Exception:
                    still_pending.append(addr)
            remaining = still_pending
            if not remaining:
                break
            time.sleep(0.5)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


def main() -> None:
    ap = argparse.ArgumentParser(description="Mock AXL P2P node")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--peers", nargs="*", default=[])
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    node = AXLNode(port=args.port, name=args.name, peer_addrs=args.peers)
    node.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("shutting down")
        node.stop()


if __name__ == "__main__":
    main()
