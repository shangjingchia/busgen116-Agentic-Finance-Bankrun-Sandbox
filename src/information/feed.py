"""
Feed: routes published events to subscribed agents with per-agent latency.

Two feed channels in v1:
  news_feed   — receives RumorPublished events; all agents subscribe by default.
  social_feed — receives SocialSignalEmitted events; agents may miss signals
                depending on the scenario's social_signal_visibility setting.

Rumor latency reflects information pipeline tier, not raw network speed.
Institutional treasurers monitor regulatory/compliance feeds directly;
gig workers see consumer aggregators that republish from those primary sources.
Each archetype samples from a band expressed as a multiplier on the scenario's
propagation_latency_seconds, producing consistent tier ordering across runs.
"""

from __future__ import annotations

import random
from typing import List

from src.core.agent import Agent
from src.core.event import AgentObserved, EventType, PolicyAnnounced, RumorPublished, SocialSignalEmitted
from src.core.scenario import Scenario


# Latency band (lo, hi) as multipliers on the scenario mean latency.
# Reflects information pipeline tier: institutional agents subscribe to
# regulatory/compliance feeds; retail agents see consumer news aggregators.
_ARCHETYPE_LATENCY_BAND: dict[str, tuple[float, float]] = {
    "institutional_treasurer": (0.1, 0.5),   # compliance/regulatory feeds
    "aggressive_trader":        (0.5, 1.2),   # professional terminals
    "cautious_retiree":         (1.0, 2.0),   # mainstream financial news
    "gig_worker":               (1.5, 3.0),   # consumer aggregators / social media
}
_DEFAULT_LATENCY_BAND: tuple[float, float] = (0.0, 2.0)


class Feed:
    def __init__(
        self,
        scenario: Scenario,
        agents: List[Agent],
        rng: random.Random,
    ) -> None:
        self._scenario = scenario
        self._agents = {a.agent_id: a for a in agents}
        self._rng = rng
        self._rumor_mean_latency: float = (
            scenario.rumors[0].propagation_latency_seconds
            if scenario.rumors
            else 5.0
        )

    def route_rumor(self, rumor: RumorPublished) -> List[AgentObserved]:
        """Return AgentObserved events for each agent subscribed to news_feed."""
        events: List[AgentObserved] = []
        for agent in self._agents.values():
            if "news_feed" not in agent.subscriptions:
                continue
            if rumor.target_agent_ids and agent.agent_id not in rumor.target_agent_ids:
                continue
            arch = getattr(agent.persona, "archetype", "")
            lo, hi = _ARCHETYPE_LATENCY_BAND.get(arch, _DEFAULT_LATENCY_BAND)
            latency = self._rng.uniform(
                lo * self._rumor_mean_latency,
                hi * self._rumor_mean_latency,
            )
            events.append(
                AgentObserved(
                    event_type=EventType.AGENT_OBSERVED,
                    timestamp=rumor.timestamp + latency,
                    agent_id=agent.agent_id,
                    observed_event_id=rumor.event_id,
                    observation_latency=latency,
                )
            )
        return events

    def route_policy_announcement(self, event: PolicyAnnounced) -> List[AgentObserved]:
        """Route a CB policy announcement to all news-feed subscribers.

        Uses the same archetype-based latency as rumors (institutional agents
        hear it faster) but always broadcasts to everyone — no visibility filter.
        """
        events: List[AgentObserved] = []
        mean_latency = 2.0  # CB announcements propagate quickly
        for agent in self._agents.values():
            if "news_feed" not in agent.subscriptions:
                continue
            arch = getattr(agent.persona, "archetype", "")
            lo, hi = _ARCHETYPE_LATENCY_BAND.get(arch, _DEFAULT_LATENCY_BAND)
            latency = self._rng.uniform(lo * mean_latency, hi * mean_latency)
            events.append(
                AgentObserved(
                    event_type=EventType.AGENT_OBSERVED,
                    timestamp=event.timestamp + latency,
                    agent_id=agent.agent_id,
                    observed_event_id=event.event_id,
                    observation_latency=latency,
                )
            )
        return events

    def route_social_signal(
        self,
        signal: SocialSignalEmitted,
        source_agent: Agent,
    ) -> List[AgentObserved]:
        """Return AgentObserved events for agents who see this social signal.

        Each agent has a ``signal.visibility`` probability of receiving it.
        Social signals propagate faster than news (0.5–3 s latency).
        """
        events: List[AgentObserved] = []
        for agent in self._agents.values():
            if agent.agent_id == signal.source_agent_id:
                continue
            if "social_feed" not in agent.subscriptions:
                continue
            if self._rng.random() > signal.visibility:
                continue
            latency = self._rng.uniform(0.5, 3.0)
            events.append(
                AgentObserved(
                    event_type=EventType.AGENT_OBSERVED,
                    timestamp=signal.timestamp + latency,
                    agent_id=agent.agent_id,
                    observed_event_id=signal.event_id,
                    observation_latency=latency,
                )
            )
        return events
