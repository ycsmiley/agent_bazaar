"""Uniswap Trade API client.

Agent Bazaar currently uses Uniswap as a real quote/check proof for supported
Base routes. Escrow settlement in the hackathon demo uses Base Sepolia MockUSDC
separately, so the demo does not claim a swap tx.
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
        chain_id: int = 84532,
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
                "chainId": chain_id,
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
        chain_id: int = 84532,
        slippage_bps: int = 50,
    ) -> SwapQuote:
        resp = await self._http.post(
            "/quote",
            json={
                "tokenIn": token_in,
                "tokenOut": token_out,
                "tokenInChainId": chain_id,
                "tokenOutChainId": chain_id,
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

        This method is kept for the production path, but the hackathon demo uses
        quote/check proof only and does not call `/swap`.
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
        chain_id: int = 84532,
    ) -> SwapResult:
        """Production path: swap whatever the buyer holds into escrow USDC."""
        quote = await self.quote(
            token_in=input_token,
            token_out=usdc_address,
            amount_in=amount_in,
            wallet_address=wallet_address,
            chain_id=chain_id,
        )
        return await self.swap(quote=quote, wallet_address=wallet_address)

    async def bridge_from_usdc(
        self,
        *,
        amount_in: int,
        wallet_address: str,
        usdc_address: str,
        preferred_token: str,
        chain_id: int = 84532,
    ) -> SwapResult:
        """Production path: swap released USDC into the seller's preferred token."""
        quote = await self.quote(
            token_in=usdc_address,
            token_out=preferred_token,
            amount_in=amount_in,
            wallet_address=wallet_address,
            chain_id=chain_id,
        )
        return await self.swap(quote=quote, wallet_address=wallet_address)

    async def aclose(self) -> None:
        await self._http.aclose()
