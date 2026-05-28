"""
Event-driven simulation engine.

Architecture:
  - heapq event queue ordered by (timestamp, event_id).
  - Main loop drains all events at the same simulation timestamp per iteration.
  - Non-decision events are handled synchronously (may enqueue more events).
  - AgentDecisionTriggered events are handled via asyncio.gather so that
    multiple decisions at the same sim-time execute LLM calls in parallel.
  - LLM calls are blocking-I/O; asyncio.to_thread runs them in a thread pool
    so the event loop is not blocked.

Speed control:
  ScenarioSpeed.AI_SPEED   -> decision fires at observation timestamp (no delay)
  ScenarioSpeed.HUMAN_SPEED -> decision fires at observation + human_delay seconds

Entry points:
  run_scenario(...)       async convenience wrapper used by dashboard and CLI.
  SimulationEngine.run()  lower-level async method on the engine class.
"""

from __future__ import annotations

import argparse
import asyncio
import heapq
import json
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.core.agent import (
    Agent,
    AgentState,
    CostCategory,
    OutcomeTag,
    RealizedCost,
    UnrealizedOutcome,
)
from src.core.bank import Bank
from src.core.belief import BeliefState
from src.core.event import (
    AgentActed,
    AgentDecisionTriggered,
    AgentObserved,
    BankReserveUpdated,
    CentralBankActed,
    CentralBankTriggered,
    Event,
    EventType,
    InformationSignalPublished,
    PolicyAnnounced,
    RumorPublished,
    RumorTruthRevealed,
    SocialSignalEmitted,
    WithdrawalProcessed,
)
from src.core.scenario import (
    AgentPopulationGroup,
    BankConfig,
    RumorConfig,
    Scenario,
    ScenarioSpeed,
)
from src.decisions.decision import DecisionContext, make_decision
from src.decisions.llm_client import LLMClient
from src.information.feed import Feed
from src.information.observation import (
    render_policy_observation,
    render_rumor_observation,
    render_signal_observation,
    render_social_observation,
)
from src.information.rumor import rumor_config_to_event

logger = logging.getLogger(__name__)

# Social cascade re-decision tiers are personalized from each persona's first
# reconsideration threshold. Offsets allow at most three re-decisions as peer
# pressure grows without flattening every archetype into the same response curve.
_RETRIGGER_TIER_OFFSETS = (0.0, 0.20, 0.45)
_CASH_KEY = "cash:available"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class RunMetrics:
    total_agents: int
    withdrawn_count: int
    partially_withdrawn_count: int
    held_count: int
    time_to_first_withdrawal: Optional[float]
    time_to_50pct_withdrawn: Optional[float]
    final_withdrawal_fraction: float  # fraction of Bank A deposits withdrawn
    attempted_exit_count: int
    paid_out_count: int
    time_to_50pct_deposits_paid: Optional[float]
    bank_suspension_time: Optional[float]
    cascade_triggered: bool
    total_events: int
    total_llm_calls: int
    total_cost_usd: float
    cb_policy_type: Optional[str] = None   # "llm" | "rule_based" | None
    cb_action: Optional[str] = None        # action taken by the CB
    cb_triggered_at: Optional[float] = None  # simulation time when CB was triggered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_agents": self.total_agents,
            "withdrawn_count": self.withdrawn_count,
            "partially_withdrawn_count": self.partially_withdrawn_count,
            "held_count": self.held_count,
            "time_to_first_withdrawal": self.time_to_first_withdrawal,
            "time_to_50pct_withdrawn": self.time_to_50pct_withdrawn,
            "final_withdrawal_fraction": self.final_withdrawal_fraction,
            "attempted_exit_count": self.attempted_exit_count,
            "paid_out_count": self.paid_out_count,
            "time_to_50pct_deposits_paid": self.time_to_50pct_deposits_paid,
            "bank_suspension_time": self.bank_suspension_time,
            "cascade_triggered": self.cascade_triggered,
            "total_events": self.total_events,
            "total_llm_calls": self.total_llm_calls,
            "total_cost_usd": self.total_cost_usd,
            "cb_policy_type": self.cb_policy_type,
            "cb_action": self.cb_action,
            "cb_triggered_at": self.cb_triggered_at,
        }


