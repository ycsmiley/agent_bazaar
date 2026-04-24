"""Uniswap Trade API client.

Two flows drive AgentBazaar:

  Pre-lock swap    — buyer holds ETH but escrow only takes USDC.
                     swap ETH → USDC, then hand off to KeeperHub lock.

  Post-release swap — seller prefers DAI (or any other token); the release
                     keeper reads the seller's preference and swaps
                     USDC → DAI on their behalf before the payout lands.

Each `swap()` call returns a real TxID — this is the identifier Uniswap's
hackathon track requires in the submission.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SwapQuote:
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    amount_out_min: int
    route: list[dict[str, Any]]
    gas_estimate: int
    quote_id: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class SwapResult:
    tx_hash: str
    amount_out: int
    raw: dict[str, Any]


@dataclass(frozen=True)
class Approval:
    approved: bool
    tx: dict[str, Any] | None


class UniswapClient:
    def __init__(
        self,
        api_base: str,
        api_key: str,
        *,
        timeout_secs: float = 20.0,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=api_base.rstrip("/"),
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=timeout_secs,
        )

    async def check_approval(
        self,
        *,
        token: str,
        amount: int,
        wallet_address: str,
    ) -> Approval:
        """Returns the Permit2 approval tx the buyer needs to sign, or a
        flag saying the allowance is already sufficient.
        """
        resp = await self._http.post(
            "/check_approval",
            json={
                "token": token,
                "amount": str(amount),
                "walletAddress": wallet_address,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("approval") is None:
            return Approval(approved=True, tx=None)
        return Approval(approved=False, tx=data["approval"])

    async def quote(
        self,
        *,
        token_in: str,
        token_out: str,
        amount_in: int,
        wallet_address: str,
        slippage_bps: int = 50,
    ) -> SwapQuote:
        resp = await self._http.post(
            "/quote",
            json={
                "tokenIn": token_in,
                "tokenOut": token_out,
                "amount": str(amount_in),
                "type": "EXACT_INPUT",
                "swapper": wallet_address,
                "slippageTolerance": slippage_bps / 100.0,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        q = data["quote"]
        return SwapQuote(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            amount_out=int(q["output"]["amount"]),
            amount_out_min=int(q.get("minOutput", {}).get("amount", q["output"]["amount"])),
            route=q.get("route", []),
            gas_estimate=int(q.get("gasFee", 0)),
            quote_id=q.get("quoteId") or q.get("id", ""),
            raw=data,
        )

    async def swap(
        self,
        *,
        quote: SwapQuote,
        wallet_address: str,
        signed_permit: dict[str, Any] | None = None,
    ) -> SwapResult:
        """Execute the swap the buyer/seller has a quote for.

        For hackathon demos we rely on the Trade API building + submitting the
        tx directly via the wallet service (the `wallet` query param on the
        Uniswap side). The returned tx_hash is the real on-chain TxID the
        Uniswap track requires in the submission.
        """
        payload: dict[str, Any] = {
            "quote": quote.raw["quote"],
            "swapper": wallet_address,
        }
        if signed_permit is not None:
            payload["permitData"] = signed_permit

        resp = await self._http.post("/swap", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return SwapResult(
            tx_hash=data["transactionHash"],
            amount_out=int(data.get("amountOut", quote.amount_out)),
            raw=data,
        )

    # ───── high-level helpers ─────────────────────────────────────────────

    async def bridge_to_usdc(
        self,
        *,
        input_token: str,
        amount_in: int,
        wallet_address: str,
        usdc_address: str,
    ) -> SwapResult:
        """Buyer side: swap whatever-they-hold → USDC so the escrow can lock."""
        quote = await self.quote(
            token_in=input_token,
            token_out=usdc_address,
            amount_in=amount_in,
            wallet_address=wallet_address,
        )
        return await self.swap(quote=quote, wallet_address=wallet_address)

    async def bridge_from_usdc(
        self,
        *,
        amount_in: int,
        wallet_address: str,
        usdc_address: str,
        preferred_token: str,
    ) -> SwapResult:
        """Seller side: released USDC → preferred token (e.g. DAI)."""
        quote = await self.quote(
            token_in=usdc_address,
            token_out=preferred_token,
            amount_in=amount_in,
            wallet_address=wallet_address,
        )
        return await self.swap(quote=quote, wallet_address=wallet_address)

    async def aclose(self) -> None:
        await self._http.aclose()
