"""Serve a small local Agent Bazaar demo service."""

from __future__ import annotations

import json
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.generate_market_trace import build_market_trace

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo"


class AgentBazaarHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(DEMO_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/market":
            self._json(build_market_trace())
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/rfqs":
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError:
                body = {}

            trace = build_market_trace(now=int(time.time()))
            prompt = str(body.get("prompt") or trace["rfq"]["prompt"])
            pair = str(body.get("pair") or trace["rfq"]["pair"])
            budget_atomic = int(body.get("budget_atomic") or trace["rfq"]["budget_atomic"])

            trace["rfq"]["prompt"] = prompt
            trace["rfq"]["pair"] = pair
            trace["rfq"]["budget_atomic"] = budget_atomic
            trace["delivery"]["content"]["pair"] = pair
            trace["timeline"][0]["detail"] = "Research Buyer broadcasts the task to seller agents."
            self._json(trace, status=201)
            return
        self.send_error(404)

    def _json(self, payload: dict[str, object], *, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 4174), AgentBazaarHandler)
    print("Agent Bazaar demo service: http://127.0.0.1:4174/market-trace.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
