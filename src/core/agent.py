"""
Agent, Persona, OutcomeLedger.

Agents do not have methods that compute decisions. Decisions happen through the
`decide` function in `src.decisions.decision`, which takes an Agent and a context
and returns a structured action. This separation lets us swap decision strategies
without changing the agent shape.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.belief import BeliefState


# ---------------------------------------------------------------------------
# Persona: the heterogeneity layer
# ---------------------------------------------------------------------------


class CostCategory(str, Enum):
    PRINCIPAL_LOSS = "principal_loss"
    WITHDRAWAL_FEES = "withdrawal_fees"
    LOCKED_IN_LOSS = "locked_in_loss"
    MISSED_UPSIDE = "missed_upside"
    CASH_FLOW_DISRUPTION = "cash_flow_disruption"
    REPUTATIONAL_DAMAGE = "reputational_damage"
    ACTION_INACTION_ASYMMETRY = "action_inaction_asymmetry"


class Severity(str, Enum):
    CATASTROPHIC = "catastrophic"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINOR = "minor"
    IRRELEVANT = "irrelevant"


SEVERITY_RANK: Dict[Severity, int] = {
    Severity.CATASTROPHIC: 0,
    Severity.SIGNIFICANT: 1,
    Severity.MODERATE: 2,
    Severity.MINOR: 3,
    Severity.IRRELEVANT: 4,
}


@dataclass
class CostItem:
    """One row of the persona's cost function.

    severity is qualitative on purpose — quantitative thresholds would let the
    LLM compare numbers instead of weighing tradeoffs. The narrative grounds the
    severity in a specific, plausible reason so the model has texture to reason with.
    """

    category: CostCategory
    severity: Severity
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "narrative": self.narrative,
        }


@dataclass
class Persona:
    archetype: str  # cautious_retiree | aggressive_trader | gig_worker | institutional_treasurer
    name: str
    age: int
    income_annual: float
    dependents: int
    risk_tolerance_score: float           # 0-1, also rendered as prose
    risk_tolerance_prose: str
    financial_sophistication_score: float # 0-1, also rendered as prose
    financial_sophistication_prose: str
    goals: List[str]
    trust_profile: str                    # how they consume + weigh information
    voice_examples: List[str]             # 2-3 example phrases as style anchors
    cost_function: List[CostItem]
    background_narrative: str             # 2-3 sentences of biography

    # Persona-level threshold for re-deciding when peers act. Higher = harder
    # to spook (institutional treasurers > retirees > gig workers).
    peer_action_reconsideration_threshold: float = 0.3

    # ---- new fields added in architecture revamp ----
    # Starting trust in institutions (used to seed BeliefState.trouble_probability)
    institution_trust_prior: float = 0.5
    # Base deliberation time in seconds (AI speed uses small jitter; human speed scales this)
    deliberation_seconds: float = 20.0
    # Which source_type strings this persona can receive (empty = no filter / all)
    information_access: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype": self.archetype,
            "name": self.name,
            "age": self.age,
            "income_annual": self.income_annual,
            "dependents": self.dependents,
            "risk_tolerance_score": self.risk_tolerance_score,
            "risk_tolerance_prose": self.risk_tolerance_prose,
            "financial_sophistication_score": self.financial_sophistication_score,
            "financial_sophistication_prose": self.financial_sophistication_prose,
            "goals": list(self.goals),
            "trust_profile": self.trust_profile,
            "voice_examples": list(self.voice_examples),
            "cost_function": [c.to_dict() for c in self.cost_function],
            "background_narrative": self.background_narrative,
            "peer_action_reconsideration_threshold": self.peer_action_reconsideration_threshold,
            "institution_trust_prior": self.institution_trust_prior,
            "deliberation_seconds": self.deliberation_seconds,
            "information_access": list(self.information_access),
        }


# ---------------------------------------------------------------------------
# OutcomeLedger: per-agent outcome tracking, populated deterministically
# ---------------------------------------------------------------------------


class OutcomeTag(str, Enum):
    AVOIDED_CRISIS = "avoided_crisis"
    PANICKED_UNNECESSARILY = "panicked_unnecessarily"
    IGNORED_REAL_WARNING = "ignored_real_warning"
    ACTED_APPROPRIATELY = "acted_appropriately"
    PARTIAL_RESPONSE = "partial_response"


@dataclass
class RealizedCost:
    timestamp: float
    cost_category: CostCategory
    amount: float
    decision_event_id: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cost_category": self.cost_category.value,
            "amount": self.amount,
            "decision_event_id": self.decision_event_id,
            "description": self.description,
        }


@dataclass
class UnrealizedOutcome:
    timestamp: float
    decision_event_id: str
    outcome_type: str  # "would_have_lost" | "would_have_gained"
    amount: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OutcomeLedger:
    agent_id: str
    principal_starting_value: float
    principal_current_value: float
    realized_costs: List[RealizedCost] = field(default_factory=list)
    unrealized_outcomes: List[UnrealizedOutcome] = field(default_factory=list)
    outcome_tags: List[OutcomeTag] = field(default_factory=list)

    def net_principal_change(self) -> float:
        return self.principal_current_value - self.principal_starting_value

    def total_realized_cost(self) -> float:
        return sum(c.amount for c in self.realized_costs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "principal_starting_value": self.principal_starting_value,
            "principal_current_value": self.principal_current_value,
            "realized_costs": [c.to_dict() for c in self.realized_costs],
            "unrealized_outcomes": [u.to_dict() for u in self.unrealized_outcomes],
            "outcome_tags": [t.value for t in self.outcome_tags],
            "net_principal_change": self.net_principal_change(),
            "total_realized_cost": self.total_realized_cost(),
        }


# ---------------------------------------------------------------------------
# DecisionRecord: full audit row for a single LLM-driven decision
# ---------------------------------------------------------------------------


@dataclass
class DecisionRecord:
    """The full audit row written for every decision."""

    decision_id: str
    agent_id: str
    timestamp: float
    trigger_reason: str
    action: str
    bank_id: str
    amount_fraction: Optional[float]
    reasoning: str
    confidence: float
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    cache_hit: bool
    system_prompt: str
    user_message: str
    raw_tool_input: Dict[str, Any]
    portfolio_snapshot: Dict[str, float]
    observation_summary: List[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class AgentState(str, Enum):
    ACTIVE = "active"           # not yet decided
    HAS_DECIDED = "has_decided" # decided but did not fully exit
    WITHDRAWN = "withdrawn"     # fully exited (no remaining deposit at target bank)


@dataclass
class Agent:
    """An agent. Decisions are NOT methods on this class — see decisions/decision.py."""

    agent_id: str
    persona: Persona
    # portfolio keys are "<bank_id>:<asset_type>", values are USD.
    # Asset types in v1: "deposit". v2 may add others (illiquid_investment, etc.).
    portfolio: Dict[str, float]
    subscriptions: List[str] = field(default_factory=list)  # feed names
    decision_history: List[DecisionRecord] = field(default_factory=list)
    state: AgentState = AgentState.ACTIVE
    outcome_ledger: Optional[OutcomeLedger] = None
    # Accumulated evidence about each bank; keyed by bank_id
    belief_states: Dict[str, BeliefState] = field(default_factory=dict)

    def total_wealth(self) -> float:
        return sum(self.portfolio.values())

    def deposit_at_bank(self, bank_id: str) -> float:
        return sum(v for k, v in self.portfolio.items() if k.startswith(f"{bank_id}:"))

    def deposit_key(self, bank_id: str, asset_type: str = "deposit") -> str:
        return f"{bank_id}:{asset_type}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "persona": self.persona.to_dict(),
            "portfolio": dict(self.portfolio),
            "subscriptions": list(self.subscriptions),
            "decision_history": [d.to_dict() for d in self.decision_history],
            "state": self.state.value,
            "outcome_ledger": self.outcome_ledger.to_dict() if self.outcome_ledger else None,
            "belief_states": {k: v.to_dict() for k, v in self.belief_states.items()},
        }
