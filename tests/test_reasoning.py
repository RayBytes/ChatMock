"""Tests for chatmock.reasoning helpers."""

from __future__ import annotations

import chatmock.reasoning as rea


def test_build_reasoning_param_overrides_and_validation() -> None:
    r = rea.build_reasoning_param("low", "auto", {"effort": "high", "summary": "concise"})
    assert r["effort"] == "high" and r["summary"] == "concise"
    # invalid values fall back to defaults and strip 'none' summary
    r2 = rea.build_reasoning_param("weird", "nope", {"effort": "bogus", "summary": "none"})
    assert r2["effort"] == "medium" and "summary" not in r2


def test_apply_reasoning_modes() -> None:
    # o3 packs summary+full into reasoning.content
    msg = {"content": "hi"}
    out = rea.apply_reasoning_to_message(msg.copy(), "sum", "full", "o3")
    assert "reasoning" in out and out["reasoning"]["content"][0]["type"] == "text"

    # legacy/current use fields
    out2 = rea.apply_reasoning_to_message(msg.copy(), "sum", "full", "legacy")
    assert out2.get("reasoning_summary") == "sum" and out2.get("reasoning") == "full"
    out3 = rea.apply_reasoning_to_message(msg.copy(), "sum", "full", "current")
    assert out3.get("reasoning_summary") == "sum" and out3.get("reasoning") == "full"

    # think-tags injects <think> prefix
    out4 = rea.apply_reasoning_to_message({"content": "X"}, "sum", "full", "think-tags")
    assert isinstance(out4.get("content"), str) and out4["content"].startswith("<think>")


def test_extract_reasoning_from_model_name() -> None:
    assert rea.extract_reasoning_from_model_name("gpt-5:high") == {"effort": "high"}
    assert rea.extract_reasoning_from_model_name("gpt-5_low") == {"effort": "low"}
    assert rea.extract_reasoning_from_model_name("gpt-5-medium") == {"effort": "medium"}
    assert rea.extract_reasoning_from_model_name("gpt-5") is None
