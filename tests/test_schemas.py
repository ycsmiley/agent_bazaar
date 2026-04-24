"""Schema hardening tests — these are the first line of prompt-injection defence."""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from schemas.quote import Erc8004ReputationSnapshot, QuoteMessage
from schemas.rfq import Budget, Constraints, RFQMessage, Task, TaskType


def _valid_rfq() -> RFQMessage:
    return RFQMessage(
        rfq_id="rfq-001",
        buyer_agent_id="0x" + "a" * 40,
        buyer_axl_peer_id="peer-buyer",
        task=Task(
            type=TaskType.DATA_FETCH,
            input={"pair": "ETH/USDC"},
            output_schema={"type": "object"},
        ),
        budget=Budget(max_usdc_atomic=500_000, accepted_tokens=["USDC"]),
        constraints=Constraints(deadline_unix=int(time.time()) + 600),
        signature="de" * 32,
    )


def test_valid_rfq_roundtrip():
    rfq = _valid_rfq()
    assert RFQMessage.model_validate(rfq.model_dump()) == rfq


def test_rfq_rejects_bad_agent_id():
    with pytest.raises(ValidationError):
        RFQMessage(
            rfq_id="x",
            buyer_agent_id="not-an-address",
            buyer_axl_peer_id="p",
            task=Task(type=TaskType.DATA_FETCH),
            budget=Budget(max_usdc_atomic=1),
            constraints=Constraints(deadline_unix=1),
            signature="x",
        )


def test_rfq_rejects_control_chars_in_input():
    with pytest.raises(ValidationError):
        Task(type=TaskType.DATA_FETCH, input={"prompt": "hello\x00world"})


def test_rfq_rejects_zero_budget():
    with pytest.raises(ValidationError):
        Budget(max_usdc_atomic=0)


def test_quote_validates_reputation_bounds():
    with pytest.raises(ValidationError):
        Erc8004ReputationSnapshot(
            total_tasks=5,
            success_rate=1.5,  # > 1.0
            on_chain_proof_uri="https://x",
        )


def test_quote_happy_path():
    q = QuoteMessage(
        rfq_id="rfq-001",
        seller_agent_id="0x" + "b" * 40,
        seller_axl_peer_id="peer-seller",
        quote_price_atomic=420_000,
        confidence_score=0.92,
        estimated_delivery_ms=2800,
        erc8004_reputation=Erc8004ReputationSnapshot(
            total_tasks=47,
            success_rate=0.957,
            on_chain_proof_uri="https://erc8004.example/agent/0xbb",
        ),
        will_use_tee=True,
        signature="ab" * 32,
    )
    assert q.confidence_score == 0.92
