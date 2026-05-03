#!/usr/bin/env python3
"""Check a real Gensyn AXL node endpoint.

Examples:
    PYTHONPATH=. python scripts/check_gensyn_axl.py --role buyer
    PYTHONPATH=. python scripts/check_gensyn_axl.py --role buyer --send-to $SELLER_AXL_PEER_ID
    PYTHONPATH=. python scripts/check_gensyn_axl.py --role seller --recv
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.lib.axl_client import AxlClient  # noqa: E402
from agents.lib.config import load_config  # noqa: E402

console = Console()


async def main() -> None:
    ap = argparse.ArgumentParser(description="Check a real Gensyn AXL HTTP API endpoint")
    ap.add_argument("--role", choices=["buyer", "seller"], default="buyer")
    ap.add_argument("--send-to", help="Optional destination peer id for a ping payload")
    ap.add_argument("--recv", action="store_true", help="Poll /recv once after topology")
    args = ap.parse_args()

    cfg = load_config(role=args.role)
    peer_id = cfg.axl_peer_id
    if not peer_id:
        raise RuntimeError(f"{args.role.upper()}_AXL_PEER_ID is required")

    client = AxlClient(cfg.axl_endpoint, peer_id=peer_id, api_mode="gensyn")
    try:
        peers = await client.topology()

        t = Table(title=f"Gensyn AXL check ({args.role})")
        t.add_column("Field", style="dim")
        t.add_column("Value")
        t.add_row("endpoint", cfg.axl_endpoint)
        t.add_row("peer_id", peer_id)
        t.add_row("topology peers", str(len(peers)))
        for idx, peer in enumerate(peers[:8], start=1):
            t.add_row(f"peer {idx}", f"{peer.peer_id} {peer.multiaddr or ''}".strip())
        console.print(t)

        if args.send_to:
            payload = {
                "type": "agentbazaar.axl_ping",
                "from_role": args.role,
                "from_peer_id": peer_id,
                "ts": int(time.time()),
            }
            await client.send(args.send_to, payload)
            console.print(f"[green]sent ping to[/] {args.send_to}")

        if args.recv:
            await client._poll_gensyn_once()
            if client._inbox.empty():
                console.print("[yellow]recv empty[/] (204 No Content)")
            else:
                msg = await client._inbox.get()
                console.print("[green]received[/]")
                console.print(json.dumps(msg, indent=2, sort_keys=True))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
