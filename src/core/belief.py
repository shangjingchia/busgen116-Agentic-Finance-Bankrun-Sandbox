"""
BeliefState: per-agent accumulated evidence about a bank's health.

Each agent maintains one BeliefState per bank they hold deposits in.
The state is updated on every InformationSignal the agent observes,
blending cumulative evidence with an archetype-specific prior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class BeliefState:
    bank_id: str
    trouble_probability: float        # 0–1; starts at 1 - institution_trust_prior
    confidence: float                 # 0–1; grows with each signal seen
    anxiety_level: float              # 0–1; rises when alarm signals dominate
    alarm_weight_total: float = 0.0
    reassurance_weight_total: float = 0.0
    signals_seen: int = 0

    def update(self, alarm_level: float, effective_credibility: float) -> None:
        """Update belief given a signal's alarm_level and archetype-adjusted credibility."""
        weighted = alarm_level * effective_credibility
        if weighted > 0:
            self.alarm_weight_total += weighted
        else:
            self.reassurance_weight_total += abs(weighted)
        self.signals_seen += 1

        total = self.alarm_weight_total + self.reassurance_weight_total + 1e-6
        raw_p = self.alarm_weight_total / total

        # Prior decays as evidence accumulates
        prior_weight = max(0.0, 1.0 - 0.2 * self.signals_seen)
        self.trouble_probability = (
            prior_weight * self.trouble_probability + (1.0 - prior_weight) * raw_p
        )
        self.confidence = min(1.0, 0.2 * self.signals_seen)
        self.anxiety_level = min(
            1.0,
            self.alarm_weight_total / (self.alarm_weight_total + 0.5),
        )

    def render_for_prompt(self) -> str:
        pct = int(self.trouble_probability * 100)
        conf_labels = [
            "very uncertain",
            "somewhat uncertain",
            "moderately confident",
            "fairly confident",
            "very confident",
        ]
        anxiety_labels = [
            "calm",
            "somewhat concerned",
            "anxious",
            "quite anxious",
            "panicked",
        ]
        conf_str = conf_labels[min(4, int(self.confidence * 5))]
        anxiety_str = anxiety_labels[min(4, int(self.anxiety_level * 5))]
        pieces_str = (
            f"{self.signals_seen} piece{'s' if self.signals_seen != 1 else ''} of information"
        )
        return (
            f"Your current read: you believe there is roughly a {pct}% chance the bank is "
            f"in genuine trouble. You are {conf_str} in this estimate — you have seen "
            f"{pieces_str}. Emotionally you feel {anxiety_str}."
        )

    @classmethod
    def initial(cls, bank_id: str, institution_trust_prior: float) -> "BeliefState":
        """Create a fresh belief state seeded from an archetype's trust prior."""
        return cls(
            bank_id=bank_id,
            trouble_probability=1.0 - institution_trust_prior,
            confidence=0.0,
            anxiety_level=0.0,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bank_id": self.bank_id,
            "trouble_probability": self.trouble_probability,
            "confidence": self.confidence,
            "anxiety_level": self.anxiety_level,
            "alarm_weight_total": self.alarm_weight_total,
            "reassurance_weight_total": self.reassurance_weight_total,
            "signals_seen": self.signals_seen,
        }
