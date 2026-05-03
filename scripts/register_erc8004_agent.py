#!/usr/bin/env python3
"""Register the seller wallet in the Agent Bazaar ERC-8004 identity registry."""

from __future__ import annotations

import json
from pathlib import Path

from web3 import Web3

from agents.lib.erc8004_client import Erc8004Client


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in Path(".env").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def main() -> int:
    env = load_env()
    w3 = Web3(Web3.HTTPProvider(env["RPC_URL"]))
    seller = env["SELLER_ADDRESS"]
    client = Erc8004Client(
        w3,
        identity_registry=env["ERC8004_IDENTITY_REGISTRY"],
        reputation_registry=env["ERC8004_REPUTATION_REGISTRY"],
        sender=seller,
        private_key=env["SELLER_PRIVATE_KEY"],
    )
    existing = client.agent_id_of(seller)
    if existing:
        print(json.dumps({"status": "already_registered", "agent_id": existing}, indent=2))
        return 0

    agent_card_uri = env.get("SELLER_AGENT_CARD_URI") or (
        "data:application/json,"
        '{"name":"Agent Bazaar Seller","capabilities":["data_fetch","market_analysis"]}'
    )
    tx_hash = client.register_agent(agent_card_uri)
    print(json.dumps({"status": "submitted", "tx_hash": tx_hash}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
