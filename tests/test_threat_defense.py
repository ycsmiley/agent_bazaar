from __future__ import annotations

import time

import pytest

from agents.lib.threat_defense import (
    MAX_RFQ_BYTES,
    ReplayGuard,
    deal_eligible_for_optimistic_release,
    delivery_hash_matches,
    passes_reputation_gate,
    sanitize_text_field,
    within_rfq_size_limit,
)
from schemas.quote import DeliveryPayload
from schemas.rfq import Budget, Constraints, RFQMessage, Task, TaskType


def test_sanitize_strips_control_characters():
    assert sanitize_text_field("hello\x00world") == "helloworld"
    assert sanitize_text_field("ok\ttab") == "ok\ttab"  # tab preserved


def test_sanitize_length_cap():
    with pytest.raises(ValueError):
        sanitize_text_field("x" * 10_000, max_len=100)


def test_replay_guard_rejects_second_submission():
    g = ReplayGuard()
    assert g.check_and_record("rfq", "peer") is True
    assert g.check_and_record("rfq", "peer") is False
    assert g.check_and_record("rfq", "peer-2") is True


def test_replay_guard_evicts_stale_entries():
    g = ReplayGuard(ttl_secs=0)
    g.check_and_record("rfq", "peer")
    time.sleep(0.01)
    # After eviction, re-recording should succeed.
    assert g.check_and_record("rfq", "peer") is True


def test_optimistic_release_gating():
    now = 1_000_000
    assert deal_eligible_for_optimistic_release(
        state="DELIVERED", dispute_deadline=now - 1, now=now
    )
    assert not deal_eligible_for_optimistic_release(
        state="DELIVERED", dispute_deadline=now + 10, now=now
    )
    assert not deal_eligible_for_optimistic_release(
        state="LOCKED", dispute_deadline=now - 1, now=now
    )


def test_rfq_size_limit():
    assert within_rfq_size_limit(b"x" * 100)
    assert not within_rfq_size_limit(b"x" * (MAX_RFQ_BYTES + 1))


def test_reputation_gate():
    rfq = RFQMessage(
        rfq_id="1",
        buyer_agent_id="0x" + "a" * 40,
        buyer_axl_peer_id="p",
        task=Task(type=TaskType.DATA_FETCH),
        budget=Budget(max_usdc_atomic=1),
        constraints=Constraints(min_reputation_score=0.9, deadline_unix=int(time.time()) + 60),
        signature="x",
    )
    assert passes_reputation_gate(rfq, 0.95)
    assert not passes_reputation_gate(rfq, 0.85)


def test_delivery_hash_comparison_normalises_prefix_and_case():
    payload = DeliveryPayload(
        rfq_id="r",
        seller_agent_id="0x" + "b" * 40,
        content={"a": 1},
        result_hash="0xABCDEF",
        signature="s",
    )
    assert delivery_hash_matches(payload, "abcdef")
    assert not delivery_hash_matches(payload, "abcdee")
