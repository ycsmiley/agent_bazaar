#!/usr/bin/env python3
"""Submit one ERC-8004 feedback signal from buyer to seller."""

from __future__ import annotations

import json
import time
from pathlib import Path

from web3 import Web3
from web3.exceptions import TransactionNotFound

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
    buyer = Erc8004Client(
        w3,
        identity_registry=env["ERC8004_IDENTITY_REGISTRY"],
        reputation_registry=env["ERC8004_REPUTATION_REGISTRY"],
        sender=env["BUYER_ADDRESS"],
        private_key=env["BUYER_PRIVATE_KEY"],
    )
    agent_id = buyer.agent_id_of(env["SELLER_ADDRESS"])
    if agent_id == 0:
        raise RuntimeError("seller is not registered; run scripts/register_erc8004_agent.py")
    tx_hash = buyer.submit_feedback(
        agent_id=agent_id,
        rating=5,
        tags=["keeperhub-settled", "hash-verified"],
        proof_uri="agent-bazaar://keeperhub/test",
    )
    receipt = None
    for _ in range(20):
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            receipt = None
        if receipt is not None:
            break
        time.sleep(2)
    rep = buyer.get_reputation(agent_id)
    print(
        json.dumps(
            {
                "agent_id": agent_id,
                "feedback_tx": tx_hash,
                "receipt_status": receipt.status if receipt else None,
                "total_tasks": rep.total_tasks,
                "success_rate": rep.success_rate,
                "avg_rating": rep.avg_rating,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
