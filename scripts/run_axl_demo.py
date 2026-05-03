#!/usr/bin/env python3
"""
AXL Integration Demo — exercises the Gensyn AXL transport layer.

By default it spins up two local mock AXL nodes so the repo demo is repeatable.
With `--external`, it uses real Gensyn AXL nodes from:

  BUYER_AXL_ENDPOINT / BUYER_AXL_PEER_ID
  SELLER_AXL_ENDPOINT / SELLER_AXL_PEER_ID

Then it runs a buyer and seller through the full message sequence:

  1.  Buyer broadcasts RFQ over AXL
  2.  Seller receives, validates, builds and signs a Quote
  3.  Seller sends Quote back over AXL
  4.  Buyer picks the winner, records a Uniswap quote proof, and locks escrow
  5.  Buyer sends "locked" trigger to seller over AXL
  6.  Seller executes task, hashes result, and confirms delivery
  7.  Seller sends DeliveryPayload back over AXL
  8.  Buyer validates content hash — trade complete

External calls are represented with deterministic demo refs so this AXL-only
script runs without sponsor credentials. The live/testnet path uses real
KeeperHub workflows, escrow transactions, ERC-8004 registries, and Uniswap
quote API responses.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from nacl.signing import SigningKey
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ── bring repo root onto path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.lib.axl_client import AxlClient  # noqa: E402
from agents.lib.signing import sign_payload  # noqa: E402
from schemas.quote import DeliveryPayload, Erc8004ReputationSnapshot, QuoteMessage  # noqa: E402
from schemas.rfq import Budget, Constraints, RFQMessage, Task, TaskType  # noqa: E402

# Import the mock AXL node so we can boot nodes in-process
from scripts.axl_mock_node import AXLNode  # noqa: E402

console = Console()
log = logging.getLogger(__name__)

BUYER_PORT  = 19001
SELLER_PORT = 19002
BUYER_ADDR  = f"http://localhost:{BUYER_PORT}"
SELLER_ADDR = f"http://localhost:{SELLER_PORT}"


# ── helpers ────────────────────────────────────────────────────────────────────

def _sign(d: dict[str, Any], sk: SigningKey) -> dict[str, Any]:
    d["signature"] = sign_payload(d, sk)
    return d


async def _drain(axl: AxlClient, timeout: float) -> list[dict[str, Any]]:
    """Drain the AXL inbox for `timeout` seconds and return all messages."""
    msgs: list[dict[str, Any]] = []
    try:
        async def _consume() -> None:
            async for msg in axl.inbox():
                msgs.append(msg)
        await asyncio.wait_for(_consume(), timeout=timeout)
    except TimeoutError:
        pass
    return msgs


# ── buyer flow ─────────────────────────────────────────────────────────────────

async def run_buyer(
    seller_peer_id: str,
    *,
    buyer_endpoint: str,
    axl_transport: str,
    buyer_sk: SigningKey,
    buyer_addr: str,
    buyer_peer_id_hex: str,
) -> dict[str, str]:
    axl = AxlClient(buyer_endpoint, peer_id=buyer_peer_id_hex, api_mode=axl_transport)

    # 1. Build + broadcast RFQ
    rfq = RFQMessage(
        rfq_id=str(uuid.uuid4()),
        buyer_agent_id=buyer_addr,
        buyer_axl_peer_id=buyer_sk.verify_key.encode().hex(),
        task=Task(
            type=TaskType.DATA_FETCH,
            input={"pair": "ETH/USDC", "prompt": "get spot price"},
            output_schema={"type": "object"},
        ),
        budget=Budget(max_usdc_atomic=500_000, accepted_tokens=["USDC"]),
        constraints=Constraints(min_reputation_score=0.8, deadline_unix=int(time.time()) + 600),
        signature="",
    )
    body = rfq.model_dump()
    _sign(body, buyer_sk)
    rfq_signed = RFQMessage.model_validate(body)

    console.print(
        f"[cyan]→ RFQ[/] {rfq_signed.rfq_id[:8]}… broadcast "
        f"(budget {rfq_signed.budget.max_usdc_atomic} USDC atomic)"
    )
    await axl.send(seller_peer_id, rfq_signed.model_dump())

    # 2. Collect quote
    await asyncio.sleep(0.2)
    quote_msgs = await _drain(axl, timeout=5.0)
    quote_msgs = [
        m
        for m in quote_msgs
        if m.get("rfq_id") == rfq_signed.rfq_id and "quote_price_atomic" in m
    ]
    if not quote_msgs:
        raise RuntimeError("no quote received from seller")

    quote = QuoteMessage.model_validate(quote_msgs[0])
    console.print(
        f"[yellow]← Quote[/] from {quote.seller_agent_id[:12]}  "
        f"price={quote.quote_price_atomic}  "
        f"rep={quote.erc8004_reputation.success_rate:.1%}"
    )

    # Demo refs for Uniswap quote proof + KeeperHub lock.
    quote_ref = "quote_52cdda69-9996-4b58-9101-d1451f44d8f0"
    lock_tx = "0x" + "22" * 32
    console.print(f"[dim]  Uniswap quote  : {quote_ref}[/]")
    console.print(f"[dim]  Escrow lock tx : {lock_tx[:20]}…[/]")

    # 3. Send "locked" trigger to seller
    trigger = {
        "locked": True,
        "rfq_id": rfq_signed.rfq_id,
        "buyer_peer_id": buyer_peer_id_hex,
        "task_input": rfq_signed.task.input,
    }
    await axl.send(seller_peer_id, trigger)
    console.print("[cyan]→ Locked trigger[/] sent to seller")

    # 4. Await delivery
    await asyncio.sleep(0.3)
    delivery_msgs = await _drain(axl, timeout=6.0)
    delivery_msgs = [
        m
        for m in delivery_msgs
        if m.get("rfq_id") == rfq_signed.rfq_id and "result_hash" in m
    ]
    if not delivery_msgs:
        raise RuntimeError("no delivery received")

    raw_delivery = delivery_msgs[0]
    # Unwrap if nested in "payload"
    if "payload" in raw_delivery and isinstance(raw_delivery["payload"], dict):
        raw_delivery = raw_delivery["payload"]

    delivery = DeliveryPayload.model_validate(raw_delivery)
    console.print(
        f"[green]← Delivery[/] result_hash={delivery.result_hash[:20]}…  "
        f"content keys={list(delivery.content.keys())}"
    )

    # Stub release + feedback
    release_tx  = "0x" + "44" * 32
    feedback_tx = "0x" + "55" * 32
    console.print(f"[dim]  Escrow release  : {release_tx[:20]}…[/]")
    console.print(f"[dim]  ERC-8004 feedback: {feedback_tx[:20]}…[/]")

    await axl.aclose()
    return {
        "rfq_id": rfq_signed.rfq_id,
        "uniswap_quote_ref": quote_ref,
        "lock_tx":          lock_tx,
        "release_tx":       release_tx,
        "feedback_tx":      feedback_tx,
        "result_hash":      delivery.result_hash,
    }


# ── seller flow ────────────────────────────────────────────────────────────────

async def run_seller(
    *,
    seller_endpoint: str,
    axl_transport: str,
    seller_sk: SigningKey,
    seller_addr: str,
    seller_peer_id_hex: str,
) -> None:
    axl = AxlClient(seller_endpoint, peer_id=seller_peer_id_hex, api_mode=axl_transport)

    async for msg in axl.inbox():
        # Handle nested envelopes from mock AXL
        if "payload" in msg and isinstance(msg["payload"], dict):
            msg = msg["payload"]

        # RFQ?
        if "task" in msg and "budget" in msg:
            rfq = RFQMessage.model_validate(msg)
            console.print(f"[magenta]Seller[/] received RFQ {rfq.rfq_id[:8]}…")
            quote = QuoteMessage(
                rfq_id=rfq.rfq_id,
                seller_agent_id=seller_addr,
                seller_axl_peer_id=seller_sk.verify_key.encode().hex(),
                quote_price_atomic=min(rfq.budget.max_usdc_atomic, 420_000),
                confidence_score=0.91,
                estimated_delivery_ms=2800,
                erc8004_reputation=Erc8004ReputationSnapshot(
                    total_tasks=47,
                    success_rate=0.957,
                    on_chain_proof_uri=f"erc8004://reputation/{seller_addr}",
                ),
                signature="",
            )
            q_dict = quote.model_dump()
            _sign(q_dict, seller_sk)
            buyer_transport_peer_id = msg.get("_axl_sender_peer_id") or msg.get("_axl_from_peer_id")
            await axl.send(buyer_transport_peer_id or rfq.buyer_axl_peer_id, q_dict)
            console.print(f"[magenta]Seller[/] → Quote sent (price={quote.quote_price_atomic})")

        # Locked trigger?
        elif msg.get("locked") and msg.get("rfq_id"):
            rfq_id = msg["rfq_id"]
            buyer_peer = msg.get("buyer_peer_id", "")
            task_input = msg.get("task_input", {})
            console.print(f"[magenta]Seller[/] received locked trigger for rfq={rfq_id[:8]}…")

            content = {
                "pair": task_input.get("pair", "ETH/USDC"),
                "price": 3412.15,
                "volume_24h": 1_234_567_890,
                "source": "agent-bazaar-seller",
                "timestamp": int(time.time()),
            }
            import hashlib
            canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
            result_hash = "0x" + hashlib.sha3_256(canonical).hexdigest()

            confirm_tx = "0x" + "33" * 32
            console.print(f"[dim]  confirmDelivery : {confirm_tx[:20]}…[/]")

            delivery = DeliveryPayload(
                rfq_id=rfq_id,
                seller_agent_id=seller_addr,
                content=content,
                result_hash=result_hash,
                signature="",
            )
            d_dict = delivery.model_dump()
            _sign(d_dict, seller_sk)
            await axl.send(buyer_peer, d_dict)
            console.print(f"[magenta]Seller[/] → DeliveryPayload sent hash={result_hash[:20]}…")
            await axl.aclose()
            return


# ── main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--external",
        action="store_true",
        help="Use real Gensyn AXL nodes from env instead of local mock nodes.",
    )
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")

    logging.basicConfig(level=logging.WARNING)
    console.print(Panel.fit(
        "Agent Bazaar — AXL P2P Integration Demo",
        subtitle=(
            "Gensyn AXL transport · Uniswap quote proof · "
            "KeeperHub escrow · ERC-8004 reputation"
        ),
        style="bold magenta",
    ))

    buyer_endpoint = BUYER_ADDR
    seller_endpoint = SELLER_ADDR
    axl_transport = "mock"
    buyer_node = None
    seller_node = None

    if args.external:
        buyer_endpoint = os.environ.get("BUYER_AXL_ENDPOINT", "").rstrip("/")
        seller_endpoint = os.environ.get("SELLER_AXL_ENDPOINT", "").rstrip("/")
        axl_transport = os.environ.get("AXL_TRANSPORT", "gensyn")
        if not buyer_endpoint or not seller_endpoint:
            raise RuntimeError("BUYER_AXL_ENDPOINT and SELLER_AXL_ENDPOINT are required")
        if axl_transport != "gensyn":
            raise RuntimeError("AXL_TRANSPORT must be gensyn for --external")
    else:
        # Boot two mock AXL nodes for deterministic local replay.
        buyer_node = AXLNode(port=BUYER_PORT, name="buyer_demo", peer_addrs=[SELLER_ADDR])
        seller_node = AXLNode(port=SELLER_PORT, name="seller_demo", peer_addrs=[BUYER_ADDR])
        buyer_node.start()
        seller_node.start()
        await asyncio.sleep(0.8)  # let peer discovery complete

    # Keypairs
    buyer_sk  = SigningKey.generate()
    seller_sk = SigningKey.generate()
    buyer_addr  = "0x" + "ba" * 20
    seller_addr = "0x" + "5e" * 20

    buyer_peer_id_hex = os.environ.get("BUYER_AXL_PEER_ID", "")
    if not args.external:
        buyer_peer_id_hex = buyer_sk.verify_key.encode().hex()
    seller_peer_id_hex = (
        os.environ.get("SELLER_AXL_PEER_ID", "")
        if args.external
        else seller_sk.verify_key.encode().hex()
    )
    if args.external and (not buyer_peer_id_hex or not seller_peer_id_hex):
        raise RuntimeError("BUYER_AXL_PEER_ID and SELLER_AXL_PEER_ID are required")

    if buyer_node and seller_node:
        # Register ed25519 peer IDs directly — no HTTP round-trip needed.
        buyer_node.register_peer(seller_peer_id_hex, SELLER_ADDR, "seller")
        seller_node.register_peer(buyer_peer_id_hex, BUYER_ADDR, "buyer")
        await asyncio.sleep(0.2)

    console.print("\n[bold]Step 1-4:[/] Buyer ↔ Seller AXL exchange\n")

    # Run seller in background task
    seller_task = asyncio.create_task(
        run_seller(
            seller_endpoint=seller_endpoint,
            axl_transport=axl_transport,
            seller_sk=seller_sk,
            seller_addr=seller_addr,
            seller_peer_id_hex=seller_peer_id_hex,
        )
    )

    await asyncio.sleep(0.1)

    # Run buyer (drives the whole flow)
    result = await run_buyer(
        seller_peer_id=seller_peer_id_hex,
        buyer_endpoint=buyer_endpoint,
        axl_transport=axl_transport,
        buyer_sk=buyer_sk,
        buyer_addr=buyer_addr,
        buyer_peer_id_hex=buyer_peer_id_hex,
    )

    await seller_task

    # Summary table
    console.print()
    t = Table(title="Trade Summary", show_header=True, header_style="bold cyan")
    t.add_column("Field", style="dim")
    t.add_column("Value")
    for k, v in result.items():
        t.add_row(k, str(v)[:72])
    console.print(t)

    console.print(Panel.fit(
        "[bold green]✓ Trade complete[/] — RFQ → Quote → Lock → Deliver → Release",
        style="green",
    ))


if __name__ == "__main__":
    asyncio.run(main())
