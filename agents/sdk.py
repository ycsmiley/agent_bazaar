"""Tiny public SDK for connecting external agents to Agent Bazaar.

The demo market intentionally keeps the integration surface small: create a
seller, publish its capacity, and return signed deliveries from a Python handler.
This file is the copy-paste path for hackathon judges and other agent builders.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from nacl.signing import SigningKey

from agents.lib.market_data_task import content_hash
from agents.lib.signing import sign_payload

TaskHandler = Callable[[dict[str, Any]], dict[str, object] | Awaitable[dict[str, object]]]


@dataclass(frozen=True)
class AgentBazaarConfig:
    """Connection details an external agent needs to join the market."""

    market_url: str = "http://127.0.0.1:4174"
    axl_endpoint: str = "http://127.0.0.1:9001"
    axl_transport: str = "mock"


@dataclass(frozen=True)
class SellerListing:
    """Public seller capacity advertised to Agent Bazaar matching."""

    label: str
    capabilities: list[str]
    quota_available: int = 10
    min_price_usdc: float = 0.30
    confidence: float = 0.88
    success_rate: float = 0.90
    estimated_delivery_ms: int = 3200
    total_tasks: int = 0

    def as_payload(self) -> dict[str, object]:
        return {
            "label": self.label,
            "capabilities": ",".join(self.capabilities),
            "quota_available": self.quota_available,
            "min_price_atomic": int(self.min_price_usdc * 1_000_000),
            "confidence": self.confidence,
            "success_rate": self.success_rate,
            "estimated_delivery_ms": self.estimated_delivery_ms,
            "total_tasks": self.total_tasks,
        }


@dataclass
class AgentBazaarSeller:
    """Open-box seller integration for external Python agents.

    Example:

        seller = AgentBazaarSeller(
            name="My Data Agent",
            capabilities=["market_data", "api_call"],
            handler=my_task_handler,
        )
        seller.publish_listing()
    """

    name: str
    capabilities: list[str]
    handler: TaskHandler
    config: AgentBazaarConfig = field(default_factory=AgentBazaarConfig)
    signing_key: SigningKey = field(default_factory=SigningKey.generate)
    quota_available: int = 10
    min_price_usdc: float = 0.30
    confidence: float = 0.88
    success_rate: float = 0.90
    estimated_delivery_ms: int = 3200

    @property
    def public_key_hex(self) -> str:
        return self.signing_key.verify_key.encode().hex()

    @property
    def agent_id(self) -> str:
        digest = hashlib.sha3_256(bytes.fromhex(self.public_key_hex)).hexdigest()
        return f"0x{digest[-40:]}"

    @property
    def axl_peer_id(self) -> str:
        return self.public_key_hex

    def integration_config(self) -> dict[str, object]:
        """Return the config block an agent developer can copy into their app."""

        return {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "public_key": self.public_key_hex,
            "axl_peer_id": self.axl_peer_id,
            "market_url": self.config.market_url,
            "axl_endpoint": self.config.axl_endpoint,
            "axl_transport": self.config.axl_transport,
            "capabilities": self.capabilities,
            "env": {
                "AGENT_BAZAAR_MARKET_URL": self.config.market_url,
                "AGENT_BAZAAR_AXL_ENDPOINT": self.config.axl_endpoint,
                "AGENT_BAZAAR_AXL_TRANSPORT": self.config.axl_transport,
            },
        }

    def listing(self) -> SellerListing:
        return SellerListing(
            label=self.name,
            capabilities=self.capabilities,
            quota_available=self.quota_available,
            min_price_usdc=self.min_price_usdc,
            confidence=self.confidence,
            success_rate=self.success_rate,
            estimated_delivery_ms=self.estimated_delivery_ms,
        )

    def listing_payload(self) -> dict[str, object]:
        payload = self.listing().as_payload()
        payload["agent_id"] = self.agent_id
        payload["agent_public_key"] = self.public_key_hex
        return payload

    def healthcheck(self) -> dict[str, object]:
        return {
            "ok": True,
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": self.capabilities,
            "market_url": self.config.market_url,
        }

    def publish_listing(self, *, timeout: float = 8.0) -> dict[str, object]:
        """Publish seller capacity to the local demo market."""

        with httpx.Client(base_url=self.config.market_url, timeout=timeout) as client:
            response = client.post("/api/listings", json=self.listing_payload())
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Agent Bazaar market returned a non-object response")
        return data

    async def execute(
        self,
        task_input: dict[str, Any],
        *,
        rfq_id: str = "sdk-local",
    ) -> dict[str, object]:
        """Run the external agent handler and return a signed delivery payload."""

        result = self.handler(task_input)
        content = await result if asyncio.iscoroutine(result) else result
        delivery = {
            "rfq_id": rfq_id,
            "seller_agent_id": self.agent_id,
            "content": content,
            "result_hash": content_hash(content),
            "signature": "",
        }
        delivery["signature"] = sign_payload(delivery, self.signing_key)
        return delivery
