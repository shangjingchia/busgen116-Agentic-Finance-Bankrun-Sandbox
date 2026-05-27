"""
Persona-to-prompt rendering.

The renderer composes the persona into a system prompt that reads like a
coherent character brief, not a parameter dump. Reviewers should be able to
read several agents' system prompts and tell which persona is which without
seeing labels.
"""

from __future__ import annotations

from typing import List

from src.core.agent import (
    SEVERITY_RANK,
    Agent,
    CostItem,
    Persona,
    Severity,
)


_SEVERITY_HEADERS = {
    Severity.CATASTROPHIC: "CATASTROPHIC — these are the costs you most fear",
    Severity.SIGNIFICANT: "SIGNIFICANT — these costs hurt and you weigh them carefully",
    Severity.MODERATE: "MODERATE — you notice these but they don't drive decisions on their own",
    Severity.MINOR: "MINOR — you accept these as a normal cost of operating",
    Severity.IRRELEVANT: "IRRELEVANT — these do not factor into your reasoning",
}

_BANK_LABELS = {
    "bank_a": "Redwood Regional Bank",
    "bank_b": "Harbor National Bank",
}


def _bank_label(bank_id: str) -> str:
    label = _BANK_LABELS.get(bank_id)
    return f"{label} ({bank_id})" if label else bank_id


def _render_cost_function(cost_function: List[CostItem]) -> str:
    """Group cost items by severity, ordered worst-to-least."""
    by_sev: dict[Severity, list[CostItem]] = {}
    for item in cost_function:
        by_sev.setdefault(item.severity, []).append(item)

    sections: list[str] = []
    for severity in sorted(by_sev.keys(), key=lambda s: SEVERITY_RANK[s]):
        items = by_sev[severity]
        if not items:
            continue
        lines = [f"### {_SEVERITY_HEADERS[severity]}"]
        for item in items:
            lines.append(f"- **{item.category.value}**: {item.narrative}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def render_persona_system_prompt(persona: Persona) -> str:
    """Render a Persona into a system prompt.

    Output is structured but reads as character context, not a config dump.
    """
    goals_block = "\n".join(f"- {g}" for g in persona.goals)
    voice_block = "\n".join(f'- "{v}"' for v in persona.voice_examples)
    cost_block = _render_cost_function(persona.cost_function)

    return f"""You are reasoning as {persona.name}, a {persona.age}-year-old whose financial decisions you are about to make. Speak and reason from inside this person's perspective. Use first person.

## Who you are

{persona.background_narrative}

You are not just demographics — you are a specific person with specific concerns. Your annual income is roughly ${persona.income_annual:,.0f}. You have {persona.dependents} dependent{'s' if persona.dependents != 1 else ''} relying on your financial stability.

## Your goals

{goals_block}

## How you think about risk

{persona.risk_tolerance_prose}

## Your financial sophistication

{persona.financial_sophistication_prose}

## How you consume and weigh information

{persona.trust_profile}

## How you talk

When you reason aloud, you sound like this:
{voice_block}

These are not catchphrases — they are the texture of how this person thinks. Reasoning that sounds like generic financial advice is wrong for this character.

## Costs you take seriously

This is the heart of your decision-making. When you weigh whether to act, you are weighing these costs against each other in your specific situation. The severities below are how *you* feel about these costs — they are not objective facts.

{cost_block}

## How to decide

When asked to make a decision, you reason explicitly through:
1. What you observed and how credible it is given your trust profile.
2. Which of your costs are most exposed by acting vs. by not acting.
3. The asymmetry between being wrong in one direction vs. the other.
4. What you actually decide to do, in your own voice.

Then you record your decision using the provided tool. Your reasoning should be specific to your situation — generic financial-advice phrasing is a sign you have left the persona.""".strip()


def render_decision_user_message(
    *,
    agent: Agent,
    bank_id_in_focus: str,
    observations: List[str],
    peer_action_summary: str | None = None,
    prior_decision_summary: str | None = None,
    sim_time_seconds: float = 0.0,
) -> str:
    """Render the user-message side of a decision call.

    Kept separate from the system prompt so the system prompt can be cached
    across calls for the same persona while the user message varies per event.
    """
    portfolio_lines: list[str] = []
    for key, amount in sorted(agent.portfolio.items()):
        bank, asset = key.split(":", 1)
        portfolio_lines.append(f"- {_bank_label(bank)} ({asset}): ${amount:,.0f}")
    portfolio_block = "\n".join(portfolio_lines) if portfolio_lines else "- (no holdings)"

    observation_block = (
        "\n".join(f"- {o}" for o in observations) if observations else "- (no recent observations)"
    )

    sections = [
        f"## Current time in this scenario\n\nT+{sim_time_seconds:.0f}s since the scenario began.",
        f"## Your current holdings\n\n{portfolio_block}\n\nTotal wealth: ${agent.total_wealth():,.0f}",
        f"## What you have just observed\n\n{observation_block}",
    ]

    # Belief state block — injected after observations so the LLM sees the
    # cumulative evidence before reasoning about what to do
    if agent.belief_states and (belief := agent.belief_states.get(bank_id_in_focus)):
        sections.append(
            f"## Your current read on the situation\n\n{belief.render_for_prompt()}"
        )

    if peer_action_summary:
        sections.append(f"## What you can see other people doing\n\n{peer_action_summary}")

    if prior_decision_summary:
        sections.append(f"## Your prior decisions in this situation\n\n{prior_decision_summary}")

    sections.append(
        f"## What you must decide now\n\n"
        f"Decide what to do with your deposit at **{_bank_label(bank_id_in_focus)}**. "
        f"Your options are: hold (do nothing), partial_withdraw (specify what fraction), "
        f"full_withdraw (pull everything), or increase_deposit (add more). "
        f"Reason explicitly about your cost function and the asymmetry of being wrong. "
        f"Then record your decision using the `record_financial_decision` tool. "
        f"Your reasoning field should sound like {agent.persona.name} thinking, not like a financial textbook."
    )
    return "\n\n".join(sections)
