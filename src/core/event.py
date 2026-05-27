"""
Event types for the simulation.

Every state change in the simulation happens via an Event. The engine processes
events in timestamp order and fires handlers; handlers may emit new events. This
is the abstraction that keeps the v2 path clean — adding a new scenario type
means adding a new event type, not a new code path through the engine.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, List, Optional


class EventType(str, Enum):
    SIMULATION_STARTED = "simulation_started"
    SIMULATION_ENDED = "simulation_ended"
    RUMOR_PUBLISHED = "rumor_published"
    INFORMATION_SIGNAL_PUBLISHED = "information_signal_published"
    AGENT_OBSERVED = "agent_observed"
    AGENT_DECISION_TRIGGERED = "agent_decision_triggered"
    AGENT_ACTED = "agent_acted"
    WITHDRAWAL_PROCESSED = "withdrawal_processed"
    BANK_RESERVE_UPDATED = "bank_reserve_updated"
    SOCIAL_SIGNAL_EMITTED = "social_signal_emitted"
    RUMOR_TRUTH_REVEALED = "rumor_truth_revealed"
    CENTRAL_BANK_TRIGGERED = "central_bank_triggered"
    CENTRAL_BANK_ACTED = "central_bank_acted"
    POLICY_ANNOUNCED = "policy_announced"


@dataclass
class Event:
    """Base event. timestamp is simulation seconds from t=0."""

    event_type: EventType
    timestamp: float
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __lt__(self, other: "Event") -> bool:
        # heapq orders by timestamp; tiebreak on event_id for determinism
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        return self.event_id < other.event_id

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d


@dataclass
class RumorPublished(Event):
    """A piece of information enters the environment."""

    content: str = ""
    source: str = ""               # e.g. "twitter", "financial_news_outlet", "direct_message"
    credibility: float = 0.5       # 0-1, how credible the source itself is
    bank_id: str = ""              # which bank the rumor is about
    target_agent_ids: List[str] = field(default_factory=list)  # empty = broadcast


@dataclass
class AgentObserved(Event):
    """A specific agent observes a specific event after some latency."""

    agent_id: str = ""
    observed_event_id: str = ""
    observation_latency: float = 0.0


@dataclass
class AgentDecisionTriggered(Event):
    agent_id: str = ""
    trigger_reason: str = ""       # "rumor_observed" | "peer_withdrawal" | "periodic_review"
    triggering_event_id: Optional[str] = None
    bank_id: str = ""              # which bank the decision focuses on


@dataclass
class AgentActed(Event):
    """The agent has executed an action. Reasoning + cost are recorded for audit."""

    agent_id: str = ""
    action: str = ""                          # hold | partial_withdraw | full_withdraw | increase_deposit
    bank_id: str = ""                         # which bank the action targets
    amount_fraction: Optional[float] = None   # for partial_withdraw / increase_deposit
    reasoning: str = ""
    confidence: float = 0.0
    decision_record_id: Optional[str] = None  # link to full DecisionRecord JSON
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class WithdrawalProcessed(Event):
    agent_id: str = ""
    bank_id: str = ""
    amount_requested: float = 0.0
    amount_paid_out: float = 0.0
    fee_paid: float = 0.0
    was_queued: bool = False


@dataclass
class BankReserveUpdated(Event):
    bank_id: str = ""
    new_reserves: float = 0.0
    new_reserve_ratio: float = 0.0
    new_state: str = "healthy"


@dataclass
class InformationSignalPublished(Event):
    """A structured InformationSignal enters the simulation environment."""

    signal_id: str = ""
    source_type: str = ""
    alarm_level: float = 0.0
    base_credibility: float = 0.5
    content: str = ""
    target_bank_id: str = ""
    propagation_latency_seconds: float = 3.0
    # serialized archetype_credibility_multipliers and visible_to_archetypes stored
    # on the originating InformationSignal; pass signal_id for handlers to look up.


@dataclass
class SocialSignalEmitted(Event):
    """Published when an agent acts and the action is visible on the social feed."""

    source_agent_id: str = ""
    source_agent_name: str = ""        # human-readable name for observation rendering
    source_archetype: str = ""         # archetype tag for peer-matching
    action_event_id: str = ""
    action: str = ""
    bank_id: str = ""
    reasoning_snippet: str = ""        # first ~80 chars of the agent's reasoning
    visibility: float = 1.0  # fraction of subscribed agents who actually receive it


@dataclass
class RumorTruthRevealed(Event):
    """At simulation end: was the rumor actually true? Used by the OutcomeLedger."""

    bank_id: str = ""
    rumor_was_true: bool = False
    revealed_reserve_ratio: float = 0.0


@dataclass
class CentralBankTriggered(Event):
    """The cascade crossed the CB trigger threshold — a CB decision is now pending."""

    bank_id: str = ""
    cascade_fraction: float = 0.0       # fraction of agents fully withdrawn at trigger time
    bank_reserve_ratio: float = 0.0
    bank_state: str = "healthy"
    withdrawn_count: int = 0
    total_agents: int = 0


@dataclass
class CentralBankActed(Event):
    """The CB has executed a policy intervention."""

    action: str = ""                    # "do_nothing" | "announce_guarantee" | "inject_liquidity"
    bank_id: str = ""
    reasoning: str = ""
    announcement_text: str = ""         # for announce_guarantee
    liquidity_amount: float = 0.0       # USD injected, for inject_liquidity
    confidence: float = 0.0
    policy_type: str = "llm"            # "llm" | "rule_based"
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class PolicyAnnounced(Event):
    """A CB policy announcement broadcast to all agents via the news feed."""

    bank_id: str = ""
    announcement_text: str = ""
    source: str = "central_bank"
    cb_action_event_id: str = ""        # links back to the CentralBankActed event
