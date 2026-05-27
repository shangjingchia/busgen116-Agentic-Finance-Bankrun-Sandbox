"""
InformationSignal: the unit of information that enters the simulation.

Replaces the single-rumor model with a stream of signals that differ by:
  - source_type: social_media vs. official_bank vs. regulator, etc.
  - alarm_level: -1.0 (reassuring) to +1.0 (alarming)
  - archetype_credibility_multipliers: each archetype weights sources differently
  - visible_to_archetypes: optional filter — empty list means broadcast to all

This creates diverging beliefs: gig workers see only social-media alarm while
institutional treasurers also receive official denials and FDIC statements.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List


# Source type labels (used in observation rendering and credibility look-ups)
SOURCE_SOCIAL_MEDIA = "social_media"
SOURCE_FINANCIAL_NEWS = "financial_news"
SOURCE_OFFICIAL_BANK = "official_bank"
SOURCE_REGULATOR = "regulator"
SOURCE_PEER_NETWORK = "peer_network"
SOURCE_INTERNAL_ANALYSIS = "internal_analysis"

# Human-readable labels for rendering in agent prompts
SOURCE_LABELS: Dict[str, str] = {
    SOURCE_SOCIAL_MEDIA:     "Social media",
    SOURCE_FINANCIAL_NEWS:   "Financial news",
    SOURCE_OFFICIAL_BANK:    "Official bank statement",
    SOURCE_REGULATOR:        "Regulatory authority",
    SOURCE_PEER_NETWORK:     "Peer network",
    SOURCE_INTERNAL_ANALYSIS: "Internal analysis",
}


@dataclass
class InformationSignal:
    """A single piece of information in the information environment.

    alarm_level is the core behavioral lever:
      +1.0 = maximally alarming ("bank will fail")
      -1.0 = maximally reassuring ("bank is fine, rumors are false")
       0.0 = neutral / uncertain

    archetype_credibility_multipliers adjusts base_credibility per archetype.
    A multiplier of 1.3 means this archetype trusts this source 30% more than average.
    A multiplier of 0.3 means this archetype largely discounts this source.

    visible_to_archetypes filters who can receive this signal at all.
    The agent's persona.information_access further filters by source_type.
    Both conditions must pass for an agent to observe a signal.
    """

    content: str
    source_type: str                           # one of SOURCE_* constants
    alarm_level: float                         # -1.0 (reassuring) to +1.0 (alarming)
    base_credibility: float                    # 0-1
    publish_at: float                          # simulation seconds
    target_bank_id: str
    propagation_latency_seconds: float = 3.0   # mean per-archetype observation latency
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    archetype_credibility_multipliers: Dict[str, float] = field(default_factory=dict)
    visible_to_archetypes: List[str] = field(default_factory=list)   # [] = broadcast all
    is_true: bool = False                      # ground truth of the underlying claim

    def effective_credibility(self, archetype: str) -> float:
        """Return this source's credibility as perceived by a given archetype."""
        mult = self.archetype_credibility_multipliers.get(archetype, 1.0)
        return min(1.0, max(0.0, self.base_credibility * mult))

    def is_visible_to(self, archetype: str, information_access: List[str]) -> bool:
        """Return True if an agent of this archetype can receive this signal."""
        if self.visible_to_archetypes and archetype not in self.visible_to_archetypes:
            return False
        if information_access and self.source_type not in information_access:
            return False
        return True
