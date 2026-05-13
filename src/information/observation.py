"""
Render simulation events into plain-English observation strings.

These strings are what agents actually read when making decisions. Each
function takes a structured event and returns a string that will appear in
the agent's decision prompt under "What you have just observed."
"""

from __future__ import annotations

from src.core.event import PolicyAnnounced, RumorPublished, SocialSignalEmitted


def render_rumor_observation(rumor: RumorPublished) -> str:
    label = _credibility_label(rumor.credibility)
    return (
        f"[{rumor.source}] {label.capitalize()}-credibility report: "
        f"{rumor.content} "
        f"(source credibility: {rumor.credibility:.0%})"
    )


def render_social_observation(signal: SocialSignalEmitted, source_archetype: str) -> str:
    archetype_label = source_archetype.replace("_", " ")
    action_phrase = {
        "full_withdraw":    "fully withdrew their funds",
        "partial_withdraw": "partially withdrew their funds",
        "hold":             "decided to hold",
        "increase_deposit": "added more to their deposit",
    }.get(signal.action, "took an action")
    return (
        f"[Social feed] A {archetype_label} just {action_phrase} "
        f"from {signal.bank_id}."
    )


def render_policy_observation(announcement: PolicyAnnounced) -> str:
    return (
        f"[CENTRAL BANK — OFFICIAL ANNOUNCEMENT] {announcement.announcement_text}"
    )


def _credibility_label(credibility: float) -> str:
    if credibility >= 0.80:
        return "high"
    elif credibility >= 0.50:
        return "moderate"
    elif credibility >= 0.25:
        return "low"
    else:
        return "very low"
