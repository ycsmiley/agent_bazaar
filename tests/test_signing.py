from __future__ import annotations

from nacl.signing import SigningKey

from agents.lib.signing import canonical_bytes, sign_payload, verify_payload


def test_canonical_ignores_signature_field_and_key_order():
    a = {"b": 1, "a": 2, "signature": "XXX"}
    b = {"a": 2, "b": 1, "signature": "YYY"}
    assert canonical_bytes(a) == canonical_bytes(b)


def test_sign_verify_roundtrip():
    sk = SigningKey.generate()
    vk_hex = sk.verify_key.encode().hex()
    payload = {"rfq_id": "1", "task": "fetch", "signature": ""}
    payload["signature"] = sign_payload(payload, sk)
    assert verify_payload(payload, vk_hex)


def test_tampered_payload_rejected():
    sk = SigningKey.generate()
    vk_hex = sk.verify_key.encode().hex()
    payload = {"rfq_id": "1", "task": "fetch", "signature": ""}
    payload["signature"] = sign_payload(payload, sk)
    payload["task"] = "attack"
    assert not verify_payload(payload, vk_hex)
