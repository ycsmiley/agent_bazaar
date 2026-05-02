"""End-to-end demo runner.

Boots an in-process buyer + seller pair against a mock transport so the
whole flow can be traced on stdout without any sponsor API being up.
This is what we screen-record for the submission video; the "real"
script is `scripts/run_demo.sh` which runs the same flow against live
endpoints after `.env` is populated.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from nacl.signing import SigningKey
from rich.console import Console
from rich.panel import Panel

from agents.lib.matching import rank_quotes
from agents.lib.signing import sign_payload
from schemas.quote import Erc8004ReputationSnapshot, QuoteMessage
from schemas.rfq import Budget, Constraints, RFQMessage, Task, TaskType

console = Console()


def _sign(payload: dict[str, Any], sk: SigningKey) -> dict[str, Any]:
    payload["signature"] = sign_payload(payload, sk)
    return payload


def build_rfq(buyer_sk: SigningKey, buyer_addr: str) -> RFQMessage:
    rfq = RFQMessage(
        rfq_id=str(uuid.uuid4()),
        buyer_agent_id=buyer_addr,
        buyer_axl_peer_id=buyer_sk.verify_key.encode().hex(),
        task=Task(
            type=TaskType.DATA_FETCH,
            input={"pair": "ETH/USDC"},
            output_schema={"type": "object"},
        ),
        budget=Budget(max_usdc_atomic=500_000, accepted_tokens=["USDC"]),
        constraints=Constraints(
            min_reputation_score=0.8, deadline_unix=int(time.time()) + 600
        ),
        signature="",
    )
    body = rfq.model_dump()
    return RFQMessage.model_validate(_sign(body, buyer_sk))


def build_quote(
    seller_sk: SigningKey,
    seller_addr: str,
    rfq: RFQMessage,
    *,
    price: int,
    confidence: float,
    success_rate: float,
) -> QuoteMessage:
    quote = QuoteMessage(
        rfq_id=rfq.rfq_id,
        seller_agent_id=seller_addr,
        seller_axl_peer_id=seller_sk.verify_key.encode().hex(),
        quote_price_atomic=price,
        confidence_score=confidence,
        estimated_delivery_ms=2800,
        erc8004_reputation=Erc8004ReputationSnapshot(
            total_tasks=47,
            success_rate=success_rate,
            on_chain_proof_uri=f"erc8004://reputation/{seller_addr}",
        ),
        signature="",
    )
    body = quote.model_dump()
    return QuoteMessage.model_validate(_sign(body, seller_sk))


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)

    buyer_sk = SigningKey.generate()
    seller_a_sk = SigningKey.generate()
    seller_b_sk = SigningKey.generate()

    buyer = "0x" + "b" * 40
    seller_a = "0x" + "a" * 40
    seller_b = "0x" + "c" * 40

    console.print(Panel.fit("AgentBazaar — end-to-end trade", style="bold magenta"))

    # 1. Buyer builds + broadcasts an RFQ.
    rfq = build_rfq(buyer_sk, buyer)
    console.print(f"[cyan]RFQ[/] {rfq.rfq_id[:8]} broadcast by {buyer[:10]} "
                  f"(budget {rfq.budget.max_usdc_atomic})")

    # 2. Two sellers quote.
    quote_a = build_quote(
        seller_a_sk, seller_a, rfq,
        price=420_000, confidence=0.91, success_rate=0.957,
    )
    quote_b = build_quote(
        seller_b_sk, seller_b, rfq,
        price=300_000, confidence=0.85, success_rate=0.88,
    )
    await asyncio.sleep(0.2)
    console.print(f"[yellow]Quote A[/] seller={seller_a[:10]} price={quote_a.quote_price_atomic} "
                  f"rep={quote_a.erc8004_reputation.success_rate:.1%}")
    console.print(f"[yellow]Quote B[/] seller={seller_b[:10]} price={quote_b.quote_price_atomic} "
                  f"rep={quote_b.erc8004_reputation.success_rate:.1%}")

    # 3. Buyer ranks and picks.
    ranked = rank_quotes(rfq, [quote_a, quote_b])
    console.print(Panel.fit(
        "\n".join(
            f"{r.quote.seller_agent_id[:10]}: score={r.score:.2e} — {r.reason}"
            for r in ranked
        ),
        title="Match ranking",
        style="green",
    ))
    winner = ranked[0].quote
    console.print(f"[bold green]Winner[/]: {winner.seller_agent_id[:10]} "
                  f"(reputation-weighted score beats cheaper quote)")

    # 4–8. Fake out the on-chain path with stub TxIDs.
    tx = {
        "uniswap_swap": "0x" + "11" * 32,
        "escrow_lock":  "0x" + "22" * 32,
        "escrow_confirm_delivery": "0x" + "33" * 32,
        "escrow_release": "0x" + "44" * 32,
        "erc8004_feedback": "0x" + "55" * 32,
    }
    for label, h in tx.items():
        console.print(f"[dim]tx[/] {label:<26s} {h}")
        await asyncio.sleep(0.2)

    console.print(Panel.fit(json.dumps(tx, indent=2), title="TxID summary", style="bold blue"))


if __name__ == "__main__":
    asyncio.run(main())
