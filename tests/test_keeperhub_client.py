from __future__ import annotations

import pytest
import respx
from httpx import Response

from agents.lib.keeperhub_client import KeeperHubClient


@pytest.mark.asyncio
@respx.mock
async def test_fire_lock_sends_idempotency_key_and_parses_tx():
    route = respx.post("https://kh.test/workflows/wf-lock/runs").mock(
        return_value=Response(
            200,
            json={
                "run_id": "run-1",
                "workflow_id": "wf-lock",
                "status": "pending",
                "tx_hash": None,
            },
        )
    )

    client = KeeperHubClient("https://kh.test", api_key="k")
    run = await client.fire_lock(
        "wf-lock",
        rfq_id="rfq-xyz",
        seller="0x" + "b" * 40,
        amount=500_000,
        token="0x" + "c" * 40,
    )
    await client.aclose()

    assert route.called
    assert route.calls[0].request.headers["Idempotency-Key"] == "rfq-xyz"
    assert run.run_id == "run-1"
    assert run.status == "pending"


@pytest.mark.asyncio
@respx.mock
async def test_wait_for_tx_returns_on_tx_hash():
    respx.get("https://kh.test/runs/run-1").mock(
        side_effect=[
            Response(200, json={"id": "run-1", "status": "running", "tx_hash": None}),
            Response(200, json={"id": "run-1", "status": "succeeded", "tx_hash": "0xabc"}),
        ]
    )

    client = KeeperHubClient("https://kh.test", api_key="k")
    run = await client.wait_for_tx("run-1", poll_interval_secs=0.01, timeout_secs=5)
    await client.aclose()

    assert run.tx_hash == "0xabc"
    assert run.status == "succeeded"
