#!/usr/bin/env python3
"""Fetch a real Uniswap quote without pretending a swap was executed."""

from __future__ import annotations

import asyncio
import json

from agents.lib.config import load_config
from agents.lib.uniswap_client import UniswapClient


async def main() -> int:
    cfg = load_config(role="buyer")
    client = UniswapClient(cfg.uniswap_api_base, cfg.uniswap_api_key)
    try:
        approval = await client.check_approval(
            token=cfg.uniswap_input_token,
            amount=cfg.uniswap_quote_amount,
            wallet_address=cfg.wallet_address,
            chain_id=cfg.uniswap_chain_id,
        )
        quote = await client.quote(
            token_in=cfg.uniswap_input_token,
            token_out=cfg.uniswap_output_token,
            amount_in=cfg.uniswap_quote_amount,
            wallet_address=cfg.wallet_address,
            chain_id=cfg.uniswap_chain_id,
        )
        print(
            json.dumps(
                {
                    "chain_id": cfg.uniswap_chain_id,
                    "token_in": quote.token_in,
                    "token_out": quote.token_out,
                    "amount_in": str(quote.amount_in),
                    "amount_out": str(quote.amount_out),
                    "quote_id": quote.quote_id,
                    "approval_required": not approval.approved,
                    "route": quote.route,
                    "gas_estimate": quote.gas_estimate,
                },
                indent=2,
            )
        )
    finally:
        await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
