from __future__ import annotations

import httpx
import pytest
import respx

from agents.lib.market_data_task import (
    SellerExecutionError,
    coinbase_product_id,
    content_hash,
    fetch_market_data,
    normalize_pair,
)


def test_normalize_pair_accepts_slash_or_dash() -> None:
    assert normalize_pair("eth/usdc") == "ETH/USDC"
    assert normalize_pair("btc-usd") == "BTC/USD"
    assert coinbase_product_id("eth/usdc") == "ETH-USD"


def test_content_hash_is_stable_for_canonical_json() -> None:
    left = {"pair": "ETH/USDC", "price": 1.0}
    right = {"price": 1.0, "pair": "ETH/USDC"}

    assert content_hash(left) == content_hash(right)
    assert content_hash(left).startswith("0x")
    assert len(content_hash(left)) == 66


@respx.mock
async def test_fetch_market_data_executes_real_provider_shape() -> None:
    respx.get("https://api.exchange.coinbase.com/products/ETH-USD/ticker").mock(
        return_value=httpx.Response(
            200,
            json={
                "price": "3412.15",
                "volume": "12345.67",
                "time": "2026-05-03T06:00:00Z",
            },
        )
    )

    content = await fetch_market_data(
        {"pair": "ETH/USDC", "prompt": "Fetch spot price and volume."}
    )

    assert content["pair"] == "ETH/USDC"
    assert content["market_pair"] == "ETH/USD"
    assert content["price"] == 3412.15
    assert content["quote_currency"] == "USD"
    assert content["volume_24h"] == 12345.67
    assert content["source"] == "coinbase_exchange"
    assert content["source_url"] == "https://api.exchange.coinbase.com/products/ETH-USD/ticker"
    assert content["prompt_echo"] == "Fetch spot price and volume."


@respx.mock
async def test_fetch_market_data_fails_loudly() -> None:
    respx.get("https://api.exchange.coinbase.com/products/ETH-USD/ticker").mock(
        return_value=httpx.Response(503, json={"message": "unavailable"})
    )

    with pytest.raises(SellerExecutionError, match="seller failed to fetch ETH/USDC"):
        await fetch_market_data({"pair": "ETH/USDC"})
