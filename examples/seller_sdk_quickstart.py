"""Open-box seller integration example.

Run the demo service first:

    PYTHONPATH=. python scripts/serve_trade_playback.py

Then publish this external seller:

    PYTHONPATH=. python examples/seller_sdk_quickstart.py

Open http://127.0.0.1:4174/market-trace.html?role=buyer and the buyer can match
this seller through the normal marketplace flow.
"""

from __future__ import annotations

import asyncio
import json

from agents.lib.market_data_task import fetch_market_data
from agents.sdk import AgentBazaarSeller


async def market_data_handler(task_input: dict[str, object]) -> dict[str, object]:
    """Your agent's real work goes here."""

    return await fetch_market_data(task_input)


async def main() -> None:
    seller = AgentBazaarSeller(
        name="SDK Market Data Agent",
        capabilities=["market_data", "api_call"],
        handler=market_data_handler,
        quota_available=8,
        min_price_usdc=0.34,
        confidence=0.92,
        success_rate=0.96,
        estimated_delivery_ms=2600,
    )

    print("Agent integration config:")
    print(json.dumps(seller.integration_config(), indent=2))

    print("\nPublishing seller capacity to Agent Bazaar...")
    seller.publish_listing()
    print("Seller is online and matchable by buyer RFQs.")

    print("\nLocal delivery smoke test:")
    delivery = await seller.execute(
        {"pair": "ETH/USDC", "prompt": "Fetch spot price and 24h volume."},
        rfq_id="sdk-smoke-test",
    )
    print(json.dumps(delivery, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
