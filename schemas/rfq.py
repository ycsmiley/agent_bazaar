"""RFQ message schema — buyer → all sellers over AXL.

Pydantic enforces the shape so a malicious or hallucinating counterparty cannot
inject arbitrary fields. All inputs are plain scalars; no eval / exec surface.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TaskType(str, Enum):
    API_CALL = "api_call"
    COMPUTATION = "computation"
    DATA_FETCH = "data_fetch"
    LLM_INFERENCE = "llm_inference"


class Task(BaseModel):
    type: TaskType
    # Inputs must be primitives. Nested structures require an explicit schema
    # extension — we refuse arbitrary dicts to shut down prompt-injection vectors.
    input: dict[str, str | int | float | bool] = Field(default_factory=dict)
    require_tee_proof: bool = False
    # JSON Schema (subset) describing the expected delivery payload.
    output_schema: dict[str, object] = Field(default_factory=dict)

    @field_validator("input")
    @classmethod
    def _no_control_chars(cls, v: dict[str, object]) -> dict[str, object]:
        for key, value in v.items():
            if isinstance(value, str) and any(ord(c) < 0x20 and c not in "\t\n" for c in value):
                raise ValueError(f"input[{key}] contains control characters")
        return v


class Budget(BaseModel):
    max_usdc_atomic: int = Field(gt=0, description="Ceiling in USDC atomic units (6 decimals).")
    accepted_tokens: list[str] = Field(default_factory=list)


class Constraints(BaseModel):
    min_reputation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    deadline_unix: int = Field(gt=0)


class RFQMessage(BaseModel):
    version: Literal["1.0"] = "1.0"
    rfq_id: str = Field(min_length=1, max_length=64)
    buyer_agent_id: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    buyer_axl_peer_id: str
    task: Task
    budget: Budget
    constraints: Constraints
    signature: str = Field(description="ed25519 signature (hex) of the canonical JSON body.")
