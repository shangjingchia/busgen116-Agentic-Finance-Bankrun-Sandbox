"""
Render simulation events into plain-English observation strings.

These strings are what agents actually read when making decisions. Each
function takes a structured event and returns a string that will appear in
the agent's decision prompt under "What you have just observed."
"""

from __future__ import annotations

from src.core.event import PolicyAnnounced, RumorPublished, SocialSignalEmitted
from src.information.environment import SOURCE_LABELS, InformationSignal

_BANK_LABELS = {
    "bank_a": "Redwood Regional Bank",
    "bank_b": "Harbor National Bank",
}


def _bank_label(bank_id: str) -> str:
    return _BANK_LABELS.get(bank_id, bank_id)


def render_rumor_observation(rumor: RumorPublished) -> str:
    label = _credibility_label(rumor.credibility)
    return (
        f"[{rumor.source}] {label.capitalize()}-credibility report: "
        f"{rumor.content} "
        f"(source credibility: {rumor.credibility:.0%})"
    )


def render_signal_observation(signal: InformationSignal, archetype: str) -> str:
    """Render an InformationSignal for the given archetype's decision prompt."""
    source_label = SOURCE_LABELS.get(signal.source_type, signal.source_type)
    eff_cred = signal.effective_credibility(archetype)
    cred_label = _credibility_label(eff_cred)
    tone = _alarm_tone(signal.alarm_level)
    return (
        f"[{source_label}] {cred_label.capitalize()}-credibility {tone}: "
        f"{signal.content} "
        f"(your assessed credibility: {eff_cred:.0%})"
    )


def render_social_observation(signal: SocialSignalEmitted, observer_archetype: str) -> str:
    """Render a social signal with agent name, peer-matching note, and reasoning snippet."""
    name = signal.source_agent_name or "Someone"
    source_arch = signal.source_archetype or ""
    peer_note = " (same type as you)" if source_arch and source_arch == observer_archetype else ""

    action_phrase = {
        "full_withdraw":    f"just pulled all their money from {_bank_label(signal.bank_id)}",
        "partial_withdraw": f"just moved some money out of {_bank_label(signal.bank_id)}",
        "hold":             f"checked their account and decided to stay at {_bank_label(signal.bank_id)}",
        "increase_deposit": f"just added more to their account at {_bank_label(signal.bank_id)}",
    }.get(signal.action, f"just took an action at {_bank_label(signal.bank_id)}")

    snippet_part = ""
    if signal.reasoning_snippet:
        snippet_part = f' They noted: "{signal.reasoning_snippet[:100]}..."'

    return f"[Social feed] {name}{peer_note} {action_phrase}.{snippet_part}"


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


def _alarm_tone(alarm_level: float) -> str:
    if alarm_level >= 0.6:
        return "alarm"
    elif alarm_level >= 0.2:
        return "warning"
    elif alarm_level >= -0.1:
        return "update"
    elif alarm_level >= -0.5:
        return "reassurance"
    else:
        return "strong reassurance"
