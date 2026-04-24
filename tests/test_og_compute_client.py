from __future__ import annotations

import pytest
import respx
from httpx import Response

from agents.lib.og_compute_client import OGComputeClient, canonical_content_hash


@pytest.mark.asyncio
@respx.mock
async def test_infer_returns_tee_material():
    respx.post("https://og-compute.test/infer").mock(
        return_value=Response(
            200,
            json={
                "response": {"answer": 3412.15, "pair": "ETH/USDC"},
                "tee_signature": "0xsigbytes",
                "provider_address": "0xprovider",
                "model": "deepseek-chat-v3-0324",
            },
        )
    )

    client = OGComputeClient("https://og-compute.test")
    r = await client.infer(messages=[{"role": "user", "content": "eth price"}])
    await client.aclose()

    assert r.tee_signature == "0xsigbytes"
    assert r.provider == "0xprovider"
    assert r.content["pair"] == "ETH/USDC"


@pytest.mark.asyncio
@respx.mock
async def test_verify_maps_status_codes():
    # 200 with valid=True
    respx.post("https://og-compute.test/verify").mock(
        return_value=Response(200, json={"valid": True})
    )
    client = OGComputeClient("https://og-compute.test")
    assert await client.verify(content={"x": 1}, tee_signature="0x", provider="0xp") is True
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_verify_invalid_signature_returns_false():
    respx.post("https://og-compute.test/verify").mock(
        return_value=Response(400, json={"error": "bad_sig"})
    )
    client = OGComputeClient("https://og-compute.test")
    assert await client.verify(content={"x": 1}, tee_signature="0x", provider="0xp") is False
    await client.aclose()


def test_canonical_content_hash_is_stable_across_key_order():
    a = {"a": 1, "b": [1, 2, 3]}
    b = {"b": [1, 2, 3], "a": 1}
    assert canonical_content_hash(a) == canonical_content_hash(b)
    assert canonical_content_hash({"a": 1}) != canonical_content_hash({"a": 2})
