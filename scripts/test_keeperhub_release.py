#!/usr/bin/env python3
"""Create a tiny delivered deal, trigger KeeperHub release, and verify state."""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path

import httpx


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in Path(".env").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    output = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(output)
    return output


def deal_state(env: dict[str, str], rfq_id: str) -> int:
    output = run(
        [
            "cast",
            "call",
            env["ESCROW_ADDRESS"],
            "getDeal(bytes32)(address,address,uint256,address,uint64,uint64,bytes32,uint8)",
            rfq_id,
            "--rpc-url",
            env["RPC_URL"],
        ]
    )
    return int(output.splitlines()[-1])


def main() -> int:
    env = load_env()
    rfq_id = "0x" + uuid.uuid4().hex.ljust(64, "0")[:64]
    result_hash = "0x" + "ab" * 32

    print(f"Creating delivered deal rfqId={rfq_id}")
    lock_out = run(
        [
            "cast",
            "send",
            env["ESCROW_ADDRESS"],
            "lockFunds(bytes32,address,uint256,address,uint64,uint64)",
            rfq_id,
            env["SELLER_ADDRESS"],
            "1",
            env["USDC_ADDRESS"],
            "600",
            "2",
            "--rpc-url",
            env["RPC_URL"],
            "--private-key",
            env["BUYER_PRIVATE_KEY"],
        ]
    )
    print(_tx_line("lock tx", lock_out))

    confirm_out = run(
        [
            "cast",
            "send",
            env["ESCROW_ADDRESS"],
            "confirmDelivery(bytes32,bytes32)",
            rfq_id,
            result_hash,
            "--rpc-url",
            env["RPC_URL"],
            "--private-key",
            env["SELLER_PRIVATE_KEY"],
        ]
    )
    print(_tx_line("confirm tx", confirm_out))

    time.sleep(3)
    payload = {"rfqId": rfq_id}
    url = env.get("KEEPERHUB_WORKFLOW_RELEASE_WEBHOOK") or (
        f"{env['KEEPERHUB_MCP_ENDPOINT'].rstrip('/')}"
        f"/workflows/{env['KEEPERHUB_WORKFLOW_RELEASE']}/runs"
    )
    body: dict[str, object] = payload if "webhook" in url else {"inputs": payload}
    headers = {"Authorization": f"Bearer {env['KEEPERHUB_API_KEY']}"}
    response = httpx.post(url, json=body, headers=headers, timeout=30)
    print(f"KeeperHub trigger status={response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text[:1000])

    time.sleep(20)
    state = deal_state(env, rfq_id)
    print(f"Final deal state={state} ({_state_name(state)})")
    return 0 if state == 3 else 1


def _tx_line(label: str, cast_output: str) -> str:
    for line in cast_output.splitlines():
        if line.strip().startswith("transactionHash"):
            return f"{label}: {line.split()[-1]}"
    return f"{label}: <not found>"


def _state_name(state: int) -> str:
    return {
        0: "OPEN",
        1: "LOCKED",
        2: "DELIVERED",
        3: "RELEASED",
        4: "DISPUTED",
        5: "REFUNDED",
    }.get(state, "UNKNOWN")


if __name__ == "__main__":
    raise SystemExit(main())
