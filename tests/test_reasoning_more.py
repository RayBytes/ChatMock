"""Extra branch coverage for reasoning helpers."""

from __future__ import annotations

import chatmock.reasoning as rea


def test_build_reasoning_param_invalid_override_summary() -> None:
    # invalid override summary should be ignored
    r = rea.build_reasoning_param("low", "auto", {"effort": "low", "summary": "weird"})
    assert r["effort"] == "low" and r["summary"] == "auto"


def test_build_reasoning_param_invalid_base_and_no_overrides() -> None:
    r = rea.build_reasoning_param("low", "bad", None)
    assert r["summary"] == "auto" and r["effort"] == "low"


def test_apply_reasoning_o3_variants() -> None:
    # only summary present
    out1 = rea.apply_reasoning_to_message({}, "sum", "", "o3")
    assert "reasoning" in out1
    # only full present
    out2 = rea.apply_reasoning_to_message({}, "", "full", "o3")
    assert "reasoning" in out2
    # neither present -> no reasoning field
    out3 = rea.apply_reasoning_to_message({}, "  ", "\t", "o3")
    assert "reasoning" not in out3


def test_apply_reasoning_legacy_current_partial_fields() -> None:
    out1 = rea.apply_reasoning_to_message({}, "sum", "", "legacy")
    assert out1.get("reasoning_summary") == "sum" and "reasoning" not in out1
    out2 = rea.apply_reasoning_to_message({}, "", "full", "current")
    assert out2.get("reasoning") == "full" and "reasoning_summary" not in out2


def test_think_tags_non_str_content() -> None:
    msg = {"content": ["not a string"]}
    out = rea.apply_reasoning_to_message(msg, "sum", "full", "think-tags")
    # content remains non-str; only exercise type guard branch
    assert isinstance(out.get("content"), list)


def test_extract_reasoning_from_model_name_edge_inputs() -> None:
    assert rea.extract_reasoning_from_model_name(None) is None
    assert rea.extract_reasoning_from_model_name("   ") is None
    # unknown suffix after colon falls through
    assert rea.extract_reasoning_from_model_name("gpt-5:weird") is None
    # cover remaining suffixes
    assert rea.extract_reasoning_from_model_name("gpt-5-minimal") == {"effort": "minimal"}
    assert rea.extract_reasoning_from_model_name("gpt_5_high") == {"effort": "high"}
