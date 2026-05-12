"""
Rumor injection: convert scenario RumorConfig objects into RumorPublished events.

This is the seam between scenario configuration and the event stream. In v2,
the natural-language scenario translator produces RumorConfig objects; this
module turns them into events without knowing how the configs were created.
"""

from __future__ import annotations

from src.core.event import EventType, RumorPublished
from src.core.scenario import RumorConfig


def rumor_config_to_event(config: RumorConfig) -> RumorPublished:
    """Convert a RumorConfig into a RumorPublished event ready for the queue."""
    return RumorPublished(
        event_type=EventType.RUMOR_PUBLISHED,
        timestamp=config.publish_at_time,
        content=config.content,
        source=config.source,
        credibility=config.credibility,
        bank_id=config.target_bank_id,
        target_agent_ids=[],  # broadcast to all subscribed agents
    )
