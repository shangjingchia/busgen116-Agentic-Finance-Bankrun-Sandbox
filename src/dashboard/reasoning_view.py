"""
Inspect view: click any agent, read their full LLM reasoning.

Layout:
  Left col  (1/3): Agent roster grouped by archetype with outcome badges.
  Right col (2/3): Context card (who + stakes) → verdict → decision →
                   reasoning (all immediately visible). Technical detail
                   in collapsible expanders below.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st


def _esc(s) -> str:
    """Escape '$' so Streamlit's markdown doesn't read a pair of dollar signs as
    LaTeX math (which renders the span in a mismatched serif font). Applied to all
    dynamic text — LLM reasoning, cost narratives, dollar amounts — before it goes
    into st.markdown(..., unsafe_allow_html=True)."""
    return str(s).replace("$", "&#36;")


_ARCHETYPE_ICON: Dict[str, str] = {
    "cautious_retiree": "🧓",
    "aggressive_trader": "📈",
    "gig_worker": "🚗",
    "institutional_treasurer": "🏛️",
}

_ARCHETYPE_LABEL: Dict[str, str] = {
    "cautious_retiree": "Cautious Retiree",
    "aggressive_trader": "Aggressive Trader",
    "gig_worker": "Gig Worker",
    "institutional_treasurer": "Institutional Treasurer",
}

_ARCHETYPE_ORDER = [
    "cautious_retiree",
    "aggressive_trader",
    "gig_worker",
    "institutional_treasurer",
]

_ACTION_COLOR: Dict[str, str] = {
    "full_withdraw": "#E15759",
    "partial_withdraw": "#F1A340",
    "hold": "#4E79A7",
    "increase_deposit": "#76B7B2",
}

_ACTION_LABEL: Dict[str, str] = {
    "full_withdraw": "Full withdrawal",
    "partial_withdraw": "Partial withdrawal",
    "hold": "Held — kept money in",
    "increase_deposit": "Increased deposit",
}


def _bank_a_init_final(agent: Dict) -> tuple:
    """Bank A deposit at the start vs the end of the run for this agent."""
    dh = agent.get("decision_history") or []
    cur = agent.get("portfolio", {}) or {}
    init_port = dh[0].get("portfolio_snapshot", cur) if dh else cur
    return init_port.get("bank_a:deposit", 0.0), cur.get("bank_a:deposit", 0.0)


def _bank_a_haircut(agent: Dict) -> float:
    """End-of-run insolvency write-down on this agent's Bank A deposit (a haircut
    shrinks the balance but is NOT a withdrawal — they held and the bank failed)."""
    return sum(
        c.get("amount", 0.0)
        for c in (agent.get("outcome_ledger") or {}).get("realized_costs", [])
        if c.get("cost_category") == "locked_in_loss"
    )


def _withdrawn_amount(agent: Dict) -> tuple:
    """(amount actually withdrawn from Bank A net of any insolvency haircut, init, final)."""
    init, final = _bank_a_init_final(agent)
    return max(0.0, (init - final) - _bank_a_haircut(agent)), init, final


def _effective_action(agent: Dict) -> Optional[str]:
    """What actually happened to the agent's money at Bank A — consistent with the
    balance, the outcome, AND the headline counts. Keyed on money actually WITHDRAWN
    (net of any insolvency write-down), not on what they decided/attempted: an agent
    who decided to run but got nothing out before suspension, or who held while the
    bank wrote their deposit down, counts as 'held' — not 'withdrew'."""
    withdrawn, init, final = _withdrawn_amount(agent)
    if init <= 0:
        return "hold"
    if agent.get("state") == "withdrawn":
        return "full_withdraw"           # fully exited (balance emptied)
    if withdrawn > 1e-6:
        return "partial_withdraw"         # actually pulled some out, some remains
    if final - init > 1e-6:
        return "increase_deposit"
    return "hold"                         # kept money in (any shrinkage was a haircut)


_MONEY_STATUS_VERB: Dict[str, str] = {
    "full_withdraw": "withdrew everything",
    "partial_withdraw": "withdrew part of it",
    "increase_deposit": "added money",
    "hold": "kept their money in",
}


def _run_was_true(run: Dict) -> Optional[bool]:
    """Was the rumor actually true (bank genuinely failing)? None if not revealed."""
    for e in run.get("events", []):
        if e.get("event_type") == "rumor_truth_revealed":
            return bool(e.get("rumor_was_true", False))
    return None


def _money_verdict(eff: Optional[str], was_true: Optional[bool]) -> str:
    """Plain-English outcome consistent with what happened to the money."""
    withdrew = eff in ("full_withdraw", "partial_withdraw")
    if was_true is True:
        if eff == "full_withdraw":
            return "got out before the collapse"
        if eff == "partial_withdraw":
            return "got some out before the bank froze"
        return "held through a real insolvency — lost principal"
    if was_true is False:
        if withdrew:
            return "withdrew from a bank that was actually fine"
        return "kept their money in — the bank was solvent"
    return ""

_SEVERITY_BADGE: Dict[str, str] = {
    "catastrophic": "🔴 Catastrophic",
    "significant": "🟠 Significant",
    "moderate": "🟡 Moderate",
    "minor": "🔵 Minor",
    "irrelevant": "⚫ Irrelevant",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bank_state_at(events: List[Dict], bank_id: str, before_ts: float) -> str:
    state = "healthy"
    for e in events:
        if (e.get("event_type") == "bank_reserve_updated"
                and e.get("bank_id") == bank_id
                and e.get("timestamp", 9e9) <= before_ts):
            state = e.get("new_state", state)
    return state


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    s = text.split(".")[0].strip()
    return s + "." if s else ""


def _build_context_summary(
    persona: Dict,
    history: List[Dict],
    ledger: Dict,
    eff_action: Optional[str] = None,
    was_true: Optional[bool] = None,
) -> Dict[str, str]:
    """Build a plain-English summary of who this agent is and what happened."""
    name = persona.get("name", "This agent")
    arch_label = _ARCHETYPE_LABEL.get(persona.get("archetype", ""), "Agent")

    # One sentence from background narrative
    bg_sentence = _first_sentence(persona.get("background_narrative", ""))

    # What's most at stake — find the highest-severity cost function item
    cost_fn = persona.get("cost_function", [])
    severity_order = ["catastrophic", "significant", "moderate", "minor", "irrelevant"]
    top_cost = None
    for sev in severity_order:
        top_cost = next((c for c in cost_fn if c.get("severity") == sev), None)
        if top_cost:
            break
    stakes = _first_sentence(top_cost.get("narrative", "")) if top_cost else ""

    # What they did — keyed on money actually moved, so it matches the badge,
    # the balance shown below, and the headline counts.
    action_verb = {
        "full_withdraw": "withdrew everything",
        "partial_withdraw": "made a partial withdrawal",
        "hold": "kept their money in",
        "increase_deposit": "increased their deposit",
    }.get(eff_action, "took no action")

    # Outcome consistent with what happened to the money (not the stored tag).
    verdict = _money_verdict(eff_action, was_true)

    return {
        "name": name,
        "arch_label": arch_label,
        "bg_sentence": bg_sentence,
        "stakes": stakes,
        "action_verb": action_verb,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Sub-renderers
# ---------------------------------------------------------------------------


def _render_context_card(summary: Dict[str, str], portfolio: Dict) -> None:
    """Top card: who this agent is and what happened, in plain English."""
    name = summary["name"]
    arch_label = summary["arch_label"]
    bg = summary["bg_sentence"]
    stakes = summary["stakes"]
    action_verb = summary["action_verb"]
    verdict = summary["verdict"]

    bank_a = portfolio.get("bank_a:deposit", 0)
    bank_b = portfolio.get("bank_b:deposit", 0)
    deposits = f"Bank A: &#36;{bank_a:,.0f}"
    if bank_b > 0:
        deposits += f" · Bank B: &#36;{bank_b:,.0f}"

    # Narrative sentence: "She withdrew everything — the bank was fine."
    narrative = action_verb.capitalize()
    if verdict:
        narrative += f" — {verdict}."
    else:
        narrative += "."

    stakes_html = (
        '<div style="font-size:0.88rem;color:#555;font-style:italic;margin-bottom:0.4rem">'
        + _esc(stakes) + "</div>"
    ) if stakes else ""

    st.markdown(
        '<div style="background:#F0F4FF;border:1.5px solid #4E79A7;border-radius:8px;'
        'padding:1rem 1.3rem;margin-bottom:1rem">'
        '<div style="font-weight:700;font-size:1.05rem;color:#1C3A5E;margin-bottom:0.3rem">'
        f'{arch_label} &nbsp;·&nbsp; {deposits}'
        '</div>'
        '<div style="font-size:0.92rem;color:#333;line-height:1.65;margin-bottom:0.4rem">'
        f'{_esc(bg)}'
        '</div>'
        + stakes_html +
        '<div style="font-size:0.92rem;font-weight:600;color:#1C3A5E">'
        f'{_esc(narrative)}'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_verdict_banner(eff_action: Optional[str], was_true: Optional[bool]) -> None:
    """Outcome verdict derived from what actually happened to the money + whether
    the rumor was true — so it can never contradict the badge/balance."""
    text = _money_verdict(eff_action, was_true)
    if not text:
        return
    withdrew = eff_action in ("full_withdraw", "partial_withdraw")
    if was_true is False:
        good = not withdrew          # holding a solvent bank was the right call
    elif was_true is True:
        good = withdrew              # exiting a failing bank was the right call
    else:
        good = None
    if good is True:
        bg, border, icon = "#E8F4EA", "#4A6741", "✅"
    elif good is False:
        bg, border, icon = "#FFF3E0", "#C4873A", "⚠️"
    else:
        bg, border, icon = "#F4F2EF", "#888", "•"
    st.markdown(
        f'<div style="background:{bg};border-left:4px solid {border};'
        f'border-radius:6px;padding:0.5rem 1rem;margin-bottom:0.8rem;font-weight:600">'
        f'{icon} {text[0].upper() + text[1:]}</div>',
        unsafe_allow_html=True,
    )


def _render_latest_decision(
    agent: Dict,
    history: List[Dict],
    all_events: List[Dict],
) -> None:
    """Decision banner + what actually happened + reasoning — the centerpiece."""
    if not history:
        st.info("No decisions recorded for this agent.")
        return

    last = history[-1]
    action = last.get("action", "—")
    ts = last.get("timestamp", 0)
    reasoning = last.get("reasoning", "")
    conf = last.get("confidence")
    trigger = last.get("trigger_reason", "").replace("_", " ")
    bank_state = _bank_state_at(all_events, "bank_a", ts)

    action_color = _ACTION_COLOR.get(action, "#AAAAAA")
    action_label = _ACTION_LABEL.get(action, action.replace("_", " ").title())

    # Action banner — this is the DECISION the agent made
    meta_parts = [f"T+{ts:.0f}s"]
    meta_parts.append(f"Bank A: {bank_state}")
    if conf is not None:
        meta_parts.append(f"confidence {conf:.0%}")
    if trigger:
        meta_parts.append(f"triggered by {trigger}")

    st.markdown(
        f'<div style="background:{action_color}22;border-left:5px solid {action_color};'
        f'border-radius:6px;padding:0.6rem 1rem;margin-bottom:0.5rem">'
        f'<span style="font-size:0.7rem;font-weight:700;color:#888;text-transform:uppercase;'
        f'letter-spacing:0.07em">Decision</span><br>'
        f'<span style="font-size:1.05rem;font-weight:700">{action_label}</span>'
        f'<span style="color:#666;font-size:0.85rem;margin-left:1rem">'
        f'{" · ".join(meta_parts)}'
        f'</span></div>',
        unsafe_allow_html=True,
    )

    # What actually happened to the money — reconciles the decision with the
    # outcome. An agent can DECIDE to pull everything yet keep their money if the
    # bank suspends first; this line makes that explicit.
    withdrawn, init, final = _withdrawn_amount(agent)
    fully_out = agent.get("state") == "withdrawn"
    decided_withdraw = action in ("full_withdraw", "partial_withdraw")
    out_txt = out_bg = out_bd = None
    if init > 0:
        if fully_out:
            out_txt = f"✅ Got the full <b>${withdrawn:,.0f}</b> out of Bank A before it suspended."
            out_bg, out_bd = "#FEECEC", "#E15759"
        elif withdrawn > 1e-6 and decided_withdraw:
            out_txt = (
                f"⚠️ Only <b>${withdrawn:,.0f}</b> came out — Bank A suspended mid-withdrawal, "
                f"so <b>${final:,.0f}</b> stayed tied up in the bank."
            )
            out_bg, out_bd = "#FFF3E0", "#C4873A"
        elif withdrawn > 1e-6 and not decided_withdraw:
            out_txt = (
                f"↩️ Pulled <b>${withdrawn:,.0f}</b> out earlier, then reversed to holding — "
                f"<b>${final:,.0f}</b> remains in Bank A."
            )
            out_bg, out_bd = "#FFF3E0", "#C4873A"
        elif decided_withdraw:  # nothing actually came out
            out_txt = (
                f"🔒 <b>$0</b> actually came out — Bank A had already suspended when this "
                f"decision fired, so none of the <b>${init:,.0f}</b> was withdrawn. "
                f"<i>Decided to run, but too late.</i>"
            )
            out_bg, out_bd = "#EEF1F6", "#4E79A7"
    if out_txt:
        st.markdown(
            f'<div style="background:{out_bg};border-left:5px solid {out_bd};'
            f'border-radius:6px;padding:0.5rem 1rem;margin-bottom:0.8rem;font-size:0.9rem">'
            f'<span style="font-size:0.7rem;font-weight:700;color:#888;text-transform:uppercase;'
            f'letter-spacing:0.07em">What actually happened</span><br>{_esc(out_txt)}</div>',
            unsafe_allow_html=True,
        )

    # Reasoning — always visible, no click required
    st.markdown(
        '<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.4rem">'
        '<span style="font-weight:700;font-size:0.95rem">What the AI was thinking</span>'
        '<span style="background:#EAF3EA;color:#3E6B3A;border:1px solid #BBD3B5;'
        'font-size:0.62rem;font-weight:800;'
        'letter-spacing:0.14em;text-transform:uppercase;padding:2px 8px;border-radius:4px">'
        'VERBATIM LLM OUTPUT</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    if reasoning:
        st.markdown(
            f'<div style="background:#FBFAF7;border:1px solid #E4E0D8;'
            f'border-left:5px solid {action_color};'
            f'border-radius:0 8px 8px 0;padding:1.1rem 1.3rem;font-size:0.97rem;'
            f'line-height:1.9;font-style:italic;color:#2A2A38;'
            f'box-shadow:0 2px 10px rgba(0,0,0,0.06)">'
            f'{_esc(reasoning)}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("*(no reasoning logged)*")


def _render_cost_function_expander(persona: Dict) -> None:
    cost_fn = persona.get("cost_function", [])
    if not cost_fn:
        return
    name = persona.get("name", "this agent")
    with st.expander(f"How {name} weighs risks"):
        severity_order = ["catastrophic", "significant", "moderate", "minor", "irrelevant"]
        for sev in severity_order:
            items = [c for c in cost_fn if c.get("severity") == sev]
            for item in items:
                cat = item.get("category", "").replace("_", " ").title()
                badge = _SEVERITY_BADGE.get(sev, sev)
                narrative = item.get("narrative", "")
                st.markdown(
                    f'<div style="border-left:3px solid #CCC;padding:0.3rem 0.8rem;'
                    f'margin:0.3rem 0;font-size:0.9rem">'
                    f'<b>{badge} — {cat}</b><br>'
                    f'<span style="color:#444">{_esc(narrative)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


def _render_decision_history_expander(history: List[Dict]) -> None:
    if len(history) <= 1:
        return
    with st.expander(f"All decisions ({len(history)} total)"):
        for i, rec in enumerate(history):
            action = rec.get("action", "—")
            ts = rec.get("timestamp", 0)
            conf = rec.get("confidence")
            reasoning = rec.get("reasoning", "")
            action_label = _ACTION_LABEL.get(action, action.replace("_", " ").title())
            color = _ACTION_COLOR.get(action, "#AAA")

            st.markdown(
                f'<div style="border-left:3px solid {color};padding:0.3rem 0.7rem;'
                f'margin:0.3rem 0"><b>Decision {i + 1}:</b> T+{ts:.0f}s — {action_label}'
                f'{f" · {conf:.0%} confidence" if conf is not None else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )
            if reasoning:
                st.write(_esc(reasoning))

            snap = rec.get("portfolio_snapshot", {})
            if snap:
                st.caption("Portfolio: " + " · ".join(
                    f"{k.upper()}: &#36;{v:,.0f}" for k, v in sorted(snap.items())
                ))
            if i < len(history) - 1:
                st.markdown("---")


def _render_cb_decision_detail(run: Dict, all_events: List[Dict]) -> None:
    """Detail view for the Central Bank's decision — the demo's strongest moment."""
    cb_events = [e for e in all_events if e.get("event_type") == "central_bank_acted"]
    trigger_events = [e for e in all_events if e.get("event_type") == "central_bank_triggered"]

    metrics = run.get("metrics", {})
    policy_type = metrics.get("cb_policy_type") or (cb_events[0].get("policy_type") if cb_events else None)

    st.subheader("🏛 Central Bank")

    if not cb_events:
        st.info("The Central Bank was configured but never triggered — the cascade threshold was not reached.")
        return

    cb = cb_events[0]
    trigger = trigger_events[0] if trigger_events else {}

    action = cb.get("action", "")
    reasoning = cb.get("reasoning", "")
    announcement = cb.get("announcement_text", "")
    confidence = cb.get("confidence")
    model_used = cb.get("model_used", "")
    ts = cb.get("timestamp", 0)
    cascade_frac = trigger.get("cascade_fraction", 0.0)
    withdrawn_count = trigger.get("withdrawn_count", 0)
    total_agents = trigger.get("total_agents", 0)
    bank_state = trigger.get("bank_state", "healthy")
    reserve_ratio = trigger.get("bank_reserve_ratio", 0.0)

    is_llm = policy_type == "llm"
    policy_badge = "🤖 AI-Powered Central Bank" if is_llm else "📋 Rule-Based Central Bank"
    policy_color = "#1C3A5E" if is_llm else "#4A4A4A"
    policy_bg = "#EEF3FF" if is_llm else "#F5F5F5"

    action_colors = {
        "do_nothing": "#AAAAAA",
        "announce_guarantee": "#4CAF50",
        "inject_liquidity": "#2196F3",
    }
    action_labels = {
        "do_nothing": "Took no action",
        "announce_guarantee": "Announced deposit guarantee",
        "inject_liquidity": "Injected emergency liquidity",
    }
    action_color = action_colors.get(action, "#AAA")
    action_label = action_labels.get(action, action.replace("_", " ").title())

    # Context card
    st.markdown(
        f'<div style="background:{policy_bg};border:1.5px solid {policy_color};border-radius:8px;'
        f'padding:1rem 1.3rem;margin-bottom:1rem">'
        f'<div style="font-weight:700;font-size:1.05rem;color:{policy_color};margin-bottom:0.5rem">'
        f'{policy_badge}</div>'
        f'<div style="font-size:0.9rem;color:#444;line-height:1.8">'
        f'Triggered at <b>T+{ts:.0f}s</b> &nbsp;·&nbsp; '
        f'Cascade: <b>{cascade_frac:.0%}</b> ({withdrawn_count}/{total_agents} withdrew) &nbsp;·&nbsp; '
        f'Bank A: <b>{bank_state}</b> · reserve <b>{reserve_ratio:.0%}</b>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # Action banner
    meta_parts: List[str] = [f"T+{ts:.0f}s"]
    if confidence is not None:
        meta_parts.append(f"confidence {confidence:.0%}")
    short_model = ""
    if model_used and model_used != "rule_based":
        short_model = model_used.split("/")[-1] if "/" in model_used else model_used
        meta_parts.append(short_model)

    st.markdown(
        f'<div style="background:{action_color}22;border-left:5px solid {action_color};'
        f'border-radius:6px;padding:0.6rem 1rem;margin-bottom:0.8rem">'
        f'<span style="font-size:1.05rem;font-weight:700">{action_label}</span>'
        f'<span style="color:#666;font-size:0.85rem;margin-left:1rem">'
        f'{" · ".join(meta_parts)}</span></div>',
        unsafe_allow_html=True,
    )

    # Official announcement text
    if announcement:
        st.markdown("**Official announcement issued**")
        st.markdown(
            f'<div style="background:#F0FFF0;border:1px solid #4CAF50;'
            f'border-radius:6px;padding:0.9rem 1.1rem;font-size:0.93rem;'
            f'line-height:1.75;color:#2C5F2C;margin-bottom:1rem">'
            f'&#8220;{_esc(announcement)}&#8221;</div>',
            unsafe_allow_html=True,
        )

    # LLM reasoning — the centrepiece of the CB view
    if is_llm and reasoning:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.4rem">'
            '<span style="font-weight:700;font-size:0.95rem">What the AI regulator was thinking</span>'
            '<span style="background:#EAF3EA;color:#3E6B3A;border:1px solid #BBD3B5;'
            'font-size:0.62rem;font-weight:800;'
            'letter-spacing:0.14em;text-transform:uppercase;padding:2px 8px;border-radius:4px">'
            'VERBATIM LLM OUTPUT</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="background:#FBFAF7;border:1px solid #E4E0D8;'
            f'border-left:5px solid #4CAF50;'
            f'border-radius:0 8px 8px 0;padding:1.1rem 1.3rem;font-size:0.97rem;'
            f'line-height:1.9;font-style:italic;color:#2A2A38;'
            f'box-shadow:0 2px 10px rgba(0,0,0,0.06)">'
            f'{_esc(reasoning)}</div>',
            unsafe_allow_html=True,
        )
    elif not is_llm:
        st.caption(
            "Rule-based policy: fires automatically when the withdrawal threshold is crossed. "
            "No LLM reasoning — this represents an institution that has not yet adopted AI-speed judgment."
        )

    # Technical call details
    prompt_tokens = cb.get("prompt_tokens", 0)
    completion_tokens = cb.get("completion_tokens", 0)
    cost_usd = cb.get("cost_usd", 0.0)
    if prompt_tokens or completion_tokens:
        with st.expander("CB call details"):
            dc = st.columns(3)
            dc[0].metric("Model", short_model or "—")
            dc[1].metric("Tokens", f"{prompt_tokens + completion_tokens:,}")
            dc[2].metric("Cost", f"${cost_usd:.4f}")


def _render_outcome_ledger_expander(ledger: Dict) -> None:
    start = ledger.get("principal_starting_value", 0.0)
    current = ledger.get("principal_current_value", 0.0)
    net = ledger.get("net_principal_change", 0.0)
    realized = ledger.get("realized_costs", [])
    unrealized = ledger.get("unrealized_outcomes", [])
    tags = ledger.get("outcome_tags", [])

    if not (realized or unrealized or tags):
        return

    with st.expander("Outcome ledger"):
        oc = st.columns(3)
        oc[0].metric("Starting", f"${start:,.0f}")
        oc[1].metric("Final", f"${current:,.0f}", delta=f"${net:,.0f}")
        oc[2].metric("Costs paid", f"${ledger.get('total_realized_cost', 0):,.0f}")

        for rc in realized:
            cat = rc.get("cost_category", "").replace("_", " ").title()
            amt = rc.get("amount", 0)
            desc = rc.get("description", "")
            ts = rc.get("timestamp", 0)
            st.write(_esc(f"- T+{ts:.0f}s · **{cat}**: ${amt:,.2f} — *{desc}*"))

        for uo in unrealized:
            otype = uo.get("outcome_type", "")
            amt = uo.get("amount", 0)
            desc = uo.get("description", "")
            if otype == "would_have_lost":
                st.error(_esc(f"Would have lost **${amt:,.0f}** — *{desc}*"))
            else:
                st.info(_esc(f"Counterfactual: **${amt:,.0f}** — *{desc}*"))


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def _render_run_summary(run: Dict, agents: List[Dict]) -> None:
    """Run-summary strip at the top of Inspect (moved here from the nav sidebar).
    Counts use the same money-moved classification as the agent badges, so the
    headline numbers and the per-agent badges always agree."""
    m = run.get("metrics", {})
    n = len(agents) or m.get("total_agents", 0)
    effs = [_effective_action(a) for a in agents]
    n_full = effs.count("full_withdraw")
    n_partial = effs.count("partial_withdraw")
    n_held = n - n_full - n_partial
    paid = m.get("paid_out_count", 0)
    pct = m.get("final_withdrawal_fraction", 0.0)
    cascade = m.get("cascade_triggered", False)
    was_true = _run_was_true(run)
    verdict = (
        "🔴 rumor was TRUE — the bank really was failing" if was_true is True
        else "🟢 rumor was FALSE — the bank was solvent" if was_true is False
        else "⏳ truth not yet revealed"
    )

    st.markdown(
        f'<div style="background:#F4F2EF;border-radius:10px;padding:1rem 1.3rem;'
        f'margin-bottom:0.9rem">'
        f'<div style="font-size:1.0rem;color:#555;margin-bottom:0.6rem">'
        f'<b style="font-size:1.15rem;color:#1A1A2E">{run.get("scenario_name","—")}</b>'
        f' · {run.get("speed","ai").upper()} speed · {verdict}</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:0.6rem 1.6rem;font-size:1.15rem;'
        f'color:#222;white-space:nowrap">'
        f'<span>🔴 <b>{n_full}</b> fully withdrew</span>'
        f'<span>🟡 <b>{n_partial}</b> partial</span>'
        f'<span>⚫ <b>{n_held}</b> kept money in</span>'
        f'<span>💵 <b>{paid}/{n}</b> got cash</span>'
        f'<span>🏦 Bank A paid out <b>{pct:.0%}</b></span>'
        f'<span>{"🔥 cascade" if cascade else "no cascade"}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


_ACTION_BADGE: Dict[str, str] = {
    "full_withdraw": " 🔴",
    "partial_withdraw": " 🟡",
    "hold": " ⚫",
    "increase_deposit": " 🟢",
}


def _render_agent_grid(
    agent_states: Dict[str, Dict],
    all_events: List[Dict],
    has_cb: bool,
    metrics: Dict,
) -> None:
    """Compact roster across the TOP of the page — one column per archetype —
    so selecting an agent keeps their reasoning (rendered directly below) in view.
    Replaces the old tall left-hand list, which forced a scroll back up to read."""
    selected = st.session_state.get("selected_agent_id")

    # Central Bank entry — its own compact button when a CB was present
    if has_cb:
        cb_acted = any(e.get("event_type") == "central_bank_acted" for e in all_events)
        cb_icon = "🤖" if metrics.get("cb_policy_type") == "llm" else "📋"
        cb_status = " ✅" if cb_acted else " —"
        cb_label = f"{'▶ ' if selected == '__cb__' else ''}{cb_icon} Central Bank{cb_status}"
        cb_col = st.columns([1, 3])[0]
        with cb_col:
            if st.button(cb_label, key="agent_btn___cb__", use_container_width=True):
                st.session_state.selected_agent_id = "__cb__"
                st.rerun()

    archs_present = [
        arch for arch in _ARCHETYPE_ORDER
        if any(a.get("persona", {}).get("archetype") == arch for a in agent_states.values())
    ]
    if not archs_present:
        return

    cols = st.columns(len(archs_present))
    for col, arch in zip(cols, archs_present):
        with col:
            icon = _ARCHETYPE_ICON.get(arch, "👤")
            label = _ARCHETYPE_LABEL.get(arch, arch.replace("_", " ").title())
            st.markdown(
                f'<div style="font-weight:700;font-size:0.82rem;color:#1A1A2E;'
                f'margin-bottom:0.35rem">{icon} {label}</div>',
                unsafe_allow_html=True,
            )
            arch_agents = sorted(
                (a for a in agent_states.values()
                 if a.get("persona", {}).get("archetype") == arch),
                key=lambda a: a["agent_id"],
            )
            for agent in arch_agents:
                aid = agent["agent_id"]
                name = agent.get("persona", {}).get("name", aid)
                badge = _ACTION_BADGE.get(_effective_action(agent), "")
                btn_label = f"{'▶ ' if selected == aid else ''}{name}{badge}"
                if st.button(btn_label, key=f"agent_btn_{aid}", use_container_width=True):
                    st.session_state.selected_agent_id = aid
                    st.rerun()


def render_inspect() -> None:
    st.markdown(
        '<h1 style="font-size:1.6rem;font-weight:900;letter-spacing:-0.02em;'
        'color:#1A1A2E;margin-bottom:0.1rem">Inspect — What Each AI Was Thinking</h1>'
        '<p style="font-size:0.88rem;color:#777;margin-top:0;margin-bottom:1rem">'
        'Pick an agent from the row below — their verbatim LLM reasoning appears right underneath.</p>',
        unsafe_allow_html=True,
    )

    run = st.session_state.get("run_result")
    if run is None:
        st.info("No simulation run yet. Go to **Presets** to run one.")
        return

    agent_states: Dict[str, Dict] = {
        a["agent_id"]: a for a in run.get("agent_final_states", [])
    }
    all_events: List[Dict] = run.get("events", [])

    _render_run_summary(run, list(agent_states.values()))

    # Detect whether this run has a Central Bank
    metrics = run.get("metrics", {})
    has_cb = bool(metrics.get("cb_policy_type"))

    # ── Agent roster: compact grid across the TOP ──────────────────────────
    _render_agent_grid(agent_states, all_events, has_cb, metrics)
    st.caption("🔴 withdrew everything · 🟡 partial · ⚫ kept money in · 🟢 added · ✅ acted")
    st.divider()

    # ── Detail: full width, directly below the roster ──────────────────────
    selected_id = st.session_state.get("selected_agent_id")

    if selected_id == "__cb__":
        _render_cb_decision_detail(run, all_events)
        return

    # Auto-select the most interesting agent when none is chosen:
    # prefer the first mover (earliest withdrawal decision), then any agent.
    if selected_id is None or selected_id not in agent_states:
        first_mover_id = None
        first_mover_ts = float("inf")
        for e in all_events:
            if (e.get("event_type") == "agent_acted"
                    and e.get("action") in ("full_withdraw", "partial_withdraw")):
                if e.get("timestamp", float("inf")) < first_mover_ts:
                    first_mover_ts = e["timestamp"]
                    first_mover_id = e.get("agent_id")
        if first_mover_id:
            st.session_state.selected_agent_id = first_mover_id
            selected_id = first_mover_id
        elif agent_states:
            selected_id = next(iter(agent_states))
            st.session_state.selected_agent_id = selected_id

    agent = agent_states.get(selected_id)
    if agent is None:
        st.warning(f"Agent {selected_id!r} not found in this run.")
        return

    persona = agent.get("persona", {})
    name = persona.get("name", selected_id)
    icon = _ARCHETYPE_ICON.get(persona.get("archetype", ""), "👤")
    history = agent.get("decision_history", [])
    ledger = agent.get("outcome_ledger") or {}
    portfolio = agent.get("portfolio", {})

    st.subheader(f"{icon} {name}")

    # Context card — who this is and what happened, in plain English
    summary = _build_context_summary(
        persona, history, ledger, _effective_action(agent), _run_was_true(run)
    )
    _render_context_card(summary, portfolio)

    # Outcome verdict
    _render_verdict_banner(_effective_action(agent), _run_was_true(run))

    # Latest decision + reasoning — the centerpiece
    _render_latest_decision(agent, history, all_events)

    st.markdown("")

    # Collapsible detail — available but not in the way
    _render_cost_function_expander(persona)
    _render_decision_history_expander(history)
    _render_outcome_ledger_expander(ledger)
