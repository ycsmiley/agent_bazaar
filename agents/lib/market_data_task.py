"""Real seller-side market data task execution."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx


class SellerExecutionError(RuntimeError):
    """Raised when the seller cannot complete a requested task."""


def content_hash(content: dict[str, object]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    return "0x" + hashlib.sha3_256(canonical).hexdigest()


def normalize_pair(pair: str) -> str:
    cleaned = pair.strip().upper().replace("-", "/")
    if "/" not in cleaned:
        raise SellerExecutionError(f"unsupported market pair: {pair!r}")
    base, quote = [part.strip() for part in cleaned.split("/", maxsplit=1)]
    if not base or not quote:
        raise SellerExecutionError(f"unsupported market pair: {pair!r}")
    return f"{base}/{quote}"


def coinbase_product_id(pair: str) -> str:
    normalized = normalize_pair(pair)
    base, quote = normalized.split("/", maxsplit=1)
    coinbase_quote = "USD" if quote == "USDC" else quote
    return f"{base}-{coinbase_quote}"


async def fetch_market_data(
    task_input: dict[str, Any],
    *,
    timeout: float = 8.0,
    client: httpx.AsyncClient | None = None,
) -> dict[str, object]:
    """Execute the seller task by querying Coinbase Exchange public market data.

    This intentionally fails loudly when the upstream request fails. The demo
    should show a seller execution failure instead of silently fabricating data.
    """

    prompt = str(task_input.get("prompt", ""))
    pair = normalize_pair(str(task_input.get("pair", "ETH/USDC")))
    product_id = coinbase_product_id(pair)
    market_pair = product_id.replace("-", "/")
    url = f"https://api.exchange.coinbase.com/products/{product_id}/ticker"

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout)
    started = time.perf_counter()
    try:
        response = await http.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SellerExecutionError(f"seller failed to fetch {pair} from Coinbase: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()

    try:
      price = float(payload["price"])
      volume_24h = float(payload.get("volume", 0))
    except (KeyError, TypeError, ValueError) as exc:
      raise SellerExecutionError(f"seller received malformed market data for {pair}") from exc

    return {
        "pair": pair,
        "market_pair": market_pair,
        "price": price,
        "quote_currency": market_pair.split("/", maxsplit=1)[1],
        "volume_24h": volume_24h,
        "source": "coinbase_exchange",
        "source_url": url,
        "observed_at": str(payload.get("time") or ""),
        "timestamp": int(time.time()),
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "prompt_echo": prompt[:96],
    }
