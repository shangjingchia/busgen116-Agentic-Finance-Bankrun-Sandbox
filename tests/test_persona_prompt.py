"""Verify the persona-to-prompt renderer produces a coherent, complete brief."""

from __future__ import annotations

from src.core.agent import CostCategory, Severity
from src.personas.instances import make_margaret_chen
from src.personas.prompts import (
    render_decision_user_message,
    render_persona_system_prompt,
)


def test_system_prompt_contains_all_persona_sections():
    agent = make_margaret_chen()
    prompt = render_persona_system_prompt(agent.persona)

    # Persona name and age appear up front
    assert "Margaret Chen" in prompt
    assert "67" in prompt

    # Each major section header is present
    for header in (
        "## Who you are",
        "## Your goals",
        "## How you think about risk",
        "## Your financial sophistication",
        "## How you consume and weigh information",
        "## How you talk",
        "## Costs you take seriously",
        "## How to decide",
    ):
        assert header in prompt, f"missing section header: {header}"


def test_system_prompt_orders_costs_worst_first_and_includes_all_categories():
    agent = make_margaret_chen()
    prompt = render_persona_system_prompt(agent.persona)

    # "CATASTROPHIC" must appear before "MINOR" in the cost block
    cat_idx = prompt.find("CATASTROPHIC")
    minor_idx = prompt.find("MINOR")
    assert cat_idx != -1 and minor_idx != -1
    assert cat_idx < minor_idx

    # All seven cost categories appear in the prompt by their machine name
    for category in CostCategory:
        assert category.value in prompt, f"cost category {category.value} missing from prompt"


def test_user_message_has_portfolio_and_observation():
    agent = make_margaret_chen()
    msg = render_decision_user_message(
        agent=agent,
        bank_id_in_focus="bank_a",
        observations=["Rumor on twitter (credibility 0.40): Bank A may be insolvent."],
        sim_time_seconds=12.5,
    )
    assert "bank_a" in msg
    assert "$50,000" in msg
    assert "$12,000" in msg
    assert "$62,000" in msg
    assert "T+12s" in msg or "T+13s" in msg
    assert "record_financial_decision" in msg


def test_voice_examples_appear_verbatim():
    """The voice examples are style anchors; they must reach the LLM verbatim."""
    agent = make_margaret_chen()
    prompt = render_persona_system_prompt(agent.persona)
    for example in agent.persona.voice_examples:
        assert example in prompt, f"voice example missing: {example!r}"
