#!/usr/bin/env python3
"""Validate hackathon demo environment without printing secrets."""

from __future__ import annotations

from pathlib import Path

from eth_account import Account

REQUIRED_FOR_LOCAL = [
    "CHAIN_ID",
    "RPC_URL",
    "BUYER_PRIVATE_KEY",
    "SELLER_PRIVATE_KEY",
    "ESCROW_ADDRESS",
    "USDC_ADDRESS",
    "BUYER_AXL_ENDPOINT",
    "SELLER_AXL_ENDPOINT",
]

REQUIRED_FOR_LIVE = REQUIRED_FOR_LOCAL + [
    "KEEPERHUB_API_KEY",
    "KEEPERHUB_MCP_ENDPOINT",
    "KEEPERHUB_WORKFLOW_LOCK",
    "KEEPERHUB_WORKFLOW_RELEASE",
    "KEEPERHUB_WORKFLOW_REFUND",
    "UNISWAP_API_KEY",
]

ANVIL_KEYS = {
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
    "0x59c6995e998f97a5a004497e5da1a24d45e90e2da78c7a9d75a0c7c0fd6f5f0f",
}

ANVIL_DEFAULT_CONTRACTS = {
    "0x5fbdb2315678afecb367f032d93f642f64180aa3",
    "0xe7f1725e7734ce288f8367e1bb143e90bb3f0512",
    "0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0",
    "0xcf7ed3acca5a467e9e704c703e8d87f634fb0fc9",
}


def _load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _mask(value: str) -> str:
    if not value:
        return "missing"
    if len(value) <= 12:
        return "set"
    return f"{value[:6]}...{value[-4:]}"


def _address_from_key(private_key: str) -> str:
    try:
        return Account.from_key(private_key).address
    except Exception:  # noqa: BLE001
        return "<invalid private key>"


def main() -> int:
    path = Path(".env")
    if not path.exists():
        print("Missing .env. Copy .env.example first.")
        return 1

    env = _load_env(path)
    chain_id = env.get("CHAIN_ID", "")
    rpc_url = env.get("RPC_URL", "")
    local_chain = chain_id == "31337" or "127.0.0.1" in rpc_url or "localhost" in rpc_url

    print("Agent Bazaar environment check")
    print(f"- Mode: {'local/anvil' if local_chain else 'testnet/live candidate'}")
    print(f"- CHAIN_ID: {chain_id or 'missing'}")
    print(f"- RPC_URL: {rpc_url or 'missing'}")
    print(f"- ESCROW_ADDRESS: {_mask(env.get('ESCROW_ADDRESS', ''))}")
    print(f"- USDC_ADDRESS: {_mask(env.get('USDC_ADDRESS', ''))}")
    print(f"- KeeperHub workflows: {_workflow_summary(env)}")
    print(f"- Uniswap API key: {_mask(env.get('UNISWAP_API_KEY', ''))}")

    for role in ("BUYER", "SELLER"):
        private_key = env.get(f"{role}_PRIVATE_KEY", "")
        configured = env.get(f"{role}_ADDRESS", "")
        derived = _address_from_key(private_key) if private_key else ""
        print(f"- {role}: address={configured or derived or 'missing'} key={_mask(private_key)}")
        if private_key.lower() in ANVIL_KEYS:
            print(f"  ! {role}_PRIVATE_KEY is a default Anvil key. Do not use it for testnet.")
        if configured and derived and configured.lower() != derived.lower():
            print(f"  ! {role}_ADDRESS does not match {role}_PRIVATE_KEY.")

    missing_local = [key for key in REQUIRED_FOR_LOCAL if not env.get(key)]
    missing_live = [key for key in REQUIRED_FOR_LIVE if not env.get(key)]
    if missing_local:
        print("\nMissing for local demo:")
        for key in missing_local:
            print(f"- {key}")
    if missing_live:
        print("\nMissing for live/testnet demo:")
        for key in missing_live:
            print(f"- {key}")

    if local_chain:
        print("\nNext for hackathon readiness:")
        print("- Replace CHAIN_ID/RPC_URL with Base Sepolia or another public testnet.")
        print("- Replace default Anvil keys with funded testnet wallets.")
        print("- Redeploy contracts and paste the new addresses into .env.")
    else:
        for key in ("ESCROW_ADDRESS", "USDC_ADDRESS"):
            value = env.get(key, "").lower()
            if value in ANVIL_DEFAULT_CONTRACTS:
                print(f"\n! {key} looks like an Anvil default deployment address.")
                print("  Redeploy on testnet and paste the new address into .env.")
        print("\nNext for hackathon readiness:")
        print("- Confirm wallets have gas.")
        print("- Run scripts/deploy_contracts.sh if contract addresses are not final.")
        print("- Run scripts/prepare_testnet_funds.sh when using MockUSDC.")

    return 0 if not missing_local else 1


def _workflow_summary(env: dict[str, str]) -> str:
    keys = [
        "KEEPERHUB_WORKFLOW_LOCK",
        "KEEPERHUB_WORKFLOW_RELEASE",
        "KEEPERHUB_WORKFLOW_REFUND",
    ]
    present = sum(1 for key in keys if env.get(key))
    return f"{present}/3 set"


if __name__ == "__main__":
    raise SystemExit(main())
