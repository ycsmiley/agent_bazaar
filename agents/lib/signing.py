"""Canonical JSON signing for RFQ / Quote / Delivery payloads.

We sign the *body* (everything except the `signature` field itself) so the
verifier can recompute the exact bytes the signer signed. Canonical JSON
dump: sorted keys, compact separators, ensure_ascii=False.
"""

from __future__ import annotations

import json
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    body = {k: v for k, v in payload.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sign_payload(payload: dict[str, Any], signing_key: SigningKey) -> str:
    sig = signing_key.sign(canonical_bytes(payload)).signature
    return sig.hex()


def verify_payload(payload: dict[str, Any], verify_key_hex: str) -> bool:
    sig_hex = payload.get("signature")
    if not isinstance(sig_hex, str):
        return False
    try:
        vk = VerifyKey(bytes.fromhex(verify_key_hex))
        vk.verify(canonical_bytes(payload), bytes.fromhex(sig_hex))
        return True
    except (BadSignatureError, ValueError):
        return False
