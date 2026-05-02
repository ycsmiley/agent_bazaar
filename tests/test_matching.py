from __future__ import annotations

import time

from agents.lib.matching import rank_quotes, select_best
from schemas.quote import Erc8004ReputationSnapshot, QuoteMessage
from schemas.rfq import Budget, Constraints, RFQMessage, Task, TaskType


def _rfq(
    *,
    budget: int = 500_000,
    min_rep: float = 0.8,
) -> RFQMessage:
    return RFQMessage(
        rfq_id="rfq-1",
        buyer_agent_id="0x" + "a" * 40,
        buyer_axl_peer_id="p-buyer",
        task=Task(
            type=TaskType.DATA_FETCH,
            input={"pair": "ETH/USDC"},
        ),
        budget=Budget(max_usdc_atomic=budget),
        constraints=Constraints(
            min_reputation_score=min_rep,
            deadline_unix=int(time.time()) + 600,
        ),
        signature="de" * 32,
    )


def _quote(
    *,
    seller_id: str,
    price: int,
    confidence: float,
    success_rate: float,
    delivery_ms: int = 3000,
) -> QuoteMessage:
    return QuoteMessage(
        rfq_id="rfq-1",
        seller_agent_id="0x" + seller_id.ljust(40, "0"),
        seller_axl_peer_id=f"peer-{seller_id}",
        quote_price_atomic=price,
        confidence_score=confidence,
        estimated_delivery_ms=delivery_ms,
        erc8004_reputation=Erc8004ReputationSnapshot(
            total_tasks=50,
            success_rate=success_rate,
            on_chain_proof_uri="https://x",
        ),
        signature="fe" * 32,
    )


def test_best_quote_balances_confidence_reputation_and_price():
    rfq = _rfq()
    cheap_unreliable = _quote(seller_id="1a", price=200_000, confidence=0.5, success_rate=0.82)
    expensive_reliable = _quote(seller_id="2b", price=400_000, confidence=0.95, success_rate=0.97)
    chosen = select_best(rfq, [cheap_unreliable, expensive_reliable])
    # expensive_reliable wins despite 2× price because conf*rep boost beats it
    assert chosen is expensive_reliable


def test_over_budget_quotes_rejected():
    rfq = _rfq(budget=300_000)
    over = _quote(seller_id="aa", price=400_000, confidence=0.99, success_rate=0.99)
    ok = _quote(seller_id="bb", price=280_000, confidence=0.85, success_rate=0.9)
    ranked = rank_quotes(rfq, [over, ok])
    assert ranked[0].quote is ok
    assert "rejected" in ranked[-1].reason


def test_low_reputation_rejected():
    rfq = _rfq(min_rep=0.9)
    bad = _quote(seller_id="aa", price=100_000, confidence=0.99, success_rate=0.8)
    assert select_best(rfq, [bad]) is None
