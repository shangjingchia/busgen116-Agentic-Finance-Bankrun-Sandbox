"""Day-3 archetype completeness and distinctness tests.

The bar (per CLAUDE.md): "Reviewers should be able to skim several agents'
reasoning logs and tell which persona produced which without seeing labels."
We can't fully test that without LLM calls, but we can enforce the
preconditions: every archetype has a complete cost function, the voice
examples and trust profiles are textually distinct, and each archetype's
system prompt renders cleanly.
"""

from __future__ import annotations

import pytest

from src.core.agent import CostCategory, Severity
from src.personas.archetypes import (
    ALL_ARCHETYPES,
    ARCHETYPE_AGGRESSIVE_TRADER,
    ARCHETYPE_CAUTIOUS_RETIREE,
    ARCHETYPE_GIG_WORKER,
    ARCHETYPE_INSTITUTIONAL_TREASURER,
    aggressive_trader_cost_function,
    build_archetype,
    cautious_retiree_cost_function,
    get_archetype_cost_function,
    gig_worker_cost_function,
    institutional_treasurer_cost_function,
)
from src.personas.instances import (
    make_all_canonical_agents,
    make_canonical_agent,
)
from src.personas.prompts import render_persona_system_prompt


_ALL_COST_FUNCTION_BUILDERS = {
    ARCHETYPE_CAUTIOUS_RETIREE: cautious_retiree_cost_function,
    ARCHETYPE_AGGRESSIVE_TRADER: aggressive_trader_cost_function,
    ARCHETYPE_GIG_WORKER: gig_worker_cost_function,
    ARCHETYPE_INSTITUTIONAL_TREASURER: institutional_treasurer_cost_function,
}


@pytest.mark.parametrize("archetype", ALL_ARCHETYPES)
def test_archetype_cost_function_covers_all_categories(archetype: str):
    """Every archetype must rate every cost category — otherwise the LLM has
    silent gaps in its weighting."""
    cf = _ALL_COST_FUNCTION_BUILDERS[archetype]()
    seen = {item.category for item in cf}
    assert seen == set(CostCategory), (
        f"{archetype} cost function missing categories: {set(CostCategory) - seen}"
    )


@pytest.mark.parametrize("archetype", ALL_ARCHETYPES)
def test_archetype_severities_are_valid(archetype: str):
    cf = _ALL_COST_FUNCTION_BUILDERS[archetype]()
    valid = {s for s in Severity}
    for item in cf:
        assert item.severity in valid


@pytest.mark.parametrize("archetype", ALL_ARCHETYPES)
def test_archetype_narratives_are_substantive(archetype: str):
    """Reject placeholder/stub narratives — these are the texture the LLM
    grounds reasoning in."""
    cf = _ALL_COST_FUNCTION_BUILDERS[archetype]()
    for item in cf:
        assert len(item.narrative) >= 60, (
            f"{archetype}/{item.category.value}: narrative too short "
            f"({len(item.narrative)} chars). Looks like a stub."
        )
        assert "placeholder" not in item.narrative.lower()


def test_archetypes_have_distinct_voice_examples():
    """No archetype should share a voice example with another — voice is the
    fingerprint."""
    seen: dict[str, str] = {}
    for archetype in ALL_ARCHETYPES:
        persona = build_archetype(
            archetype,
            name="Test",
            age=40,
            income_annual=50_000,
            dependents=0,
            background_narrative="Test background.",
        )
        for example in persona.voice_examples:
            assert example not in seen, (
                f"{archetype} voice example {example!r} also appears in {seen[example]}"
            )
            seen[example] = archetype


def test_archetypes_have_distinct_trust_profiles():
    """Trust profiles drive how a persona consumes information — they must
    be archetype-specific."""
    seen: set[str] = set()
    for archetype in ALL_ARCHETYPES:
        persona = build_archetype(
            archetype,
            name="Test",
            age=40,
            income_annual=50_000,
            dependents=0,
            background_narrative="Test background.",
        )
        assert persona.trust_profile not in seen, (
            f"{archetype} duplicates a trust profile from another archetype"
        )
        seen.add(persona.trust_profile)


def test_archetype_priors_make_sense_relative_to_each_other():
    """peer_action_reconsideration_threshold encodes how easily this kind of
    person is moved by peer behavior. The ordering should be intuitive."""
    pers = {a: build_archetype(
        a, name="Test", age=40, income_annual=50_000, dependents=0,
        background_narrative="Test."
    ) for a in ALL_ARCHETYPES}

    # Gig workers should be the most peer-influenced (lowest threshold).
    assert pers[ARCHETYPE_GIG_WORKER].peer_action_reconsideration_threshold < \
        pers[ARCHETYPE_CAUTIOUS_RETIREE].peer_action_reconsideration_threshold

    # Aggressive traders should be the least (most contrarian).
    assert pers[ARCHETYPE_AGGRESSIVE_TRADER].peer_action_reconsideration_threshold > \
        pers[ARCHETYPE_INSTITUTIONAL_TREASURER].peer_action_reconsideration_threshold

    # Institutional treasurers should be more peer-resistant than retirees.
    assert pers[ARCHETYPE_INSTITUTIONAL_TREASURER].peer_action_reconsideration_threshold > \
        pers[ARCHETYPE_CAUTIOUS_RETIREE].peer_action_reconsideration_threshold


@pytest.mark.parametrize("archetype", ALL_ARCHETYPES)
def test_canonical_instance_renders_clean_system_prompt(archetype: str):
    agent = make_canonical_agent(archetype)
    prompt = render_persona_system_prompt(agent.persona)
    # Has the agent's name
    assert agent.persona.name in prompt
    # All 7 cost categories appear
    for category in CostCategory:
        assert category.value in prompt
    # All voice examples appear verbatim
    for example in agent.persona.voice_examples:
        assert example in prompt


def test_get_archetype_cost_function_round_trip():
    for archetype in ALL_ARCHETYPES:
        cf = get_archetype_cost_function(archetype)
        assert len(cf) == len(CostCategory)


def test_make_all_canonical_agents_returns_four_distinct_archetypes():
    agents = make_all_canonical_agents()
    assert len(agents) == len(ALL_ARCHETYPES)
    archetypes_seen = {a.persona.archetype for a in agents}
    assert archetypes_seen == set(ALL_ARCHETYPES)
    # Different agent_ids
    assert len({a.agent_id for a in agents}) == len(agents)
