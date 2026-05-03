from __future__ import annotations

import json

from scripts.generate_market_trace import build_market_trace, write_trace


def test_market_trace_uses_matching_winner() -> None:
    trace = build_market_trace(now=1_777_737_600)

    assert trace["project"]["name"] == "Agent Bazaar"
    assert trace["source"]["mode"] == "local_project_playback"
    assert trace["matching"]["formula"] == "confidence * reputation / price"
    assert trace["quotes"][0]["selected"] is True
    assert trace["quotes"][0]["seller"] == trace["matching"]["winner"]
    assert trace["quotes"][0]["seller_label"] == "Efficient Price Agent"
    assert trace["quotes"][-1]["status"] == "rejected"
    assert "reputation" in trace["quotes"][-1]["reason"]


def test_market_trace_delivery_hash_is_stable() -> None:
    trace = build_market_trace(now=1_777_737_600)

    assert trace["delivery"]["verified"] is True
    assert trace["delivery"]["result_hash"].startswith("0x")
    assert len(trace["delivery"]["result_hash"]) == 66


def test_write_trace_outputs_browser_global(tmp_path) -> None:
    output = tmp_path / "market-trace-data.js"
    write_trace(output)

    text = output.read_text(encoding="utf-8")
    assert text.startswith("window.MARKET_TRACE = ")
    data = json.loads(text.removeprefix("window.MARKET_TRACE = ").removesuffix(";\n"))
    assert data["proofs"]["uniswap_quote_id"]
    assert data["proofs"]["keeperhub_lock_execution"]
