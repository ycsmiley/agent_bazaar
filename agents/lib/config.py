"""Runtime config loaded once from environment variables.

Centralising this means the agent code can just `cfg = load_config()` and
every sponsor-track client has what it needs; no scattered `os.getenv`
calls inside business logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from eth_account import Account


@dataclass(frozen=True)
class Config:
    # Chain
    chain_id: int
    rpc_url: str
    escrow_address: str
    usdc_address: str
    # ERC-8004
    erc8004_identity: str
    erc8004_reputation: str
    # AXL
    axl_endpoint: str
    axl_transport: str
    axl_peer_id: str
    # KeeperHub
    keeperhub_endpoint: str
    keeperhub_api_key: str
    keeperhub_workflow_lock: str
    keeperhub_workflow_release: str
    keeperhub_workflow_refund: str
    keeperhub_workflow_lock_webhook: str
    keeperhub_workflow_release_webhook: str
    keeperhub_workflow_refund_webhook: str
    # Uniswap
    uniswap_api_base: str
    uniswap_api_key: str
    uniswap_chain_id: int
    uniswap_input_token: str
    uniswap_output_token: str
    uniswap_quote_amount: int
    # Identity (per-agent overrides from CLI)
    wallet_address: str
    private_key: str | None


def load_config(
    *,
    role: str = "buyer",
    env_path: Path | None = None,
) -> Config:
    if env_path is None:
        env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    def _get(name: str, default: str = "") -> str:
        return os.getenv(name, default)

    role_upper = role.upper()
    pk = _get(f"{role_upper}_PRIVATE_KEY") or None
    wallet = _get(f"{role_upper}_ADDRESS")
    if not wallet and pk:
        wallet = Account.from_key(pk).address

    axl_endpoint_key = (
        "BUYER_AXL_ENDPOINT" if role == "buyer" else "SELLER_AXL_ENDPOINT"
    )
    axl_peer_id_key = "BUYER_AXL_PEER_ID" if role == "buyer" else "SELLER_AXL_PEER_ID"

    return Config(
        chain_id=int(_get("CHAIN_ID", "84532")),
        rpc_url=_get("RPC_URL", "https://sepolia.base.org"),
        escrow_address=_get("ESCROW_ADDRESS"),
        usdc_address=_get("USDC_ADDRESS"),
        erc8004_identity=_get("ERC8004_IDENTITY_REGISTRY"),
        erc8004_reputation=_get("ERC8004_REPUTATION_REGISTRY"),
        axl_endpoint=_get(axl_endpoint_key, "http://localhost:9001"),
        axl_transport=_get("AXL_TRANSPORT", "gensyn"),
        axl_peer_id=_get(axl_peer_id_key),
        keeperhub_endpoint=_get("KEEPERHUB_MCP_ENDPOINT"),
        keeperhub_api_key=_get("KEEPERHUB_API_KEY"),
        keeperhub_workflow_lock=_get("KEEPERHUB_WORKFLOW_LOCK"),
        keeperhub_workflow_release=_get("KEEPERHUB_WORKFLOW_RELEASE"),
        keeperhub_workflow_refund=_get("KEEPERHUB_WORKFLOW_REFUND"),
        keeperhub_workflow_lock_webhook=_get("KEEPERHUB_WORKFLOW_LOCK_WEBHOOK"),
        keeperhub_workflow_release_webhook=_get("KEEPERHUB_WORKFLOW_RELEASE_WEBHOOK"),
        keeperhub_workflow_refund_webhook=_get("KEEPERHUB_WORKFLOW_REFUND_WEBHOOK"),
        uniswap_api_base=_get("UNISWAP_API_BASE", "https://trade-api.gateway.uniswap.org/v1"),
        uniswap_api_key=_get("UNISWAP_API_KEY"),
        uniswap_chain_id=int(_get("UNISWAP_CHAIN_ID", _get("CHAIN_ID", "84532"))),
        uniswap_input_token=_get(
            "UNISWAP_INPUT_TOKEN",
            "0x4200000000000000000000000000000000000006",
        ),
        uniswap_output_token=_get("UNISWAP_OUTPUT_TOKEN", _get("USDC_ADDRESS")),
        uniswap_quote_amount=int(_get("UNISWAP_QUOTE_AMOUNT", "1000000000000000")),
        wallet_address=wallet,
        private_key=pk,
    )
