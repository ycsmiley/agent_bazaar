"""Seller agent — answers RFQs, executes tasks, proves delivery.

Lifecycle:
  1. Boot  → register capabilities in memory, read own reputation from ERC-8004.
  2. Loop  → consume AXL inbox.
              • On RFQ matching our capabilities: build + sign a Quote.
              • On "locked" trigger from buyer: run the task, hash result,
                confirmDelivery on-chain, send payload over AXL.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

from nacl.signing import SigningKey
from web3 import Web3

from agents.lib.axl_client import AxlClient
from agents.lib.config import Config, load_config
from agents.lib.erc8004_client import Erc8004Client
from agents.lib.escrow_client import EscrowClient
from agents.lib.signing import sign_payload, verify_payload
from schemas.quote import DeliveryPayload, Erc8004ReputationSnapshot, QuoteMessage
from schemas.rfq import RFQMessage

log = logging.getLogger(__name__)


def _content_hash(content: dict[str, object]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    return "0x" + hashlib.sha3_256(canonical).hexdigest()


def _rfq_id_bytes(rfq_id: str) -> bytes:
    if rfq_id.startswith("0x") and len(rfq_id) == 66:
        return bytes.fromhex(rfq_id[2:])
    return bytes.fromhex(rfq_id.replace("-", "").ljust(64, "0")[:64])


class SellerAgent:
    def __init__(
        self,
        cfg: Config,
        *,
        agent_id: str,
        signing_key: SigningKey,
        capabilities: list[str],
    ) -> None:
        self.cfg = cfg
        self.agent_id = agent_id
        self.signing_key = signing_key
        self.verify_key_hex = signing_key.verify_key.encode().hex()
        self.capabilities = capabilities

        self.axl_peer_id = cfg.axl_peer_id or self.verify_key_hex
        self.axl = AxlClient(
            cfg.axl_endpoint,
            peer_id=self.axl_peer_id,
            api_mode=cfg.axl_transport,
        )

        w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
        self.escrow = EscrowClient(
            w3, cfg.escrow_address, sender=cfg.wallet_address, private_key=cfg.private_key
        )
        self.erc8004 = Erc8004Client(
            w3,
            identity_registry=cfg.erc8004_identity,
            reputation_registry=cfg.erc8004_reputation,
            sender=cfg.wallet_address,
            private_key=cfg.private_key,
        )

    # ───── public entry ────────────────────────────────────────────────

    async def run_forever(self) -> None:
        log.info("seller %s online, capabilities: %s", self.agent_id[:10], self.capabilities)
        async for msg in self.axl.inbox():
            try:
                await self._handle(msg)
            except Exception as exc:  # noqa: BLE001
                log.exception("handler error: %s", exc)

    # ───── handlers ────────────────────────────────────────────────────

    async def _handle(self, msg: dict[str, Any]) -> None:
        if "task" in msg and "budget" in msg:
            rfq = RFQMessage.model_validate(msg)
            if not verify_payload(msg, rfq.buyer_axl_peer_id):
                log.warning("dropping RFQ with bad signature")
                return
            await self._maybe_quote(rfq)
            return

        if msg.get("locked") and msg.get("rfq_id"):
            await self._execute_and_deliver(
                msg["rfq_id"],
                msg.get("buyer_peer_id"),
                msg.get("task_input", {}),
            )

    async def _maybe_quote(self, rfq: RFQMessage) -> None:
        task_type = rfq.task.type.value
        if task_type not in {"data_fetch", "api_call", "computation", "llm_inference"}:
            return

        quote = QuoteMessage(
            rfq_id=rfq.rfq_id,
            seller_agent_id=self.agent_id,
                seller_axl_peer_id=self.axl_peer_id,
            quote_price_atomic=min(rfq.budget.max_usdc_atomic, 420_000),
            confidence_score=0.91,
            estimated_delivery_ms=2800,
            erc8004_reputation=Erc8004ReputationSnapshot(
                total_tasks=47,
                success_rate=0.957,
                on_chain_proof_uri=f"erc8004://reputation/{self.agent_id}",
            ),
            signature="",
        )
        payload = quote.model_dump()
        payload["signature"] = sign_payload(payload, self.signing_key)
        await self.axl.send(rfq.buyer_axl_peer_id, payload)
        log.info("sent quote for rfq=%s price=%d", rfq.rfq_id[:8], quote.quote_price_atomic)

    async def _execute_and_deliver(
        self,
        rfq_id: str,
        buyer_peer_id: str | None,
        task_input: dict[str, Any],
    ) -> None:
        if not buyer_peer_id:
            log.warning("trigger missing buyer_peer_id — skipping")
            return

        start = time.perf_counter()
        content = await self._run_task(task_input)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        result_hash = _content_hash(content)
        rfq_bytes = _rfq_id_bytes(rfq_id)
        tx_hash = self.escrow.confirm_delivery(rfq_bytes, bytes.fromhex(result_hash[2:]))
        log.info("confirmDelivery tx=%s elapsed=%dms", tx_hash, elapsed_ms)

        payload = DeliveryPayload(
            rfq_id=rfq_id,
            seller_agent_id=self.agent_id,
            content=content,
            result_hash=result_hash,
            signature="",
        )
        signed = payload.model_dump()
        signed["signature"] = sign_payload(signed, self.signing_key)
        await self.axl.send(buyer_peer_id, signed)

    async def _run_task(self, task_input: dict[str, Any]) -> dict[str, Any]:
        """Execute the task. Extend this to call real APIs or LLMs."""
        prompt = str(task_input.get("prompt", ""))
        pair = str(task_input.get("pair", "ETH/USDC"))
        # Demo: return a realistic-looking market data response
        return {
            "pair": pair,
            "price": 3412.15,
            "volume_24h": 1_234_567_890,
            "source": "agentbazaar-seller",
            "timestamp": int(time.time()),
            "prompt_echo": prompt[:64],
        }

    async def aclose(self) -> None:
        await self.axl.aclose()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(role="seller")
    sk = SigningKey.generate()
    seller = SellerAgent(
        cfg,
        agent_id=cfg.wallet_address,
        signing_key=sk,
        capabilities=["price_query", "data_fetch", "market_analysis"],
    )
    try:
        await seller.run_forever()
    finally:
        await seller.aclose()


if __name__ == "__main__":
    asyncio.run(main())
