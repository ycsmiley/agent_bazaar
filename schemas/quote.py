"""Quote message schema — seller → buyer reply to an RFQ."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Erc8004ReputationSnapshot(BaseModel):
    total_tasks: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    on_chain_proof_uri: str


class QuoteMessage(BaseModel):
    version: Literal["1.0"] = "1.0"
    rfq_id: str
    seller_agent_id: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    seller_axl_peer_id: str
    quote_price_atomic: int = Field(gt=0, description="Quoted price in USDC atomic units.")
    confidence_score: float = Field(ge=0.0, le=1.0)
    estimated_delivery_ms: int = Field(gt=0)
    erc8004_reputation: Erc8004ReputationSnapshot
    signature: str


class DeliveryPayload(BaseModel):
    """Seller → buyer: the actual result plus the hash committed on-chain."""

    rfq_id: str
    seller_agent_id: str
    content: dict[str, object]
    result_hash: str = Field(description="Hex keccak256 of canonical `content`.")
    signature: str
