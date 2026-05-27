"""
Generate a Persona from a natural language description via LLM.

The LLM picks the closest-fit archetype and generates all persona prose from
scratch. The archetype's pre-written cost function is attached unchanged — this
keeps cost functions well-calibrated while letting everything else be freeform.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.core.agent import Agent, AgentState, OutcomeLedger, Persona
from src.personas.archetypes import ALL_ARCHETYPES, get_archetype_cost_function

PERSONA_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "define_agent_persona",
        "description": (
            "Define a complete agent persona for a bank-run simulation. "
            "Every field must be specific to this exact person — not generic archetype prose."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "archetype": {
                    "type": "string",
                    "enum": list(ALL_ARCHETYPES),
                    "description": (
                        "Best-fit archetype. "
                        "cautious_retiree: capital preservation above all, no recovery runway. "
                        "aggressive_trader: fears missing upside more than losing principal. "
                        "gig_worker: precarity-driven, every dollar matters, trusts social network. "
                        "institutional_treasurer: fiduciary duty, acts on verified sources only."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": "A short role label or real-sounding name (e.g. 'Nervous Retiree' or 'Sophie Park'). Under 25 chars.",
                },
                "age": {"type": "integer", "minimum": 18, "maximum": 85},
                "income_annual": {"type": "number", "description": "Annual income in USD."},
                "dependents": {"type": "integer", "minimum": 0, "maximum": 10},
                "risk_tolerance_score": {
                    "type": "number", "minimum": 0.0, "maximum": 1.0,
                    "description": "0 = will never risk principal; 1 = maximises risk for return.",
                },
                "financial_sophistication_score": {
                    "type": "number", "minimum": 0.0, "maximum": 1.0,
                    "description": "0 = no financial literacy; 1 = professional-grade analysis.",
                },
                "background_narrative": {
                    "type": "string",
                    "description": (
                        "3-5 sentences of concrete biography. Include specific amounts, dates, "
                        "obligations, and what makes this person financially unique. "
                        "This is what the LLM reads when making decisions — make it vivid."
                    ),
                },
                "risk_tolerance_prose": {
                    "type": "string",
                    "description": "2-3 sentences describing how THIS person thinks about risk — in their specific voice, not generic archetype language.",
                },
                "financial_sophistication_prose": {
                    "type": "string",
                    "description": "2-3 sentences describing their actual financial knowledge and how they get information.",
                },
                "goals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 4,
                    "description": "2-4 concrete financial goals, specific to this person.",
                },
                "trust_profile": {
                    "type": "string",
                    "description": "2-3 sentences: what sources do they trust, how do they react to rumours, what makes them act vs wait?",
                },
                "voice_examples": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "3 short quotes in this person's voice — how they'd actually talk about a money decision. Should be unmistakably this person.",
                },
                "peer_action_reconsideration_threshold": {
                    "type": "number", "minimum": 0.1, "maximum": 0.6,
                    "description": (
                        "Fraction of peers who must act before this person reconsiders. "
                        "Low (0.10-0.20) for easily-swayed people; high (0.40-0.60) for skeptics."
                    ),
                },
            },
            "required": [
                "archetype", "name", "age", "income_annual", "dependents",
                "risk_tolerance_score", "financial_sophistication_score",
                "background_narrative", "risk_tolerance_prose",
                "financial_sophistication_prose", "goals", "trust_profile",
                "voice_examples", "peer_action_reconsideration_threshold",
            ],
        },
    },
}

_SYSTEM_PROMPT = """\
You are creating agent personas for a bank-run simulation. Each agent holds deposits
at a bank and will make AI-powered financial decisions when a rumour circulates that
the bank is in trouble.

Your job: take a user description and generate a persona that is specific, concrete,
and would produce genuinely distinctive reasoning. Generic prose ("she is risk-averse")
is bad. Specific prose ("she watched her neighbour lose a CD in the IndyMac failure and
still can't talk about it") is good.

The archetype you pick determines the agent's core cost function (the weights it assigns
to different kinds of financial loss). Pick the archetype that best fits the person's
actual situation and psychology — not just their job title.

