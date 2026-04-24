from __future__ import annotations

import pytest
import respx
from httpx import Response

from agents.lib.og_storage_client import (
    Capabilities,
    HistoryRecord,
    OGStorageClient,
    ReputationSnapshot,
)


@pytest.mark.asyncio
@respx.mock
async def test_put_and_get_capabilities_roundtrip():
    caps = Capabilities(
        agent_id="0x" + "a" * 40,
        capabilities=["price_query", "data_fetch"],
        supported_task_types=["api_call"],
        max_budget_acceptance=10_000_000,
        avg_delivery_ms=3200,
    )

    put_route = respx.put("https://og.test/kv").mock(
        return_value=Response(200, json={"root_hash": "0xrootA"})
    )
    get_route = respx.get("https://og.test/kv").mock(
        return_value=Response(
            200,
            json={
                "value": {
                    "agent_id": caps.agent_id,
                    "capabilities": caps.capabilities,
                    "supported_task_types": caps.supported_task_types,
                    "max_budget_acceptance": caps.max_budget_acceptance,
                    "avg_delivery_ms": caps.avg_delivery_ms,
                    "preferred_token": "USDC",
                    "version": "1.0",
                }
            },
        )
    )

    client = OGStorageClient("https://og.test")
    assert await client.put_capabilities(caps) == "0xrootA"
    loaded = await client.get_capabilities(caps.agent_id)
    await client.aclose()

    assert put_route.called and get_route.called
    assert loaded == caps


@pytest.mark.asyncio
@respx.mock
async def test_history_append_returns_root_hash():
    record = HistoryRecord(
        timestamp=1_745_000_000,
        rfq_id="rfq-1",
        counterparty_agent_id="0x" + "b" * 40,
        task_type="data_fetch",
        amount_usdc=500_000,
        delivery_ms=2800,
        result_hash="0xbeef",
        outcome="SUCCESS",
        tx_hash="0xtx",
    )
    respx.post("https://og.test/log/append").mock(
        return_value=Response(200, json={"root_hash": "0xhist1"})
    )
    client = OGStorageClient("https://og.test")
    root = await client.append_history("0x" + "a" * 40, record)
    await client.aclose()
    assert root == "0xhist1"


@pytest.mark.asyncio
@respx.mock
async def test_get_reputation_missing_returns_none():
    respx.get("https://og.test/kv").mock(return_value=Response(404, json={}))
    client = OGStorageClient("https://og.test")
    assert await client.get_reputation("0x" + "a" * 40) is None
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_upload_blob():
    respx.post("https://og.test/blob/upload").mock(
        return_value=Response(200, json={"root_hash": "0xblob"})
    )
    client = OGStorageClient("https://og.test")
    h = await client.upload_blob(b'{"content":"payload"}')
    await client.aclose()
    assert h == "0xblob"


def test_reputation_snapshot_dataclass_defaults():
    snap = ReputationSnapshot(
        agent_id="0x" + "a" * 40,
        total_tasks=47,
        success_rate=0.957,
        avg_rating=4.3,
    )
    assert snap.source == "erc8004_reputation_registry"
    assert snap.last_updated > 0
