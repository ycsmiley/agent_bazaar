from __future__ import annotations

import respx
from httpx import Response

from agents.lib.signing import verify_payload
from agents.sdk import AgentBazaarSeller


def _handler(task_input: dict[str, object]) -> dict[str, object]:
    return {"echo": task_input["prompt"], "source": "test-agent"}


def test_seller_integration_config_is_copyable() -> None:
    seller = AgentBazaarSeller(
        name="Test SDK Seller",
        capabilities=["market_data", "api_call"],
        handler=_handler,
    )

    config = seller.integration_config()

    assert config["agent_id"] == seller.agent_id
    assert config["axl_peer_id"] == seller.public_key_hex
    assert config["capabilities"] == ["market_data", "api_call"]
    assert config["env"]["AGENT_BAZAAR_MARKET_URL"] == "http://127.0.0.1:4174"


@respx.mock
def test_publish_listing_posts_sdk_identity() -> None:
    route = respx.post("http://127.0.0.1:4174/api/listings").mock(
        return_value=Response(201, json={"sellers": []})
    )
    seller = AgentBazaarSeller(
        name="Test SDK Seller",
        capabilities=["market_data"],
        handler=_handler,
        min_price_usdc=0.34,
    )

    seller.publish_listing()

    assert route.called
    payload = route.calls.last.request.content
    assert seller.agent_id.encode() in payload
    assert b"340000" in payload


async def test_execute_returns_signed_delivery() -> None:
    seller = AgentBazaarSeller(
        name="Test SDK Seller",
        capabilities=["market_data"],
        handler=_handler,
    )

    delivery = await seller.execute({"prompt": "hello"}, rfq_id="rfq-1")

    assert delivery["rfq_id"] == "rfq-1"
    assert delivery["content"] == {"echo": "hello", "source": "test-agent"}
    assert str(delivery["result_hash"]).startswith("0x")
    assert verify_payload(delivery, seller.public_key_hex)
