from __future__ import annotations

import pytest
import respx
from httpx import Response

from agents.lib.uniswap_client import UniswapClient

BUYER = "0x" + "b" * 40
USDC = "0x" + "1" * 40
ETH = "0x" + "e" * 40


@pytest.mark.asyncio
@respx.mock
async def test_check_approval_reports_needed():
    respx.post("https://u.test/check_approval").mock(
        return_value=Response(
            200,
            json={"approval": {"to": "0xperm2", "data": "0xdeadbeef", "value": "0"}},
        )
    )
    client = UniswapClient("https://u.test", "k")
    approval = await client.check_approval(token=ETH, amount=10**16, wallet_address=BUYER)
    await client.aclose()
    assert not approval.approved
    assert approval.tx is not None
    body = route_body(respx.calls[0])
    assert body["chainId"] == 84532


@pytest.mark.asyncio
@respx.mock
async def test_bridge_to_usdc_returns_tx_hash():
    respx.post("https://u.test/quote").mock(
        return_value=Response(
            200,
            json={
                "quote": {
                    "output": {"amount": "500000"},
                    "minOutput": {"amount": "498000"},
                    "route": [{"pool": "ETH/USDC"}],
                    "gasFee": "100000",
                    "quoteId": "q1",
                }
            },
        )
    )
    respx.post("https://u.test/swap").mock(
        return_value=Response(
            200,
            json={"transactionHash": "0xabc", "amountOut": "499500"},
        )
    )

    client = UniswapClient("https://u.test", "k")
    result = await client.bridge_to_usdc(
        input_token=ETH,
        amount_in=10**16,
        wallet_address=BUYER,
        usdc_address=USDC,
    )
    await client.aclose()

    assert result.tx_hash == "0xabc"
    assert result.amount_out == 499_500
    body = route_body(respx.calls[0])
    assert body["tokenInChainId"] == 84532
    assert body["tokenOutChainId"] == 84532


def route_body(call) -> dict[str, object]:
    import json

    return json.loads(call.request.content.decode())
