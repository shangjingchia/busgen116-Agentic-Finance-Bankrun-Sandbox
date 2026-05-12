"""
Cheap-vs-strategic model routing.

Sonnet is used when the decision warrants deeper reasoning:
  - Large portfolio (≥ $200k): institutional treasurers and wealthy retirees
    face high-stakes fiduciary decisions on every call.
  - Conflicting information: when the signal environment is ambiguous, any
    agent benefits from more careful reasoning.

Haiku is used for small-portfolio retail agents (gig workers, typical retirees).
Their reasoning is faster and cheaper — and should read differently in the
Inspect view, which is the point.

The old "first decision → Sonnet for everyone" rule was removed. It blurred
the distinction between archetypes: a gig worker's first-call reasoning looked
as sophisticated as an institutional treasurer's, which is unrealistic.
"""

from __future__ import annotations

from typing import List, Optional

from src.core.agent import Agent

# Agents with total wealth above this threshold always use Sonnet.
LARGE_PORTFOLIO_USD = 200_000.0


def should_use_strategic_model(
    agent: Agent,
    *,
    observations: List[str],
    prior_decision_count: Optional[int] = None,
) -> bool:
    """Return True iff this decision warrants Sonnet rather than Haiku."""
    # Conflicting information: any agent benefits from deeper reasoning when
    # the signal environment sends mixed messages.
    if _looks_conflicting(observations):
        return True

    # Large portfolio: institutional treasurers, wealthy retirees.
    # These agents use Sonnet on every decision, not just the first.
    if agent.total_wealth() >= LARGE_PORTFOLIO_USD:
        return True

    return False


def _looks_conflicting(observations: List[str]) -> bool:
    if len(observations) < 2:
        return False
    text = " ".join(observations).lower()
    alarm_terms = ("insolvent", "panic", "withdraw", "run", "freeze", "distressed")
    reassure_terms = ("denies", "denied", "reassures", "stable", "no concern", "false")
    has_alarm = any(t in text for t in alarm_terms)
    has_reassure = any(t in text for t in reassure_terms)
    return has_alarm and has_reassure
