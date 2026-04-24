"""Buyer agent — orchestrates the full five-layer trade flow.

End-to-end sequence mirrors section 7 of the spec:

  1. Build + sign an RFQMessage.
  2. Broadcast over AXL.
  3. Collect quotes for a fixed window, rank them, pick the winner.
  4. (Optional) Uniswap swap into USDC → fire KeeperHub lock.
  5. Wait for the seller's confirmDelivery event.
  6. Fetch delivery payload over AXL, validate schema, verify TEE.
  7. releaseFunds (or raiseDispute) + submit ERC-8004 feedback.

This file is the glue; every layer-specific concern lives in agents/lib/.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from nacl.signing import SigningKey
from web3 import Web3

from agents.lib.axl_client import AxlClient
from agents.lib.config import Config, load_config
from agents.lib.erc8004_client import Erc8004Client
from agents.lib.escrow_client import DealState, EscrowClient
from agents.lib.keeperhub_client import KeeperHubClient
from agents.lib.matching import select_best
from agents.lib.og_compute_client import OGComputeClient, canonical_content_hash
from agents.lib.og_storage_client import OGStorageClient
from agents.lib.signing import sign_payload, verify_payload
from agents.lib.uniswap_client import UniswapClient
from schemas.quote import DeliveryPayload, QuoteMessage
from schemas.rfq import Budget, Constraints, RFQMessage, Task, TaskType

log = logging.getLogger(__name__)


class BuyerAgent:
    def __init__(
        self,
        cfg: Config,
        *,
        agent_id: str,
        signing_key: SigningKey,
    ) -> None:
        self.cfg = cfg
        self.agent_id = agent_id
        self.signing_key = signing_key
        self.verify_key_hex = signing_key.verify_key.encode().hex()

        self.axl = AxlClient(cfg.axl_endpoint, peer_id=self.verify_key_hex)
        self.uniswap = UniswapClient(cfg.uniswap_api_base, cfg.uniswap_api_key)
        self.keeperhub = KeeperHubClient(cfg.keeperhub_endpoint, cfg.keeperhub_api_key)
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

    async def run_one_trade(
        self,
        *,
        task_input: dict[str, Any],
        task_type: TaskType = TaskType.DATA_FETCH,
        budget_atomic: int = 500_000,
        require_tee: bool = False,
        collection_window_secs: float = 10.0,
    ) -> dict[str, str]:
        rfq = self._build_rfq(
            task_input=task_input,
            task_type=task_type,
            budget_atomic=budget_atomic,
            require_tee=require_tee,
        )
        log.info("broadcasting RFQ %s", rfq.rfq_id)
        await self.axl.broadcast(rfq.model_dump())

        quotes = await self._collect_quotes(rfq.rfq_id, collection_window_secs)
        log.info("collected %d quotes for %s", len(quotes), rfq.rfq_id)

        winner = select_best(rfq, quotes)
        if winner is None:
            raise RuntimeError("no eligible quote for this RFQ")
        log.info("winner: %s @ %d", winner.seller_agent_id, winner.quote_price_atomic)

        lock_tx = await self._ensure_usdc_and_lock(winner)
        delivery = await self._await_delivery(winner)
        release_tx = await self._settle(winner, delivery)
        feedback_tx = self._submit_feedback(winner, outcome="SUCCESS")

        return {
            "rfq_id": rfq.rfq_id,
            "lock_tx": lock_tx,
            "release_tx": release_tx,
            "feedback_tx": feedback_tx,
        }

    # ───── internals ───────────────────────────────────────────────────

    def _build_rfq(
        self,
        *,
        task_input: dict[str, Any],
        task_type: TaskType,
        budget_atomic: int,
        require_tee: bool,
    ) -> RFQMessage:
        rfq = RFQMessage(
            rfq_id=str(uuid.uuid4()),
            buyer_agent_id=self.agent_id,
            buyer_axl_peer_id=self.verify_key_hex,
            task=Task(
                type=task_type,
                input={k: v for k, v in task_input.items() if isinstance(v, (str, int, float, bool))},
                require_tee_proof=require_tee,
                output_schema={"type": "object"},
            ),
            budget=Budget(
                max_usdc_atomic=budget_atomic,
                accepted_tokens=[self.cfg.usdc_address],
            ),
            constraints=Constraints(
                min_reputation_score=0.8,
                deadline_unix=int(time.time()) + 600,
            ),
            signature="",
        )
        payload = rfq.model_dump()
        payload["signature"] = sign_payload(payload, self.signing_key)
        return RFQMessage.model_validate(payload)

    async def _collect_quotes(self, rfq_id: str, window_secs: float) -> list[QuoteMessage]:
        quotes: list[QuoteMessage] = []
        deadline = time.monotonic() + window_secs

        async def _consume() -> None:
            async for msg in self.axl.inbox():
                if msg.get("rfq_id") != rfq_id or "quote_price_atomic" not in msg:
                    continue
                # signature on the seller's ed25519 key — we verify on the
                # seller_axl_peer_id they announced.
                peer_id = msg.get("seller_axl_peer_id", "")
                if not verify_payload(msg, peer_id):
                    log.warning("dropping quote with bad signature from %s", peer_id)
                    continue
                try:
                    quotes.append(QuoteMessage.model_validate(msg))
                except Exception as exc:  # pydantic ValidationError
                    log.warning("dropping malformed quote: %s", exc)

        try:
            await asyncio.wait_for(_consume(), timeout=max(0.0, deadline - time.monotonic()))
        except asyncio.TimeoutError:
            pass
        return quotes

    async def _ensure_usdc_and_lock(self, quote: QuoteMessage) -> str:
        """If the buyer doesn't already hold enough USDC we bridge via
        Uniswap first; then we fire the KeeperHub lock workflow so the
        deal becomes LOCKED with retries + audit trail.
        """
        # Demo simplification: we always path through Uniswap first so the
        # track's required swap TxID is present regardless of wallet state.
        # Production would check on-chain balance and skip when possible.
        _ = await self.uniswap.bridge_to_usdc(
            input_token="ETH",
            amount_in=quote.quote_price_atomic * 10**12,  # crude ETH size
            wallet_address=self.cfg.wallet_address,
            usdc_address=self.cfg.usdc_address,
        )

        run = await self.keeperhub.fire_lock(
            self.cfg.keeperhub_workflow_lock,
            rfq_id=quote.rfq_id,
            seller=quote.seller_agent_id,
            amount=quote.quote_price_atomic,
            token=self.cfg.usdc_address,
        )
        settled = await self.keeperhub.wait_for_tx(run.run_id)
        if settled.tx_hash is None:
            raise RuntimeError(f"lock workflow failed: {settled.error}")
        return settled.tx_hash

    async def _await_delivery(self, quote: QuoteMessage) -> DeliveryPayload:
        async for msg in self.axl.inbox():
            if msg.get("rfq_id") != quote.rfq_id or "tee_signature" not in msg and "result_hash" not in msg:
                continue
            if not verify_payload(msg, quote.seller_axl_peer_id):
                log.warning("delivery signature invalid — ignoring")
                continue
            payload = DeliveryPayload.model_validate(msg)
            if canonical_content_hash(payload.content).lower().replace("0x", "") != payload.result_hash.lower().replace("0x", ""):
                log.warning("result_hash does not match content")
                continue
            return payload
        raise RuntimeError("inbox closed before delivery arrived")

    async def _settle(self, quote: QuoteMessage, payload: DeliveryPayload) -> str:
        if quote.will_use_tee and payload.tee_signature and payload.tee_provider:
            ok = await self.og_compute.verify(
                content=payload.content,
                tee_signature=payload.tee_signature,
                provider=payload.tee_provider,
            )
            if not ok:
                dispute_tx = self.escrow.raise_dispute(
                    bytes.fromhex(quote.rfq_id.replace("-", "").ljust(64, "0")[:64]),
                    "invalid_tee_signature",
                )
                raise RuntimeError(f"TEE verification failed — dispute raised: {dispute_tx}")
        rfq_bytes = bytes.fromhex(quote.rfq_id.replace("-", "").ljust(64, "0")[:64])
        return self.escrow.release_funds(rfq_bytes)

    def _submit_feedback(self, quote: QuoteMessage, *, outcome: str) -> str:
        rating = 5 if outcome == "SUCCESS" else 1
        # agent_id of the winner — the ERC-8004 registry stores agentIds,
        # not addresses, so we resolve via the address embedded in the
        # Quote's seller_agent_id (which is an address in AgentBazaar).
        agent_id = self.erc8004.agent_id_of(quote.seller_agent_id)
        return self.erc8004.submit_feedback(
            agent_id=agent_id,
            rating=rating,
            tags=["fast", "accurate"] if outcome == "SUCCESS" else ["disputed"],
            proof_uri=f"agentbazaar://rfq/{quote.rfq_id}",
        )

    async def aclose(self) -> None:
        await asyncio.gather(
            self.axl.aclose(),
            self.uniswap.aclose(),
            self.keeperhub.aclose(),
            self.og_storage.aclose(),
            self.og_compute.aclose(),
        )


async def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="fetch ETH/USDC price")
    ap.add_argument("--budget", type=int, default=500_000)
    ap.add_argument("--require-tee", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)
    cfg = load_config(role="buyer")
    sk = SigningKey.generate()
    agent = BuyerAgent(cfg, agent_id=cfg.wallet_address, signing_key=sk)

    result = await agent.run_one_trade(
        task_input={"prompt": args.task, "pair": "ETH/USDC"},
        budget_atomic=args.budget,
        require_tee=args.require_tee,
    )
    print(result)
    await agent.aclose()


if __name__ == "__main__":
    asyncio.run(main())
