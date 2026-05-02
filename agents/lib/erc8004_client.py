"""ERC-8004 Identity & Reputation registry client.

Two registries, same ABI shape on Base Sepolia:

  IdentityRegistry    — mint agentId (ERC-721) whose tokenURI points at the
                        Agent Card JSON.

  ReputationRegistry  — submitFeedback(agentId, rating, tags, proofURI)
                        and getReputation(agentId) aggregate view.

Only the entry points we actually use are wired. The full EIP-8004 ABI is
much larger but everything the protocol needs is reputation read/write
plus the minimal identity resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from web3 import Web3

IDENTITY_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"name": "agentCardURI", "type": "string"}],
        "name": "registerAgent",
        "outputs": [{"name": "agentId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "agentId", "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "agentIdOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

REPUTATION_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "rating", "type": "uint8"},
            {"name": "tags", "type": "string[]"},
            {"name": "proofURI", "type": "string"},
        ],
        "name": "submitFeedback",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "agentId", "type": "uint256"}],
        "name": "getReputation",
        "outputs": [
            {"name": "totalTasks", "type": "uint64"},
            {"name": "successCount", "type": "uint64"},
            {"name": "avgRatingBps", "type": "uint16"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass(frozen=True)
class ReputationView:
    total_tasks: int
    success_count: int
    avg_rating: float  # 0.0 - 5.0

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_tasks if self.total_tasks else 0.0


class Erc8004Client:
    def __init__(
        self,
        w3: Web3,
        *,
        identity_registry: str,
        reputation_registry: str,
        sender: str,
        private_key: str | None = None,
    ) -> None:
        self.w3 = w3
        self.sender = Web3.to_checksum_address(sender)
        self._pk = private_key
        self.identity = w3.eth.contract(
            address=Web3.to_checksum_address(identity_registry), abi=IDENTITY_ABI
        )
        self.reputation = w3.eth.contract(
            address=Web3.to_checksum_address(reputation_registry), abi=REPUTATION_ABI
        )

    # ───── identity ────────────────────────────────────────────────────

    def register_agent(self, agent_card_uri: str) -> str:
        return self._send(self.identity.functions.registerAgent(agent_card_uri))

    def agent_id_of(self, owner: str) -> int:
        return int(
            self.identity.functions.agentIdOf(Web3.to_checksum_address(owner)).call()
        )

    def agent_card_uri(self, agent_id: int) -> str:
        return self.identity.functions.tokenURI(agent_id).call()

    # ───── reputation ──────────────────────────────────────────────────

    def submit_feedback(
        self,
        *,
        agent_id: int,
        rating: int,
        tags: list[str],
        proof_uri: str,
    ) -> str:
        if not 0 <= rating <= 5:
            raise ValueError("rating must be 0..5")
        return self._send(
            self.reputation.functions.submitFeedback(agent_id, rating, tags, proof_uri)
        )

    def get_reputation(self, agent_id: int) -> ReputationView:
        total, success, avg_bps = self.reputation.functions.getReputation(agent_id).call()
        return ReputationView(
            total_tasks=int(total),
            success_count=int(success),
            avg_rating=int(avg_bps) / 10_000 * 5.0,
        )

    # ───── internals ───────────────────────────────────────────────────

    def _send(self, fn: Any) -> str:
        if self._pk is None:
            raise RuntimeError("private key required for write")
        tx = fn.build_transaction(
            {
                "from": self.sender,
                "nonce": self.w3.eth.get_transaction_count(self.sender),
                "chainId": self.w3.eth.chain_id,
            }
        )
        signed = self.w3.eth.account.sign_transaction(tx, self._pk)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()
