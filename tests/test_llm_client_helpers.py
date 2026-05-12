"""Tests for the LLMClient helpers that don't require a network call."""

from __future__ import annotations

import pytest

from src.decisions.llm_client import (
    DECISION_TOOL_SCHEMA,
    _hash_call,
    _validate_decision_tool_input,
)


def test_hash_call_is_deterministic_and_input_sensitive():
    h1 = _hash_call(
        model="claude-haiku-4-5-20251001",
        system_prompt="sys",
        user_message="msg",
        tool_schema=DECISION_TOOL_SCHEMA,
    )
    h2 = _hash_call(
        model="claude-haiku-4-5-20251001",
        system_prompt="sys",
        user_message="msg",
        tool_schema=DECISION_TOOL_SCHEMA,
    )
    h3 = _hash_call(
        model="claude-haiku-4-5-20251001",
        system_prompt="sys",
        user_message="different",
        tool_schema=DECISION_TOOL_SCHEMA,
    )
    assert h1 == h2
    assert h1 != h3


def test_validate_tool_input_normalizes_hold_and_full_withdraw():
    out = _validate_decision_tool_input({
        "reasoning": "Hold for now.",
        "action": "hold",
        "amount_fraction": 0.5,  # should be normalized to 0.0
        "confidence": 0.8,
    })
    assert out["amount_fraction"] == 0.0

    out2 = _validate_decision_tool_input({
        "reasoning": "Out completely.",
        "action": "full_withdraw",
        "amount_fraction": 0.3,  # should be normalized to 1.0
        "confidence": 0.9,
    })
    assert out2["amount_fraction"] == 1.0


def test_validate_tool_input_rejects_unknown_action():
    with pytest.raises(ValueError):
        _validate_decision_tool_input({
            "reasoning": "x",
            "action": "buy_stocks",
            "amount_fraction": 0.0,
            "confidence": 0.5,
        })


def test_validate_tool_input_rejects_out_of_range_confidence():
    with pytest.raises(ValueError):
        _validate_decision_tool_input({
            "reasoning": "x",
            "action": "hold",
            "amount_fraction": 0.0,
            "confidence": 1.5,
        })


def test_validate_tool_input_rejects_missing_fields():
    with pytest.raises(ValueError):
        _validate_decision_tool_input({
            "action": "hold",
            "amount_fraction": 0.0,
            "confidence": 0.5,
        })