@dataclass
class RunResult:
    run_id: str
    scenario_id: str
    scenario_name: str
    scenario_description: str
    speed: str
    seed: int
    events: List[Dict[str, Any]]
    agent_final_states: List[Dict[str, Any]]
    bank_final_states: List[Dict[str, Any]]
    metrics: RunMetrics
    llm_summary: Dict[str, Any]
    started_at: str
    completed_at: str
    duration_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "scenario_description": self.scenario_description,
            "speed": self.speed,
            "seed": self.seed,
            "events": self.events,
            "agent_final_states": self.agent_final_states,
            "bank_final_states": self.bank_final_states,
            "metrics": self.metrics.to_dict(),
            "llm_summary": self.llm_summary,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
        }

    def save(self, runs_dir: Path) -> Path:
        runs_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.fromisoformat(self.started_at).strftime("%Y%m%d_%H%M%S")
        path = runs_dir / f"{self.scenario_id}_{self.speed}_{ts}.json"
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SimulationEngine:
    """Event-driven simulation engine. Instantiate once per run."""

    def __init__(
        self,
        scenario: Scenario,
        agents: List[Agent],
        banks: Dict[str, Bank],
        llm_client: LLMClient,
    ) -> None:
        self._scenario = scenario
        self._agents: Dict[str, Agent] = {a.agent_id: a for a in agents}
        self._banks = banks
        self._llm_client = llm_client
        self._rng = random.Random(scenario.seed)

        # Event queue (heapq)
        self._queue: List[Event] = []
        self._event_log: List[Event] = []
        # All logged events indexed by ID for observation lookups
        self._event_by_id: Dict[str, Event] = {}

        # Per-agent pending observation strings (consumed on decision trigger)
        self._pending_obs: Dict[str, List[str]] = {a.agent_id: [] for a in agents}

        # Per-agent social signal accumulation
        self._social_count: Dict[str, int] = {a.agent_id: 0 for a in agents}
        self._social_details: Dict[str, List[str]] = {a.agent_id: [] for a in agents}
        # Tiered re-decision: tracks how many threshold tiers each agent has crossed.
        # Tiers fire at 15%, 35%, 60% of peers withdrawing — at most 3 re-decisions total.
        self._re_decided_tier: Dict[str, int] = {a.agent_id: 0 for a in agents}

        # Outcome tracking
        self._first_withdrawal_time: Optional[float] = None
        self._time_to_50pct: Optional[float] = None
        self._time_to_50pct_deposits_paid: Optional[float] = None
        self._bank_suspension_time: Optional[float] = None
        self._withdrawn_agents: Set[str] = set()
        self._partially_withdrawn_agents: Set[str] = set()
        self._attempted_exit_agents: Set[str] = set()
        self._paid_out_agents: Set[str] = set()

        # Initial deposit totals per bank (for withdrawal-fraction metric)
        self._initial_deposits: Dict[str, float] = {
            bc.bank_id: sum(
                v
                for a in agents
                for k, v in a.portfolio.items()
                if k.startswith(bc.bank_id + ":")
            )
            for bc in scenario.banks
        }

        self._feed = Feed(scenario=scenario, agents=agents, rng=self._rng)

        # Initialize per-agent belief states from each persona's trust prior
        for agent in agents:
            trust_prior = getattr(agent.persona, "institution_trust_prior", 0.5)
            for bc in scenario.banks:
                if any(k.startswith(bc.bank_id + ":") for k in agent.portfolio):
                    agent.belief_states[bc.bank_id] = BeliefState.initial(
                        bc.bank_id, trust_prior
                    )

        # Central Bank agent (optional)
        self._cb_triggered: bool = False
        self._cb_agent = None
        self._cb_initial_reserves: Dict[str, float] = {bid: b.reserves for bid, b in banks.items()}
        self._cb_policy_type: Optional[str] = None
        self._cb_action: Optional[str] = None
        self._cb_triggered_at: Optional[float] = None
        if scenario.central_bank is not None:
            from src.core.central_bank import CentralBankAgent
            self._cb_agent = CentralBankAgent(scenario.central_bank, llm_client)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> RunResult:
        started_at = datetime.now(timezone.utc)
        t0 = asyncio.get_event_loop().time()

        # Seed the queue with legacy rumor events
        for rumor_config in self._scenario.rumors:
            self._schedule(rumor_config_to_event(rumor_config))

        # Seed the queue with InformationSignal events (new signal stream)
        for signal in self._scenario.signals:
            pub = InformationSignalPublished(
                event_type=EventType.INFORMATION_SIGNAL_PUBLISHED,
                timestamp=signal.publish_at,
                signal_id=signal.signal_id,
                source_type=signal.source_type,
                alarm_level=signal.alarm_level,
                base_credibility=signal.base_credibility,
                content=signal.content,
                target_bank_id=signal.target_bank_id,
                propagation_latency_seconds=signal.propagation_latency_seconds,
            )
            self._schedule(pub)

        sim_time = 0.0

        while self._queue:
            next_time = self._queue[0].timestamp
            if next_time > self._scenario.max_simulation_time:
                break
            sim_time = next_time

            # Drain all events at this timestamp
            batch: List[Event] = []
            while self._queue and self._queue[0].timestamp == sim_time:
                batch.append(heapq.heappop(self._queue))

            decisions = [e for e in batch if isinstance(e, AgentDecisionTriggered)]
            cb_decisions = [e for e in batch if isinstance(e, CentralBankTriggered)]
            others = [e for e in batch if not isinstance(e, (AgentDecisionTriggered, CentralBankTriggered))]

            # Process non-decision events first (may push new events at same time)
            for event in others:
                self._log(event)
                for ne in self._handle_sync(event, sim_time):
                    self._schedule(ne)

            # CB decision fires before agent decisions so any CB announcement can be
            # routed to agents who haven't yet committed to a decision.
            if cb_decisions:
                for e in cb_decisions:
                    self._log(e)
                cb_lists = await asyncio.gather(
                    *[self._handle_cb_decision(e, sim_time) for e in cb_decisions]
                )
                for nl in cb_lists:
                    for ne in nl:
                        self._schedule(ne)

            # Gather all agent decision events at this timestamp in parallel
            if decisions:
                for e in decisions:
                    self._log(e)
                result_lists = await asyncio.gather(
                    *[self._handle_decision(e, sim_time) for e in decisions],
                    return_exceptions=False,
                )
                for new_events in result_lists:
                    for ne in new_events:
                        self._schedule(ne)

        self._finalize(sim_time)

        elapsed = asyncio.get_event_loop().time() - t0
        completed_at = datetime.now(timezone.utc)

        return self._build_result(
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Sync event dispatch
    # ------------------------------------------------------------------

    def _handle_sync(self, event: Event, sim_time: float) -> List[Event]:
        if isinstance(event, RumorPublished):
            return self._handle_rumor_published(event)
        elif isinstance(event, InformationSignalPublished):
            return self._handle_information_signal_published(event)
        elif isinstance(event, AgentObserved):
            return self._handle_agent_observed(event, sim_time)
        elif isinstance(event, AgentActed):
            return self._handle_agent_acted(event, sim_time)
        elif isinstance(event, SocialSignalEmitted):
            return self._handle_social_signal_emitted(event, sim_time)
        elif isinstance(event, CentralBankActed):
            return self._handle_central_bank_acted(event, sim_time)
        elif isinstance(event, PolicyAnnounced):
            return self._handle_policy_announced(event, sim_time)
        # WithdrawalProcessed and BankReserveUpdated appear in the log only.
        return []

    def _handle_rumor_published(self, event: RumorPublished) -> List[Event]:
        # Store so observers can look it up later
        self._event_by_id[event.event_id] = event
        return self._feed.route_rumor(event)

    def _handle_information_signal_published(
        self, event: InformationSignalPublished
    ) -> List[Event]:
        self._event_by_id[event.event_id] = event
        return self._feed.route_signal(event)

    def _handle_agent_observed(self, event: AgentObserved, sim_time: float) -> List[Event]:
        agent = self._agents.get(event.agent_id)
        if agent is None or agent.state == AgentState.WITHDRAWN:
            return []

        original = self._event_by_id.get(event.observed_event_id)
        if original is None:
            return []

        new_events: List[Event] = []

        if isinstance(original, RumorPublished):
            obs_str = render_rumor_observation(original)
            self._pending_obs[event.agent_id].append(obs_str)
            delay = self._decision_delay(agent)
            trigger = AgentDecisionTriggered(
                event_type=EventType.AGENT_DECISION_TRIGGERED,
                timestamp=event.timestamp + delay,
                agent_id=event.agent_id,
                trigger_reason="rumor_observed",
                triggering_event_id=event.event_id,
                bank_id=original.bank_id,
            )
            new_events.append(trigger)

        elif isinstance(original, InformationSignalPublished):
            # Look up the full InformationSignal to get archetype-aware rendering
            info_signal = self._feed._signal_map.get(original.signal_id)
            arch = agent.persona.archetype
            if info_signal is not None:
                obs_str = render_signal_observation(info_signal, arch)
                eff_cred = info_signal.effective_credibility(arch)
                # Update the agent's belief state for the target bank
                belief = agent.belief_states.get(original.target_bank_id)
                if belief is not None:
                    belief.update(info_signal.alarm_level, eff_cred)
            else:
                obs_str = f"[{original.source_type}] {original.content}"
            self._pending_obs[event.agent_id].append(obs_str)
            delay = self._decision_delay(agent)
            trigger = AgentDecisionTriggered(
                event_type=EventType.AGENT_DECISION_TRIGGERED,
                timestamp=event.timestamp + delay,
                agent_id=event.agent_id,
                trigger_reason="signal_observed",
                triggering_event_id=event.event_id,
                bank_id=original.target_bank_id,
            )
            new_events.append(trigger)

        elif isinstance(original, SocialSignalEmitted):
            observer_arch = agent.persona.archetype
            obs_str = render_social_observation(original, observer_arch)
            self._social_details[event.agent_id].append(obs_str)
            self._social_count[event.agent_id] += 1

            # Tiered re-decision: fire each time this persona crosses their
            # next social threshold.
            total_others = len(self._agents) - 1
            current_tier = self._re_decided_tier[event.agent_id]
            base_threshold = agent.persona.peer_action_reconsideration_threshold
            retrigger_tiers = tuple(
                min(0.95, base_threshold + offset)
                for offset in _RETRIGGER_TIER_OFFSETS
            )
            if (
                current_tier < len(retrigger_tiers)
                and agent.state != AgentState.WITHDRAWN
            ):
                next_frac = retrigger_tiers[current_tier]
                if self._social_count[event.agent_id] >= next_frac * max(total_others, 1):
                    self._re_decided_tier[event.agent_id] = current_tier + 1
                    delay = self._decision_delay(agent)
                    trigger = AgentDecisionTriggered(
                        event_type=EventType.AGENT_DECISION_TRIGGERED,
                        timestamp=event.timestamp + delay,
                        agent_id=event.agent_id,
                        trigger_reason="peer_withdrawal",
                        triggering_event_id=event.event_id,
                        bank_id=original.bank_id,
                    )
                    new_events.append(trigger)

        elif isinstance(original, PolicyAnnounced):
            # CB announcement: add to pending observations and trigger a re-decision
            # for agents who have not yet fully withdrawn.
            obs_str = render_policy_observation(original)
            self._pending_obs[event.agent_id].append(obs_str)
            if agent.state != AgentState.WITHDRAWN:
                delay = self._decision_delay(agent)
                trigger = AgentDecisionTriggered(
                    event_type=EventType.AGENT_DECISION_TRIGGERED,
                    timestamp=event.timestamp + delay,
                    agent_id=event.agent_id,
                    trigger_reason="policy_announced",
                    triggering_event_id=event.event_id,
                    bank_id=original.bank_id,
                )
                new_events.append(trigger)

        return new_events

    def _handle_agent_acted(self, event: AgentActed, sim_time: float) -> List[Event]:
        agent = self._agents[event.agent_id]
        new_events: List[Event] = []

        if event.action in ("hold", "increase_deposit"):
            if agent.state == AgentState.ACTIVE:
                agent.state = AgentState.HAS_DECIDED
            # Emit a low-visibility social signal so peers learn some people are staying
            reasoning_snippet = event.reasoning[:100] if event.reasoning else ""
            hold_social = SocialSignalEmitted(
                event_type=EventType.SOCIAL_SIGNAL_EMITTED,
                timestamp=event.timestamp,
                source_agent_id=agent.agent_id,
                source_agent_name=agent.persona.name,
                source_archetype=agent.persona.archetype,
                action_event_id=event.event_id,
                action=event.action,
                bank_id=event.bank_id,
                reasoning_snippet=reasoning_snippet,
                visibility=min(0.4, self._scenario.social_signal_visibility * 0.4),
            )
            new_events.append(hold_social)
            return new_events

        # Withdrawal
        deposit_key = f"{event.bank_id}:deposit"
        current_deposit = agent.portfolio.get(deposit_key, 0.0)
        if current_deposit <= 0.0:
            return new_events

        amount_requested = current_deposit * event.amount_fraction
        if amount_requested <= 0.0:
            return new_events

        bank = self._banks.get(event.bank_id)
        if bank is None:
            logger.warning("Unknown bank %s in AgentActed", event.bank_id)
            return new_events

        result = bank.process_withdrawal(
            agent.agent_id,
            amount_requested,
            timestamp=event.timestamp,
        )

        # Keep agent portfolio in sync with bank deposits
        agent.portfolio[deposit_key] = max(
            0.0, agent.portfolio.get(deposit_key, 0.0) - result.amount_debited
        )
        if result.amount_paid_out > 0:
            agent.portfolio[_CASH_KEY] = (
                agent.portfolio.get(_CASH_KEY, 0.0) + result.amount_paid_out
            )
            self._paid_out_agents.add(agent.agent_id)
        self._attempted_exit_agents.add(agent.agent_id)
        if self._first_withdrawal_time is None:
            self._first_withdrawal_time = event.timestamp

        # Record realized fee cost
        if result.fee_paid > 0 and agent.outcome_ledger is not None:
            agent.outcome_ledger.realized_costs.append(
                RealizedCost(
                    timestamp=event.timestamp,
                    cost_category=CostCategory.WITHDRAWAL_FEES,
                    amount=result.fee_paid,
                    decision_event_id=event.event_id,
                    description=(
                        f"Early withdrawal fee: ${result.fee_paid:,.2f} "
                        f"on ${result.amount_debited:,.0f} debited from {event.bank_id} "
                        f"(${amount_requested:,.0f} requested)"
                    ),
                )
            )

        # Update ledger principal value
        if agent.outcome_ledger is not None:
            agent.outcome_ledger.principal_current_value = agent.total_wealth()

        # Update agent state
        remaining = agent.portfolio.get(deposit_key, 0.0)
        if remaining <= 0.0:
            agent.state = AgentState.WITHDRAWN
            self._withdrawn_agents.add(agent.agent_id)
            frac_withdrawn = len(self._withdrawn_agents) / len(self._agents)
            if frac_withdrawn >= 0.50 and self._time_to_50pct is None:
                self._time_to_50pct = event.timestamp
        else:
            agent.state = AgentState.HAS_DECIDED
            self._partially_withdrawn_agents.add(agent.agent_id)

        focus_initial = self._initial_deposits.get(event.bank_id, 0.0)
        if focus_initial > 0:
            current_total = bank.total_deposits()
            paid_fraction = max(0.0, (focus_initial - current_total) / focus_initial)
            if paid_fraction >= 0.50 and self._time_to_50pct_deposits_paid is None:
                self._time_to_50pct_deposits_paid = event.timestamp
        if bank.state.value == "suspended" and self._bank_suspension_time is None:
            self._bank_suspension_time = event.timestamp

        # Central Bank trigger: fires once when deposit-fraction-withdrawn crosses threshold.
        # Uses reserves-depleted fraction (partial withdrawals count) rather than agent count,
        # which only tracks fully-withdrawn agents and misses the real stress signal.
        if self._cb_agent is not None and not self._cb_triggered:
            cb_bank = self._banks.get(event.bank_id)
            initial_res = self._cb_initial_reserves.get(event.bank_id, 1.0)
            if cb_bank is not None and initial_res > 0:
                frac = max(0.0, 1.0 - cb_bank.reserves / initial_res)
            else:
                frac = len(self._withdrawn_agents) / max(len(self._agents), 1)
            if frac >= self._scenario.central_bank.trigger_threshold:
                self._cb_triggered = True
                new_events.append(CentralBankTriggered(
                    event_type=EventType.CENTRAL_BANK_TRIGGERED,
                    timestamp=event.timestamp,
                    bank_id=event.bank_id,
                    cascade_fraction=frac,
                    bank_reserve_ratio=cb_bank.reserve_ratio() if cb_bank else 0.0,
                    bank_state=cb_bank.state.value if cb_bank else "healthy",
                    withdrawn_count=len(self._withdrawn_agents),
                    total_agents=len(self._agents),
                ))

        # Schedule audit events
        wp = WithdrawalProcessed(
            event_type=EventType.WITHDRAWAL_PROCESSED,
            timestamp=event.timestamp,
            agent_id=agent.agent_id,
            bank_id=event.bank_id,
            amount_requested=amount_requested,
            amount_paid_out=result.amount_paid_out,
            fee_paid=result.fee_paid,
            was_queued=result.was_queued,
        )
        bru = BankReserveUpdated(
            event_type=EventType.BANK_RESERVE_UPDATED,
            timestamp=event.timestamp,
            bank_id=event.bank_id,
            new_reserves=bank.reserves,
            new_reserve_ratio=bank.reserve_ratio(),
            new_state=bank.state.value,
        )
        new_events.extend([wp, bru])

        # Emit social signal if the withdrawal went through
        if result.amount_paid_out > 0:
            reasoning_snippet = event.reasoning[:100] if event.reasoning else ""
            social = SocialSignalEmitted(
                event_type=EventType.SOCIAL_SIGNAL_EMITTED,
                timestamp=event.timestamp,
                source_agent_id=agent.agent_id,
                source_agent_name=agent.persona.name,
                source_archetype=agent.persona.archetype,
                action_event_id=event.event_id,
                action=event.action,
                bank_id=event.bank_id,
                reasoning_snippet=reasoning_snippet,
                visibility=self._scenario.social_signal_visibility,
            )
            new_events.append(social)

        return new_events

    def _handle_social_signal_emitted(
        self, event: SocialSignalEmitted, sim_time: float
    ) -> List[Event]:
        # Store for lookup when AgentObserved fires
        self._event_by_id[event.event_id] = event
        source_agent = self._agents.get(event.source_agent_id)
        return self._feed.route_social_signal(event, source_agent)

    def _handle_central_bank_acted(self, event: CentralBankActed, sim_time: float) -> List[Event]:
        """Apply the CB's chosen policy intervention."""
        new_events: List[Event] = []

        # Track CB outcome for metrics
        self._cb_policy_type = event.policy_type
        self._cb_action = event.action
        self._cb_triggered_at = event.timestamp

        bank = self._banks.get(event.bank_id)

        if event.action == "inject_liquidity" and bank is not None and event.liquidity_amount > 0:
            bank.reserves += event.liquidity_amount
            bru = BankReserveUpdated(
                event_type=EventType.BANK_RESERVE_UPDATED,
                timestamp=event.timestamp,
                bank_id=event.bank_id,
                new_reserves=bank.reserves,
                new_reserve_ratio=bank.reserve_ratio(),
                new_state=bank._recompute_state().value,
            )
            new_events.append(bru)
            logger.info(
                "CB injected $%.0f into %s → reserve ratio %.1f%%",
                event.liquidity_amount, event.bank_id, bank.reserve_ratio() * 100,
            )

        elif event.action == "announce_guarantee" and event.announcement_text:
            announcement = PolicyAnnounced(
                event_type=EventType.POLICY_ANNOUNCED,
                timestamp=event.timestamp,
                bank_id=event.bank_id,
                announcement_text=event.announcement_text,
                source="central_bank",
                cb_action_event_id=event.event_id,
            )
            new_events.append(announcement)
            logger.info("CB issued guarantee for %s", event.bank_id)

        return new_events

    def _handle_policy_announced(self, event: PolicyAnnounced, sim_time: float) -> List[Event]:
        """Route a CB policy announcement to all agents via the news feed."""
        self._event_by_id[event.event_id] = event
        return self._feed.route_policy_announcement(event)

    # ------------------------------------------------------------------
    # Async CB decision handler
    # ------------------------------------------------------------------

    async def _handle_cb_decision(
        self, event: CentralBankTriggered, sim_time: float
    ) -> List[Event]:
        """Run the CB decision (LLM call or rule-based) and return a CentralBankActed event."""
        result = await asyncio.to_thread(
            self._cb_agent.decide,
            bank_id=event.bank_id,
            bank_state=event.bank_state,
            bank_reserve_ratio=event.bank_reserve_ratio,
            cascade_fraction=event.cascade_fraction,
            withdrawn_count=event.withdrawn_count,
            total_agents=event.total_agents,
            sim_time=event.timestamp,
        )

        initial_reserves = self._cb_initial_reserves.get(event.bank_id, 0.0)
        liquidity_amount = initial_reserves * result.liquidity_fraction

        acted = CentralBankActed(
            event_type=EventType.CENTRAL_BANK_ACTED,
            timestamp=event.timestamp,
            action=result.action,
            bank_id=event.bank_id,
            reasoning=result.reasoning,
            announcement_text=result.announcement_text,
            liquidity_amount=liquidity_amount,
            confidence=result.confidence,
            policy_type=self._scenario.central_bank.policy_type,
            model_used=result.model_used,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd,
        )

        logger.info(
            "CB decision: action=%s policy=%s cost=$%.4f",
            result.action, self._scenario.central_bank.policy_type, result.cost_usd,
        )
        return [acted]

    # ------------------------------------------------------------------
    # Async decision handler (LLM call)
    # ------------------------------------------------------------------

    async def _handle_decision(
        self, event: AgentDecisionTriggered, sim_time: float
    ) -> List[Event]:
        agent = self._agents[event.agent_id]
        if agent.state == AgentState.WITHDRAWN:
            logger.debug(
                "Skipping decision for %s — already withdrawn", agent.agent_id
            )
            return []

        # Consume pending observations
        observations = list(self._pending_obs.get(event.agent_id, []))
        self._pending_obs[event.agent_id] = []

        # For peer-withdrawal re-decisions, surface the social signals too
        if event.trigger_reason == "peer_withdrawal":
            recent = self._social_details.get(event.agent_id, [])[-3:]
            observations.extend(recent)

        peer_summary = self._build_peer_summary(event.agent_id)
        prior_summary = self._build_prior_summary(agent)

        context = DecisionContext(
            bank_id_in_focus=event.bank_id,
            observations=observations,
            sim_time_seconds=event.timestamp,
            trigger_reason=event.trigger_reason,
            peer_action_summary=peer_summary,
            prior_decision_summary=prior_summary,
        )

        logger.info(
            "Decision: agent=%s bank=%s trigger=%s t=%.1f",
            agent.agent_id,
            event.bank_id,
            event.trigger_reason,
            event.timestamp,
        )

        record = await asyncio.to_thread(
            make_decision, agent, context, llm_client=self._llm_client
        )

        acted = AgentActed(
            event_type=EventType.AGENT_ACTED,
            timestamp=event.timestamp,
            agent_id=agent.agent_id,
            action=record.action,
            bank_id=context.bank_id_in_focus,
            amount_fraction=record.amount_fraction,
            reasoning=record.reasoning,
            confidence=record.confidence,
            decision_record_id=record.decision_id,
            model_used=record.model_used,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            cost_usd=record.cost_usd,
        )
        return [acted]

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _finalize(self, sim_time: float) -> None:
        """Reveal rumor truth, tag agent outcomes, compute unrealized outcomes."""
        # Build a unified list of (target_bank_id, is_true) from both rumors and signals.
        # For signals, use the first signal per bank to determine is_true.
        truth_by_bank: dict[str, bool] = {}
        for rumor in self._scenario.rumors:
            truth_by_bank[rumor.target_bank_id] = rumor.is_true
        for signal in self._scenario.signals:
            if signal.target_bank_id not in truth_by_bank:
                truth_by_bank[signal.target_bank_id] = signal.is_true

        class _TruthEntry:
            def __init__(self, bank_id: str, is_true: bool) -> None:
                self.target_bank_id = bank_id
                self.is_true = is_true

        unified_rumors = [_TruthEntry(bid, t) for bid, t in truth_by_bank.items()]

        for rumor in unified_rumors if unified_rumors else self._scenario.rumors:
            bank = self._banks.get(rumor.target_bank_id)
            truth = RumorTruthRevealed(
                event_type=EventType.RUMOR_TRUTH_REVEALED,
                timestamp=sim_time,
                bank_id=rumor.target_bank_id,
                rumor_was_true=rumor.is_true,
                revealed_reserve_ratio=bank.reserve_ratio() if bank else 0.0,
            )
            self._log(truth)

            for agent in self._agents.values():
                if agent.outcome_ledger is None:
                    continue

                withdrew_fully = agent.state == AgentState.WITHDRAWN
                last_action = (
                    agent.decision_history[-1].action
                    if agent.decision_history
                    else "hold"
                )
                # Only count as "partially withdrew" if the FINAL decision was a
                # withdrawal — agents who attempted a withdrawal but reversed to hold
                # should not be penalised for the reversal.
                withdrew_partially = (
                    agent.state == AgentState.HAS_DECIDED
                    and last_action in ("full_withdraw", "partial_withdraw")
                )

                if rumor.is_true:
                    if withdrew_fully:
                        tag = OutcomeTag.AVOIDED_CRISIS
                    elif withdrew_partially:
                        tag = OutcomeTag.PARTIAL_RESPONSE
                    else:
                        tag = OutcomeTag.IGNORED_REAL_WARNING
                        # Record counterfactual loss
                        if bank is not None:
                            deposit_at_risk = agent.deposit_at_bank(rumor.target_bank_id)
                            if deposit_at_risk > 0:
                                agent.outcome_ledger.unrealized_outcomes.append(
                                    UnrealizedOutcome(
                                        timestamp=sim_time,
                                        decision_event_id="finalization",
                                        outcome_type="would_have_lost",
                                        amount=deposit_at_risk,
                                        description=(
                                            f"Held ${deposit_at_risk:,.0f} at {rumor.target_bank_id} "
                                            f"through a real insolvency event."
                                        ),
                                    )
                                )
                else:
                    total_fees = agent.outcome_ledger.total_realized_cost()
                    if withdrew_fully or withdrew_partially:
                        tag = OutcomeTag.PANICKED_UNNECESSARILY
                        # Record the fees paid as the unnecessary cost
                        if total_fees > 0:
                            agent.outcome_ledger.unrealized_outcomes.append(
                                UnrealizedOutcome(
                                    timestamp=sim_time,
                                    decision_event_id="finalization",
                                    outcome_type="would_have_gained",
                                    amount=total_fees,
                                    description=(
                                        f"Paid ${total_fees:,.2f} in fees on a false rumor."
                                    ),
                                )
                            )
                    elif total_fees > 0:
                        # Partially withdrew then reversed to hold — paid fees but
                        # stopped before full exit. Outcome is nuanced: not a full
                        # panic, but not clean either.
                        tag = OutcomeTag.REVERSED_TO_HOLD
                        agent.outcome_ledger.unrealized_outcomes.append(
                            UnrealizedOutcome(
                                timestamp=sim_time,
                                decision_event_id="finalization",
                                outcome_type="would_have_gained",
                                amount=total_fees,
                                description=(
                                    f"Paid ${total_fees:,.2f} in fees before reversing to hold."
                                ),
                            )
                        )
                    else:
                        tag = OutcomeTag.ACTED_APPROPRIATELY

                if tag not in agent.outcome_ledger.outcome_tags:
                    agent.outcome_ledger.outcome_tags.append(tag)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _schedule(self, event: Event) -> None:
        heapq.heappush(self._queue, event)

    def _log(self, event: Event) -> None:
        self._event_log.append(event)
        self._event_by_id[event.event_id] = event
        logger.debug(
            "  [t=%6.1f] %s  agent=%s",
            event.timestamp,
            event.event_type.value,
            getattr(event, "agent_id", "—"),
        )

    def _decision_delay(self, agent: Optional[Agent] = None) -> float:
        if self._scenario.speed == ScenarioSpeed.AI_SPEED:
            # Small jitter so agents don't all decide at exactly the same timestamp
            return self._rng.uniform(0.5, 3.0)
        # Human speed: archetype-calibrated deliberation with anxiety scaling
        base = getattr(agent.persona, "deliberation_seconds", 20.0) if agent else 20.0
        anxiety_factor = 1.0
        if agent and agent.belief_states:
            max_anxiety = max(
                (b.anxiety_level for b in agent.belief_states.values()), default=0.0
            )
            # Anxious agents decide faster — panic overrides deliberation
            anxiety_factor = 1.0 - 0.6 * max_anxiety
        jitter = self._rng.uniform(0.8, 1.3)
        multiplier = getattr(self._scenario, "human_speed_deliberation_multiplier", 1.0)
        return max(1.0, base * anxiety_factor * jitter * multiplier)

    def _build_peer_summary(self, agent_id: str) -> Optional[str]:
        count = self._social_count.get(agent_id, 0)
        if count == 0:
            return None
        total_others = len(self._agents) - 1
        pct = int(count / max(total_others, 1) * 100)
        summary = (
            f"You have observed {count} of {total_others} other depositors "
            f"({pct}%) making withdrawals."
        )
        recent = self._social_details.get(agent_id, [])[-2:]
        if recent:
            summary += " Most recently: " + " ".join(recent)
        return summary

    def _build_prior_summary(self, agent: Agent) -> Optional[str]:
        if not agent.decision_history:
            return None
        last = agent.decision_history[-1]
        verb = last.action.replace("_", " ")
        snippet = last.reasoning[:200].rstrip()
        return (
            f"At T+{last.timestamp:.0f}s you decided to {verb} "
            f"(confidence {last.confidence:.0%}). Reasoning: '{snippet}...'"
        )

    def _build_result(
        self,
        started_at: str,
        completed_at: str,
        duration_seconds: float,
    ) -> RunResult:
        n = len(self._agents)
        fully = len(self._withdrawn_agents)
        partially = len(
            self._partially_withdrawn_agents - self._withdrawn_agents
        )
        held = n - fully - partially

        # Withdrawal fraction: fraction of Bank A deposits that left
        if self._scenario.rumors:
            focus_bank_id = self._scenario.rumors[0].target_bank_id
        elif self._scenario.signals:
            focus_bank_id = self._scenario.signals[0].target_bank_id
        else:
            focus_bank_id = None
        if focus_bank_id and self._initial_deposits.get(focus_bank_id, 0) > 0:
            initial = self._initial_deposits[focus_bank_id]
            current = self._banks[focus_bank_id].total_deposits() if focus_bank_id in self._banks else initial
            withdrawal_fraction = max(0.0, (initial - current) / initial)
        else:
            withdrawal_fraction = 0.0

        summary = self._llm_client.summary()

        metrics = RunMetrics(
            total_agents=n,
            withdrawn_count=fully,
            partially_withdrawn_count=partially,
            held_count=held,
            time_to_first_withdrawal=self._first_withdrawal_time,
            time_to_50pct_withdrawn=self._time_to_50pct,
            final_withdrawal_fraction=withdrawal_fraction,
            attempted_exit_count=len(self._attempted_exit_agents),
            paid_out_count=len(self._paid_out_agents),
            time_to_50pct_deposits_paid=self._time_to_50pct_deposits_paid,
            bank_suspension_time=self._bank_suspension_time,
            cascade_triggered=withdrawal_fraction >= 0.25,
            total_events=len(self._event_log),
            total_llm_calls=summary.total_calls,
            total_cost_usd=summary.total_cost_usd,
            cb_policy_type=self._cb_policy_type,
            cb_action=self._cb_action,
            cb_triggered_at=self._cb_triggered_at,
        )

        return RunResult(
            run_id=str(uuid.uuid4()),
            scenario_id=self._scenario.scenario_id,
            scenario_name=self._scenario.name,
            scenario_description=self._scenario.description,
            speed=self._scenario.speed.value,
            seed=self._scenario.seed,
            events=[e.to_dict() for e in self._event_log],
            agent_final_states=[a.to_dict() for a in self._agents.values()],
            bank_final_states=[b.to_dict() for b in self._banks.values()],
            metrics=metrics,
            llm_summary={
                "total_calls": summary.total_calls,
                "cache_hits": summary.cache_hits,
                "total_prompt_tokens": summary.total_prompt_tokens,
                "total_completion_tokens": summary.total_completion_tokens,
                "total_cost_usd": summary.total_cost_usd,
                "by_model": summary.by_model,
            },
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
        )


# ---------------------------------------------------------------------------
# Convenience: build banks from agents + scenario config
# ---------------------------------------------------------------------------


def build_banks(scenario: Scenario, agents: List[Agent]) -> Dict[str, Bank]:
    """Derive Bank objects from agent portfolios and scenario bank configs."""
    # Collect per-bank deposits from agent portfolios
    bank_deposits: Dict[str, Dict[str, float]] = {}
    for agent in agents:
        for key, amount in agent.portfolio.items():
            bank_id = key.split(":", 1)[0]
            bank_deposits.setdefault(bank_id, {})[agent.agent_id] = (
                bank_deposits.get(bank_id, {}).get(agent.agent_id, 0.0) + amount
            )

    banks: Dict[str, Bank] = {}
    for bc in scenario.banks:
        deposits = bank_deposits.get(bc.bank_id, {})
        total = sum(deposits.values())
        banks[bc.bank_id] = Bank(
            bank_id=bc.bank_id,
            name=bc.name,
            deposits=dict(deposits),
            reserves=total * bc.initial_reserve_ratio,
            reserve_ratio_target=bc.initial_reserve_ratio,
            withdrawal_processing_capacity=bc.withdrawal_processing_capacity,
            early_withdrawal_fee_rate=bc.early_withdrawal_fee_rate,
            distress_threshold=bc.distress_threshold,
            suspension_threshold=bc.suspension_threshold,
        )
    return banks


# ---------------------------------------------------------------------------
# Convenience: run a fully-configured scenario
# ---------------------------------------------------------------------------


async def run_scenario(
    scenario: Scenario,
    agents: List[Agent],
    *,
    llm_client: LLMClient,
    runs_dir: Optional[Path] = None,
    verbose: bool = True,
) -> RunResult:
    """Build banks, run the engine, optionally save, print cost summary."""
    banks = build_banks(scenario, agents)
    engine = SimulationEngine(
        scenario=scenario,
        agents=agents,
        banks=banks,
        llm_client=llm_client,
    )
    result = await engine.run()

    if verbose:
        m = result.metrics
        sep = "=" * 62
        print(f"\n{sep}")
        print(f"  {result.scenario_name}  [{result.speed} speed, seed={result.seed}]")
        print(sep)
        print(
            f"  Agents: {m.total_agents}  |  "
            f"Withdrew: {m.withdrawn_count}  |  "
            f"Partial: {m.partially_withdrawn_count}  |  "
            f"Held: {m.held_count}"
        )
        print(f"  Deposits withdrawn: {m.final_withdrawal_fraction:.1%} of Bank A total")
        print(
            f"  Tried to exit: {m.attempted_exit_count}/{m.total_agents}  |  "
            f"Got cash: {m.paid_out_count}/{m.total_agents}"
        )
        if m.time_to_first_withdrawal is not None:
            print(f"  Time to first withdrawal: {m.time_to_first_withdrawal:.1f}s")
        if m.time_to_50pct_deposits_paid is not None:
            print(f"  Time to 50%% deposits paid: {m.time_to_50pct_deposits_paid:.1f}s")
        if m.time_to_50pct_withdrawn is not None:
            print(f"  Time to 50%% withdrawn:   {m.time_to_50pct_withdrawn:.1f}s")
        if m.bank_suspension_time is not None:
            print(f"  Bank suspended:           {m.bank_suspension_time:.1f}s")
        print(f"  Cascade: {'YES' if m.cascade_triggered else 'no'}")
        print(f"  Events: {m.total_events}  |  Wall clock: {result.duration_seconds:.1f}s")
        print()
        print(llm_client.format_cost_summary())
        print(sep)

    if runs_dir is not None:
        path = result.save(runs_dir)
        if verbose:
            print(f"  Run saved -> {path}\n")

    return result


# ---------------------------------------------------------------------------
# Preset scenarios
# ---------------------------------------------------------------------------


def make_rumor_moderate_scenario(
    speed: ScenarioSpeed = ScenarioSpeed.AI_SPEED,
    seed: int = 42,
) -> Scenario:
    """Standard bank-run scenario: moderate-credibility rumor about Bank A.

    Bank A starts with a 10% reserve ratio (tight). Bank B is at 20% (healthy).
    The rumor is false by default so we can observe unnecessary panic dynamics.
    """
    return Scenario(
        scenario_id="rumor_moderate",
        name="Bank Run: Moderate-Credibility Rumor",
        description=(
            "A moderate-credibility rumor about Bank A insolvency enters the "
            "information environment at t=0. Bank A has a 10% reserve ratio. "
            "The rumor is false — this scenario tests unnecessary panic dynamics."
        ),
        rumors=[
            RumorConfig(
                content=(
                    "Redwood Regional Bank is facing unusual liquidity pressure "
                    "after a weak quarterly call report. Several large corporate "
                    "depositors are rumored to have begun moving funds."
                ),
                source="financial_news_outlet",
                credibility=0.55,
                target_bank_id="bank_a",
                publish_at_time=0.0,
                is_true=False,
                propagation_latency_seconds=5.0,
            )
        ],
        banks=[
            BankConfig(
                bank_id="bank_a",
                name="Redwood Regional Bank",
                initial_reserve_ratio=0.10,
                early_withdrawal_fee_rate=0.03,
                withdrawal_processing_capacity=450_000.0,
            ),
            BankConfig(
                bank_id="bank_b",
                name="Harbor National Bank",
                initial_reserve_ratio=0.20,
                early_withdrawal_fee_rate=0.02,
                withdrawal_processing_capacity=5_000_000.0,
            ),
        ],
        population=[
            AgentPopulationGroup(
                archetype="cautious_retiree",
                count=3,
                primary_bank_id="bank_a",
                primary_deposit_range=(25_000, 52_000),
                secondary_bank_id="bank_b",
                secondary_deposit_range=(6_000, 19_000),
            ),
            AgentPopulationGroup(
                archetype="aggressive_trader",
                count=3,
                primary_bank_id="bank_a",
                primary_deposit_range=(11_000, 38_000),
                secondary_bank_id="bank_b",
                secondary_deposit_range=(3_000, 9_000),
            ),
            AgentPopulationGroup(
                archetype="gig_worker",
                count=3,
                primary_bank_id="bank_a",
                primary_deposit_range=(1_800, 3_200),
                secondary_bank_id="bank_b",
                secondary_deposit_range=(350, 600),
            ),
            AgentPopulationGroup(
                archetype="institutional_treasurer",
                count=3,
                primary_bank_id="bank_a",
                primary_deposit_range=(310_000, 590_000),
                secondary_bank_id="bank_b",
                secondary_deposit_range=(85_000, 260_000),
            ),
        ],
        speed=speed,
        human_speed_decision_delay_seconds=90.0,
        social_signal_visibility=1.0,
        seed=seed,
        max_simulation_time=3600.0,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s %(message)s",
    )


if __name__ == "__main__":
    import os
    import sys

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Run a bank-run simulation.")
    parser.add_argument(
        "--scenario",
        choices=["rumor_moderate"],
        default="rumor_moderate",
        help="Preset scenario to run (default: rumor_moderate)",
    )
    parser.add_argument(
        "--speed",
        choices=["ai", "human"],
        default="ai",
        help="Simulation speed setting (default: ai)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Directory to save run JSON (default: runs/)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug-level event logging",
    )
    args = parser.parse_args()

    _setup_logging(args.debug)

    from src.decisions.llm_client import LLMClient
    from src.personas.instances import make_all_agents

    speed = ScenarioSpeed.AI_SPEED if args.speed == "ai" else ScenarioSpeed.HUMAN_SPEED
    scenario = make_rumor_moderate_scenario(speed=speed, seed=args.seed)
    agents = make_all_agents()
    client = LLMClient()

    asyncio.run(
        run_scenario(
            scenario,
            agents,
            llm_client=client,
            runs_dir=Path(args.runs_dir),
            verbose=True,
        )
    )