Write everything in present tense, second person ("You are...", "You believe...").
The text will be read by the LLM as the agent's self-description during a decision.
"""


def generate_persona(description: str, client: Any) -> Tuple[Persona, float]:
    """
    Make one LLM call to generate a Persona from a natural language description.
    Returns (persona, cost_usd).

    `client` is an LLMClient instance from src.decisions.llm_client.
    """
    result = client.decide(
        system_prompt=_SYSTEM_PROMPT,
        user_message=(
            f"Create a persona for this person:\n\n{description.strip()}\n\n"
            "Make every field specific and vivid. Use second-person present tense."
        ),
        model="anthropic/claude-sonnet-4.5",
        max_tokens=2000,
        tool_schema=PERSONA_TOOL_SCHEMA,
        force_tool=True,
        tool_validator=_validate_persona_tool_input,
    )

    ti = result.tool_input
    cost_fn = get_archetype_cost_function(ti["archetype"])

    persona = Persona(
        archetype=ti["archetype"],
        name=ti["name"],
        age=ti["age"],
        income_annual=ti["income_annual"],
        dependents=ti["dependents"],
        risk_tolerance_score=float(ti["risk_tolerance_score"]),
        risk_tolerance_prose=ti["risk_tolerance_prose"],
        financial_sophistication_score=float(ti["financial_sophistication_score"]),
        financial_sophistication_prose=ti["financial_sophistication_prose"],
        goals=list(ti["goals"]),
        trust_profile=ti["trust_profile"],
        voice_examples=list(ti["voice_examples"]),
        cost_function=cost_fn,
        background_narrative=ti["background_narrative"],
        peer_action_reconsideration_threshold=float(ti["peer_action_reconsideration_threshold"]),
    )
    return persona, result.cost_usd


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def persona_to_save_dict(
    persona: Persona,
    *,
    description_input: str,
    deposit_bank_a: float,
    deposit_bank_b: float,
) -> Dict[str, Any]:
    """Produce the dict saved to custom_personas/<id>.json."""
    p_dict = persona.to_dict()
    p_dict.pop("cost_function", None)  # reconstructed from archetype on load
    return {
        "persona_id": f"custom_{uuid.uuid4().hex[:8]}",
        "description_input": description_input,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deposit_bank_a": deposit_bank_a,
        "deposit_bank_b": deposit_bank_b,
        "persona": p_dict,
    }


def load_agent_from_dict(data: Dict[str, Any], agent_id: Optional[str] = None) -> Agent:
    """Reconstruct an Agent from a saved custom persona dict."""
    p = data["persona"]
    cost_fn = get_archetype_cost_function(p["archetype"])
    persona = Persona(
        archetype=p["archetype"],
        name=p["name"],
        age=p["age"],
        income_annual=p["income_annual"],
        dependents=p["dependents"],
        risk_tolerance_score=p["risk_tolerance_score"],
        risk_tolerance_prose=p["risk_tolerance_prose"],
        financial_sophistication_score=p["financial_sophistication_score"],
        financial_sophistication_prose=p["financial_sophistication_prose"],
        goals=list(p["goals"]),
        trust_profile=p["trust_profile"],
        voice_examples=list(p["voice_examples"]),
        cost_function=cost_fn,
        background_narrative=p["background_narrative"],
        peer_action_reconsideration_threshold=p.get("peer_action_reconsideration_threshold", 0.3),
    )
    aid = agent_id or data.get("persona_id", f"custom_{uuid.uuid4().hex[:8]}")
    deposit_a = float(data.get("deposit_bank_a", 20_000))
    deposit_b = float(data.get("deposit_bank_b", 5_000))
    starting_wealth = deposit_a + deposit_b
    return Agent(
        agent_id=aid,
        persona=persona,
        portfolio={"bank_a:deposit": deposit_a, "bank_b:deposit": deposit_b},
        subscriptions=["news_feed", "social_feed"],
        state=AgentState.ACTIVE,
        outcome_ledger=OutcomeLedger(
            agent_id=aid,
            principal_starting_value=starting_wealth,
            principal_current_value=starting_wealth,
        ),
    )


def load_all_saved(custom_personas_dir: Path) -> list[Dict[str, Any]]:
    """Return list of saved persona dicts, sorted newest first."""
    if not custom_personas_dir.exists():
        return []
    results = []
    for p in sorted(custom_personas_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            results.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return results


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_persona_tool_input(ti: Dict[str, Any]) -> Dict[str, Any]:
    required = {
        "archetype", "name", "age", "income_annual", "dependents",
        "risk_tolerance_score", "financial_sophistication_score",
        "background_narrative", "risk_tolerance_prose",
        "financial_sophistication_prose", "goals", "trust_profile",
        "voice_examples", "peer_action_reconsideration_threshold",
    }
    missing = required - set(ti.keys())
    if missing:
        raise ValueError(f"Persona tool input missing fields: {missing}")
    if ti["archetype"] not in ALL_ARCHETYPES:
        raise ValueError(f"Unknown archetype: {ti['archetype']!r}")
    if not (0.0 <= float(ti["risk_tolerance_score"]) <= 1.0):
        raise ValueError("risk_tolerance_score out of range")
    if not (0.0 <= float(ti["financial_sophistication_score"]) <= 1.0):
        raise ValueError("financial_sophistication_score out of range")
    if len(ti.get("voice_examples", [])) < 3:
        raise ValueError("Need at least 3 voice_examples")
    if len(ti.get("goals", [])) < 2:
        raise ValueError("Need at least 2 goals")
    return ti
