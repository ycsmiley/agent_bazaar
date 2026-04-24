"""Seller agent — answers RFQs, executes, proves delivery.

Lifecycle (mirrors the buyer trace in reverse):

  1. Boot  → publish capabilities to 0G Storage, read own reputation.
  2. Loop  → consume AXL inbox.
              • On RFQ matching our capabilities: build + sign a Quote.
              • On escrow LOCKED event for our quote: run the task
                (via 0G Compute when TEE is required), upload payload to
                0G Storage, confirmDelivery, send payload over AXL.
              • On RELEASED: append a SUCCESS record to 0G history.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from nacl.signing import SigningKey
from web3 import Web3

from agents.lib.axl_client import AxlClient
from agents.lib.config import Config, load_config
from agents.lib.erc8004_client import Erc8004Client
from agents.lib.escrow_client import DealState, EscrowClient
from agents.lib.og_compute_client import OGComputeClient, canonical_content_hash
from agents.lib.og_storage_client import (
    Capabilities,
    HistoryRecord,
    OGStorageClient,
    ReputationSnapshot,
)
from agents.lib.signing import sign_payload, verify_payload
from schemas.quote import DeliveryPayload, Erc8004ReputationSnapshot, QuoteMessage
from schemas.rfq import RFQMessage, TaskType

log = logging.getLogger(__name__)


class SellerAgent:
    def __init__(
        self,
        cfg: Config,
        *,
        agent_id: str,
        signing_key: SigningKey,
        capabilities: list[str],
        use_tee: bool = True,
    ) -> None:
        self.cfg = cfg
        self.agent_id = agent_id
        self.signing_key = signing_key
        self.verify_key_hex = signing_key.verify_key.encode().hex()
        self.capabilities = capabilities
        self.use_tee = use_tee

        self.axl = AxlClient(cfg.axl_endpoint, peer_id=self.verify_key_hex)
        self.og_storage = OGStorageClient(cfg.og_storage_indexer)
        self.og_compute = OGComputeClient(cfg.og_compute_broker, default_model=cfg.og_compute_model)

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

    async def boot(self) -> None:
        caps = Capabilities(
            agent_id=self.agent_id,
            capabilities=self.capabilities,
            supported_task_types=["data_fetch", "llm_inference", "computation"],
            max_budget_acceptance=10_000_000,
            avg_delivery_ms=3000,
        )
        await self.og_storage.put_capabilities(caps)
        log.info("seller %s published capabilities", self.agent_id)

    async def run_forever(self) -> None:
        await self.boot()
        async for msg in self.axl.inbox():
            try:
                await self._handle(msg)
            except Exception as exc:  # noqa: BLE001 — loop must not die on one bad msg
                log.exception("handler error: %s", exc)

    # ───── handlers ────────────────────────────────────────────────────

    async def _handle(self, msg: dict[str, Any]) -> None:
        # RFQ messages carry `task` and `budget`.
        if "task" in msg and "budget" in msg:
            rfq = RFQMessage.model_validate(msg)
            if not verify_payload(msg, rfq.buyer_axl_peer_id):
                log.warning("dropping RFQ with bad signature")
                return
            await self._maybe_quote(rfq)
            return
        # "trigger" messages from the buyer after funds lock: rfq_id + locked=True.
        if msg.get("locked") and msg.get("rfq_id"):
            await self._execute_and_deliver(msg["rfq_id"], msg.get("buyer_peer_id"), msg.get("task_input", {}))

    async def _maybe_quote(self, rfq: RFQMessage) -> None:
        task_type = rfq.task.type.value
        if task_type not in {"data_fetch", "llm_inference", "computation", "api_call"}:
            return

        reputation = await self._reputation_snapshot()

        quote = QuoteMessage(
            rfq_id=rfq.rfq_id,
            seller_agent_id=self.agent_id,
            seller_axl_peer_id=self.verify_key_hex,
            quote_price_atomic=min(rfq.budget.max_usdc_atomic, 420_000),
            confidence_score=0.91,
            estimated_delivery_ms=2800,
            og_storage_history_ref=f"0g://kv/agentbazaar/{self.agent_id}:history",
            erc8004_reputation=reputation,
            will_use_tee=self.use_tee,
            signature="",
        )
        payload = quote.model_dump()
        payload["signature"] = sign_payload(payload, self.signing_key)
        await self.axl.send(rfq.buyer_axl_peer_id, payload)
        log.info("sent quote for rfq=%s to peer=%s", rfq.rfq_id, rfq.buyer_axl_peer_id[:8])

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
        content, tee_sig, provider, model = await self._produce_result(task_input)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Upload content blob to 0G Storage → root hash becomes resultHash.
        content_bytes = str(content).encode("utf-8")
        await self.og_storage.upload_blob(content_bytes)
        result_hash_hex = canonical_content_hash(content)

        # On-chain confirmDelivery.
        rfq_bytes = bytes.fromhex(rfq_id.replace("-", "").ljust(64, "0")[:64])
        tx_hash = self.escrow.confirm_delivery(rfq_bytes, bytes.fromhex(result_hash_hex[2:]))
        log.info("confirmDelivery tx=%s elapsed=%dms", tx_hash, elapsed_ms)

        payload = DeliveryPayload(
            rfq_id=rfq_id,
            seller_agent_id=self.agent_id,
            content=content,
            result_hash=result_hash_hex,
            tee_signature=tee_sig,
            tee_provider=provider,
            model_used=model,
            og_storage_tx_id=tx_hash,
            signature="",
        )
        signed = payload.model_dump()
        signed["signature"] = sign_payload(signed, self.signing_key)
        await self.axl.send(buyer_peer_id, signed)

        await self.og_storage.append_history(
            self.agent_id,
            HistoryRecord(
                timestamp=int(time.time()),
                rfq_id=rfq_id,
                counterparty_agent_id=buyer_peer_id,
                task_type="data_fetch",
                amount_usdc=0,  # filled on RELEASED event
                delivery_ms=elapsed_ms,
                result_hash=result_hash_hex,
                outcome="SUCCESS",
                tx_hash=tx_hash,
            ),
        )

    async def _produce_result(
        self,
        task_input: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None, str | None, str | None]:
        prompt = str(task_input.get("prompt", "fetch"))
        if self.use_tee:
            r = await self.og_compute.infer(messages=[{"role": "user", "content": prompt}])
            content = dict(r.content) if isinstance(r.content, dict) else {"answer": r.content}
            return content, r.tee_signature, r.provider, r.model
        # Demo fallback: deterministic canned response.
        return ({"answer": f"answered: {prompt}"}, None, None, None)

    async def _reputation_snapshot(self) -> Erc8004ReputationSnapshot:
        cached = await self.og_storage.get_reputation(self.agent_id)
        if cached is not None:
            return Erc8004ReputationSnapshot(
                total_tasks=cached.total_tasks,
                success_rate=cached.success_rate,
                on_chain_proof_uri=f"erc8004://reputation/{self.agent_id}",
            )
        # Cold start — assume a baseline so new agents can still bid.
        return Erc8004ReputationSnapshot(
            total_tasks=1,
            success_rate=0.85,
            on_chain_proof_uri=f"erc8004://reputation/{self.agent_id}",
        )

    async def aclose(self) -> None:
        await asyncio.gather(
            self.axl.aclose(), self.og_storage.aclose(), self.og_compute.aclose()
        )


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
