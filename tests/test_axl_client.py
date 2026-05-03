from __future__ import annotations

import httpx
import pytest
import respx

from agents.lib.axl_client import AxlClient


@pytest.mark.asyncio
@respx.mock
async def test_gensyn_send_uses_official_send_endpoint() -> None:
    route = respx.post("http://axl.local/send").mock(return_value=httpx.Response(200))
    client = AxlClient("http://axl.local", peer_id="buyer", api_mode="gensyn")

    await client.send("seller-peer", {"rfq_id": "rfq-1"})

    request = route.calls.last.request
    assert request.headers["X-Destination-Peer-Id"] == "seller-peer"
    assert request.content == b'{"_axl_sender_peer_id":"buyer","rfq_id":"rfq-1"}'
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_gensyn_recv_reads_raw_body_and_sender_header() -> None:
    respx.get("http://axl.local/recv").mock(
        return_value=httpx.Response(
            200,
            content=b'{"rfq_id":"rfq-1"}',
            headers={"X-From-Peer-Id": "seller-peer"},
        )
    )
    client = AxlClient("http://axl.local", peer_id="buyer", api_mode="gensyn")

    await client._poll_gensyn_once()
    message = await client._inbox.get()

    assert message == {"rfq_id": "rfq-1", "_axl_from_peer_id": "seller-peer"}
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_gensyn_recv_204_is_empty() -> None:
    respx.get("http://axl.local/recv").mock(return_value=httpx.Response(204))
    client = AxlClient("http://axl.local", peer_id="buyer", api_mode="gensyn")

    await client._poll_gensyn_once()

    assert client._inbox.empty()
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_topology_accepts_official_public_key_shape() -> None:
    respx.get("http://axl.local/topology").mock(
        return_value=httpx.Response(
            200,
            json={
                "our_public_key": "buyer-peer",
                "peers": [{"public_key": "seller-peer", "address": "200:abcd::1"}],
            },
        )
    )
    client = AxlClient("http://axl.local", peer_id="buyer-peer", api_mode="gensyn")

    peers = await client.topology()

    assert [(p.peer_id, p.multiaddr) for p in peers] == [("seller-peer", "200:abcd::1")]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_mock_send_keeps_local_demo_endpoint() -> None:
    route = respx.post("http://axl.local/send/seller-peer").mock(return_value=httpx.Response(200))
    client = AxlClient("http://axl.local", peer_id="buyer", api_mode="mock")

    await client.send("seller-peer", {"rfq_id": "rfq-1"})

    assert route.called
    assert route.calls.last.request.content == b'{"payload":{"rfq_id":"rfq-1"},"from":"buyer"}'
    await client.aclose()
