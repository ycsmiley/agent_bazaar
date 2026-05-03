"""Serve a small local Agent Bazaar demo service."""

from __future__ import annotations

import asyncio
import json
import os
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv
from nacl.signing import SigningKey

from agents.lib.market_data_task import SellerExecutionError, content_hash, fetch_market_data
from scripts.generate_market_trace import build_market_trace
from scripts.run_axl_demo import run_buyer, run_seller

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo"
load_dotenv(ROOT / ".env")


SELLER_LISTINGS: list[dict[str, object]] = [
    {
        "id": "seller-efficient-price",
        "label": "Efficient Price Agent",
        "agent_id": "0xB222222222222222222222222222222222222222",
        "capabilities": ["market_data", "api_call"],
        "quota_available": 18,
        "min_price_atomic": 300_000,
        "confidence": 0.85,
        "success_rate": 0.88,
        "total_tasks": 18,
        "estimated_delivery_ms": 4100,
        "status": "online",
    },
    {
        "id": "seller-fast-data",
        "label": "Fast Data Agent",
        "agent_id": "0xA111111111111111111111111111111111111111",
        "capabilities": ["market_data", "data_fetch"],
        "quota_available": 9,
        "min_price_atomic": 420_000,
        "confidence": 0.91,
        "success_rate": 0.957,
        "total_tasks": 47,
        "estimated_delivery_ms": 2800,
        "status": "online",
    },
    {
        "id": "seller-research-agent",
        "label": "Research Summarizer",
        "agent_id": "0xC333333333333333333333333333333333333333",
        "capabilities": ["llm_inference", "research"],
        "quota_available": 6,
        "min_price_atomic": 260_000,
        "confidence": 0.74,
        "success_rate": 0.71,
        "total_tasks": 9,
        "estimated_delivery_ms": 2300,
        "status": "online",
    },
]


class AgentBazaarHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(DEMO_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/market":
            trace = build_market_trace()
            _apply_seller_listings(trace)
            self._json(trace)
            return
        if self.path == "/api/listings":
            self._json({"sellers": SELLER_LISTINGS})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            body = {}

        if self.path == "/api/listings":
            listing = _listing_from_body(body)
            SELLER_LISTINGS.insert(0, listing)
            trace = build_market_trace(now=int(time.time()))
            _apply_seller_listings(trace)
            self._json(trace, status=201)
            return

        if self.path != "/api/rfqs":
            self.send_error(404)
            return

        trace = build_market_trace(now=int(time.time()))
        prompt = str(body.get("prompt") or trace["rfq"]["prompt"])
        pair = str(body.get("pair") or trace["rfq"]["pair"])
        budget_atomic = int(body.get("budget_atomic") or trace["rfq"]["budget_atomic"])

        trace["rfq"]["prompt"] = prompt
        trace["rfq"]["pair"] = pair
        trace["rfq"]["budget_atomic"] = budget_atomic
        trace["timeline"][0]["detail"] = "Research Buyer broadcasts the task to seller agents."
        _apply_seller_listings(trace)

        if os.getenv("AGENT_BAZAAR_AXL_UI") == "1":
            try:
                result = asyncio.run(
                    _run_axl_trade_from_ui(
                        task_input={"pair": pair, "prompt": prompt},
                        budget_atomic=budget_atomic,
                    )
                )
                trace["rfq"]["id"] = result["rfq_id"]
                trace["delivery"]["content"] = result["content"]
                trace["delivery"]["result_hash"] = result["result_hash"]
                trace["delivery"]["verified"] = True
                trace["delivery"]["verification"] = (
                    "real seller execution completed over AXL and hash matched"
                )
                trace["proofs"]["uniswap_quote_ref"] = result["uniswap_quote_ref"]
                trace["proofs"]["escrow_lock"] = result["lock_tx"]
                trace["proofs"]["escrow_release"] = result["release_tx"]
                trace["proofs"]["erc8004_feedback"] = result["feedback_tx"]
                trace["source"]["connected_to"].append("live AXL trade")
            except Exception as exc:  # noqa: BLE001
                _mark_execution_failed(trace, pair=pair, error=str(exc))
        else:
            try:
                content = asyncio.run(fetch_market_data({"pair": pair, "prompt": prompt}))
                trace["delivery"]["content"] = content
                trace["delivery"]["result_hash"] = content_hash(content)
                trace["delivery"]["verified"] = True
                trace["delivery"]["verification"] = (
                    "real seller execution completed via Coinbase Exchange public API"
                )
                trace["source"]["connected_to"].append("real seller market-data execution")
            except SellerExecutionError as exc:
                _mark_execution_failed(trace, pair=pair, error=str(exc))
        _consume_selected_seller_capacity(trace)

        self._json(trace, status=201)
        return

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


def _listing_from_body(body: dict[str, object]) -> dict[str, object]:
    now = int(time.time())
    label = str(body.get("label") or "Seller Agent").strip()[:40] or "Seller Agent"
    capabilities = [
        item.strip().lower().replace(" ", "_")
        for item in str(body.get("capabilities") or "market_data,api_call").split(",")
        if item.strip()
    ]
    quota = max(1, int(body.get("quota_available") or 10))
    price_atomic = max(1, int(body.get("min_price_atomic") or 300_000))
    success_rate = min(1.0, max(0.0, float(body.get("success_rate") or 0.9)))
    confidence = min(1.0, max(0.0, float(body.get("confidence") or 0.88)))
    agent_id = str(body.get("agent_id") or "")
    if not (agent_id.startswith("0x") and len(agent_id) == 42):
        agent_suffix = hex(now)[2:].rjust(40, "0")[-40:]
        agent_id = f"0x{agent_suffix}"
    return {
        "id": f"seller-{now}",
        "label": label,
        "agent_id": agent_id,
        "agent_public_key": str(body.get("agent_public_key") or ""),
        "capabilities": capabilities,
        "quota_available": quota,
        "min_price_atomic": price_atomic,
        "confidence": confidence,
        "success_rate": success_rate,
        "total_tasks": int(body.get("total_tasks") or 0),
        "estimated_delivery_ms": int(body.get("estimated_delivery_ms") or 3200),
        "status": "online",
    }


def _apply_seller_listings(trace: dict[str, object]) -> None:
    rfq = trace.get("rfq", {})
    if not isinstance(rfq, dict):
        return
    budget = int(rfq.get("budget_atomic") or 500_000)
    min_reputation = float(rfq.get("min_reputation") or 0.8)
    task_type = str(rfq.get("task_type") or "data_fetch")
    required_capability = "market_data" if task_type == "data_fetch" else task_type

    quotes: list[dict[str, object]] = []
    best_index: int | None = None
    best_score = float("-inf")

    for listing in SELLER_LISTINGS:
        price = int(listing["min_price_atomic"])
        confidence = float(listing["confidence"])
        success_rate = float(listing["success_rate"])
        quota = int(listing["quota_available"])
        capabilities = list(listing["capabilities"])
        eligible = (
            quota > 0
            and price <= budget
            and success_rate >= min_reputation
            and required_capability in capabilities
        )
        score = confidence * success_rate / price if eligible else None
        reason = "eligible"
        if quota <= 0:
            reason = "rejected: no quota available"
        elif required_capability not in capabilities:
            reason = f"rejected: missing {required_capability} capability"
        elif price > budget:
            reason = "rejected: price exceeds buyer budget"
        elif success_rate < min_reputation:
            reason = f"rejected: reputation {success_rate:.3f} < min {min_reputation:.3f}"
        quote = {
            "seller": listing["agent_id"],
            "seller_label": listing["label"],
            "listing_id": listing["id"],
            "capabilities": capabilities,
            "quota_available": quota,
            "price_atomic": price,
            "confidence": confidence,
            "success_rate": success_rate,
            "total_tasks": listing["total_tasks"],
            "estimated_delivery_ms": listing["estimated_delivery_ms"],
            "score": score,
            "status": "eligible" if eligible else "rejected",
            "reason": reason,
            "selected": False,
        }
        if score is not None and score > best_score:
            best_score = score
            best_index = len(quotes)
        quotes.append(quote)

    if best_index is not None:
        quotes[best_index]["selected"] = True

    trace["sellers"] = SELLER_LISTINGS
    trace["quotes"] = sorted(
        quotes,
        key=lambda quote: quote["score"] if quote["score"] is not None else -1,
        reverse=True,
    )
    winner = next((quote for quote in trace["quotes"] if quote["selected"]), None)
    trace["matching"] = {
        "formula": "confidence * reputation / price",
        "winner": winner["seller"] if winner else "",
        "winner_reason": "best eligible listed capacity" if winner else "no eligible seller",
    }


def _consume_selected_seller_capacity(trace: dict[str, object]) -> None:
    selected = next((quote for quote in trace.get("quotes", []) if quote.get("selected")), None)
    if not selected:
        return
    listing_id = selected.get("listing_id")
    for listing in SELLER_LISTINGS:
        if listing["id"] == listing_id:
            listing["quota_available"] = max(0, int(listing["quota_available"]) - 1)
            selected["quota_available"] = listing["quota_available"]
            return


def _mark_execution_failed(trace: dict[str, object], *, pair: str, error: str) -> None:
    trace["delivery"] = {
        "content": {
            "pair": pair,
            "error": error,
            "source": "seller_execution_error",
            "timestamp": int(time.time()),
        },
        "result_hash": "",
        "verified": False,
        "verification": "seller execution failed; no payment should release",
    }
    trace["trade_status"] = "seller_failed"
    if isinstance(trace.get("timeline"), list):
        trace["timeline"].append(
            {
                "label": "Seller execution failed",
                "layer": "Seller worker",
                "detail": error,
                "state": "failed",
            }
        )


async def _run_axl_trade_from_ui(
    *,
    task_input: dict[str, str | int | float | bool],
    budget_atomic: int,
) -> dict[str, object]:
    buyer_endpoint = _required_env("BUYER_AXL_ENDPOINT")
    seller_endpoint = _required_env("SELLER_AXL_ENDPOINT")
    buyer_peer_id = _required_env("BUYER_AXL_PEER_ID")
    seller_peer_id = _required_env("SELLER_AXL_PEER_ID")
    axl_transport = os.getenv("AXL_TRANSPORT", "gensyn")

    buyer_sk = SigningKey.generate()
    seller_sk = SigningKey.generate()
    buyer_addr = "0x" + "ba" * 20
    seller_addr = "0x" + "5e" * 20

    seller_task = asyncio.create_task(
        run_seller(
            seller_endpoint=seller_endpoint,
            axl_transport=axl_transport,
            seller_sk=seller_sk,
            seller_addr=seller_addr,
            seller_peer_id_hex=seller_peer_id,
        )
    )
    await asyncio.sleep(0.1)
    try:
        result = await run_buyer(
            seller_peer_id=seller_peer_id,
            buyer_endpoint=buyer_endpoint,
            axl_transport=axl_transport,
            buyer_sk=buyer_sk,
            buyer_addr=buyer_addr,
            buyer_peer_id_hex=buyer_peer_id,
            task_input=task_input,
            budget_atomic=budget_atomic,
        )
        await seller_task
        return result
    finally:
        if not seller_task.done():
            seller_task.cancel()


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


if __name__ == "__main__":
    main()
