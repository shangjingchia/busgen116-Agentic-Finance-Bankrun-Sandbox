"""
The decision flow.

Inputs: an Agent, a list of observations, peer/social signals, simulation time.
Output: a DecisionRecord with full audit context, appended to the agent's
``decision_history``. The caller turns the record into an AgentActed event.

This module is the seam between persona/state (data) and LLM (compute). The
agent itself does not have a ``.decide()`` method — keeping the decision a
free function lets us swap in a deterministic baseline or a different model
without touching the agent dataclass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from src.core.agent import Agent, DecisionRecord
from src.decisions.llm_client import (
    DECISION_TOOL_SCHEMA,
    DEFAULT_HAIKU_MODEL,
    DEFAULT_SONNET_MODEL,
    LLMCallResult,
    LLMClient,
)
from src.decisions.strategies import should_use_strategic_model
from src.personas.prompts import (
    render_decision_user_message,
    render_persona_system_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class DecisionContext:
    """All the per-call inputs to a decision."""

    bank_id_in_focus: str
    observations: List[str]
    sim_time_seconds: float = 0.0
    trigger_reason: str = "rumor_observed"
    peer_action_summary: Optional[str] = None
    prior_decision_summary: Optional[str] = None


def make_decision(
    agent: Agent,
    context: DecisionContext,
    *,
    llm_client: LLMClient,
    haiku_model: str = DEFAULT_HAIKU_MODEL,
    sonnet_model: str = DEFAULT_SONNET_MODEL,
    force_strategic: Optional[bool] = None,
) -> DecisionRecord:
    """Run one structured LLM-driven decision and append it to ``agent.decision_history``."""

    system_prompt = render_persona_system_prompt(agent.persona)
    user_message = render_decision_user_message(
        agent=agent,
        bank_id_in_focus=context.bank_id_in_focus,
        observations=context.observations,
        peer_action_summary=context.peer_action_summary,
        prior_decision_summary=context.prior_decision_summary,
        sim_time_seconds=context.sim_time_seconds,
    )

    # Model routing
    if force_strategic is not None:
        use_strategic = force_strategic
    else:
        use_strategic = should_use_strategic_model(
            agent, observations=context.observations
        )
    model = sonnet_model if use_strategic else haiku_model

    logger.debug(
        "Calling LLM for agent=%s bank=%s model=%s trigger=%s",
        agent.agent_id,
        context.bank_id_in_focus,
        model,
        context.trigger_reason,
    )

    result: LLMCallResult = llm_client.decide(
        system_prompt=system_prompt,
        user_message=user_message,
        model=model,
    )

    record = DecisionRecord(
        decision_id=DecisionRecord.new_id(),
        agent_id=agent.agent_id,
        timestamp=context.sim_time_seconds,
        trigger_reason=context.trigger_reason,
        action=result.tool_input["action"],
        bank_id=context.bank_id_in_focus,
        amount_fraction=float(result.tool_input["amount_fraction"]),
        reasoning=result.tool_input["reasoning"],
        confidence=float(result.tool_input["confidence"]),
        model_used=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        cost_usd=result.cost_usd,
        cache_hit=result.cache_hit,
        system_prompt=system_prompt,
        user_message=user_message,
        raw_tool_input=dict(result.tool_input),
        portfolio_snapshot=dict(agent.portfolio),
        observation_summary=(
            list(context.observations)
            + ([f"Peer context: {context.peer_action_summary}"] if context.peer_action_summary else [])
        ),
    )
    agent.decision_history.append(record)
    return record
