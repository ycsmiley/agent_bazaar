"""Thin web3 wrapper around AgentBazaarEscrow.

Used by agents that need to submit transactions directly (without KeeperHub),
and by tests. In production the lock / optimistic-release / refund paths are
routed through KeeperHub workflows for retry + gas handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from web3 import Web3
from web3.contract import Contract


class DealState(IntEnum):
    OPEN = 0
    LOCKED = 1
    DELIVERED = 2
    RELEASED = 3
    DISPUTED = 4
    REFUNDED = 5


@dataclass(frozen=True)
class Deal:
    buyer: str
    seller: str
    amount: int
    token: str
    delivery_deadline: int
    dispute_deadline: int
    result_hash: bytes
    state: DealState


# Minimal ABI — enough for all agent-side interactions. Full ABI lives in
# out/AgentBazaarEscrow.sol/AgentBazaarEscrow.json after `forge build`.
ESCROW_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "rfqId", "type": "bytes32"},
            {"name": "seller", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "token", "type": "address"},
            {"name": "deliveryWindowSecs", "type": "uint64"},
            {"name": "disputeWindowSecs", "type": "uint64"},
        ],
        "name": "lockFunds",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "rfqId", "type": "bytes32"},
            {"name": "resultHash", "type": "bytes32"},
        ],
        "name": "confirmDelivery",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "rfqId", "type": "bytes32"}],
        "name": "releaseFunds",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "rfqId", "type": "bytes32"}],
        "name": "optimisticRelease",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "rfqId", "type": "bytes32"},
            {"name": "reason", "type": "string"},
        ],
        "name": "raiseDispute",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "rfqId", "type": "bytes32"}],
        "name": "claimRefund",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "rfqId", "type": "bytes32"}],
        "name": "getDeal",
        "outputs": [
            {"name": "buyer", "type": "address"},
            {"name": "seller", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "token", "type": "address"},
            {"name": "deliveryDeadline", "type": "uint64"},
            {"name": "disputeDeadline", "type": "uint64"},
            {"name": "resultHash", "type": "bytes32"},
            {"name": "state", "type": "uint8"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


class EscrowClient:
    def __init__(
        self,
        w3: Web3,
        escrow_address: str,
        *,
        sender: str,
        private_key: str | None = None,
    ) -> None:
        self.w3 = w3
        self.sender = Web3.to_checksum_address(sender)
        self._pk = private_key
        self.contract: Contract = w3.eth.contract(
            address=Web3.to_checksum_address(escrow_address), abi=ESCROW_ABI
        )

    # ───── writes ─────────────────────────────────────────────────────────

    def lock_funds(
        self,
        rfq_id: bytes,
        seller: str,
        amount: int,
        token: str,
        *,
        delivery_window_secs: int = 600,
        dispute_window_secs: int = 300,
    ) -> str:
        return self._send(
            self.contract.functions.lockFunds(
                rfq_id,
                Web3.to_checksum_address(seller),
                amount,
                Web3.to_checksum_address(token),
                delivery_window_secs,
                dispute_window_secs,
            )
        )

    def confirm_delivery(self, rfq_id: bytes, result_hash: bytes) -> str:
        return self._send(self.contract.functions.confirmDelivery(rfq_id, result_hash))

    def release_funds(self, rfq_id: bytes) -> str:
        return self._send(self.contract.functions.releaseFunds(rfq_id))

    def raise_dispute(self, rfq_id: bytes, reason: str) -> str:
        return self._send(self.contract.functions.raiseDispute(rfq_id, reason))

    # ───── reads ──────────────────────────────────────────────────────────

    def get_deal(self, rfq_id: bytes) -> Deal:
        result = self.contract.functions.getDeal(rfq_id).call()
        return Deal(
            buyer=result[0],
            seller=result[1],
            amount=result[2],
            token=result[3],
            delivery_deadline=result[4],
            dispute_deadline=result[5],
            result_hash=result[6],
            state=DealState(result[7]),
        )

    # ───── internals ──────────────────────────────────────────────────────

    def _send(self, fn: Any) -> str:
        tx = fn.build_transaction(
            {
                "from": self.sender,
                "nonce": self.w3.eth.get_transaction_count(self.sender),
                "chainId": self.w3.eth.chain_id,
            }
        )
        if self._pk is None:
            raise RuntimeError("private key required to send tx directly")
        signed = self.w3.eth.account.sign_transaction(tx, self._pk)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()
