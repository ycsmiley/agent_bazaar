"""0G Compute client — TeeML sealed inference (Layer 4).

When the RFQ demands `require_tee_proof=true`, the seller cannot just hand
back a JSON result and claim an LLM produced it — the buyer would have to
trust them. 0G Compute runs the inference inside a TEE and returns a
signed attestation over the (prompt, response, model) triple. The buyer
can then verify the attestation locally without ever talking to the
provider.

This client wraps the broker-side HTTP surface:

    POST /infer         → run a model inside a TEE, get back response + sig
    POST /verify        → verify an arbitrary (content, sig) pair

The seller-side call returns a `TeeResponse` that our DeliveryPayload
schema already knows how to carry: content, tee_signature, tee_provider,
model_used.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeeResponse:
    content: dict[str, object]
    tee_signature: str
    provider: str
    model: str
    raw: dict[str, Any]


class OGComputeClient:
    def __init__(
        self,
        broker_url: str,
        *,
        default_model: str = "deepseek-chat-v3-0324",
        timeout_secs: float = 60.0,
    ) -> None:
        self._http = httpx.AsyncClient(base_url=broker_url.rstrip("/"), timeout=timeout_secs)
        self.default_model = default_model

    async def infer(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> TeeResponse:
        body = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = await self._http.post("/infer", json=body)
        resp.raise_for_status()
        data = resp.json()
        return TeeResponse(
            content=data["response"],
            tee_signature=data["tee_signature"],
            provider=data["provider_address"],
            model=data["model"],
            raw=data,
        )

    async def verify(
        self,
        *,
        content: dict[str, object],
        tee_signature: str,
        provider: str,
    ) -> bool:
        """Ask the broker to verify an attestation. In a mature deployment
        the buyer can also verify locally against a cached TEE root cert;
        we call out to the broker for MVP simplicity.
        """
        resp = await self._http.post(
            "/verify",
            json={
                "content": content,
                "tee_signature": tee_signature,
                "provider": provider,
            },
        )
        if resp.status_code == 200:
            return bool(resp.json().get("valid", False))
        if resp.status_code in (400, 422):
            return False
        resp.raise_for_status()
        return False

    async def aclose(self) -> None:
        await self._http.aclose()


def canonical_content_hash(content: dict[str, object]) -> str:
    """Keccak-style hash of the canonical JSON `content`.

    We cite this hash on escrow.confirmDelivery so the buyer (and anyone
    watching the chain) can tie the on-chain tx back to the exact TEE
    payload that was produced.
    """
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "0x" + hashlib.sha3_256(canonical).hexdigest()
