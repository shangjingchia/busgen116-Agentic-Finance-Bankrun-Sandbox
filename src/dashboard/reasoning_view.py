"""
Inspect view: click any agent, read their full LLM reasoning.

Layout:
  Left col  (1/3): Agent roster grouped by archetype with outcome badges.
  Right col (2/3): Context card (who + stakes) → verdict → decision →
                   reasoning (all immediately visible). Technical detail
                   in collapsible expanders below.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st


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

_OUTCOME_TAG_LABEL: Dict[str, str] = {
    "avoided_crisis": "✅ Got out in time — bank really was failing",
    "panicked_unnecessarily": "⚠️ Withdrew unnecessarily — bank was actually fine",
    "ignored_real_warning": "🔴 Stayed in — missed a real warning",
    "acted_appropriately": "✅ Made the right call",
    "partial_response": "🟡 Partial response",
}

_OUTCOME_PLAIN: Dict[str, str] = {
    "avoided_crisis": "the bank really was failing — they got out in time",
    "panicked_unnecessarily": "the bank was actually fine",
    "ignored_real_warning": "the bank was genuinely in trouble",
    "acted_appropriately": "",
    "partial_response": "",
}

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
    tags: List[str],
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

    # What they did
    last_action = history[-1].get("action") if history else None
    action_verb = {
        "full_withdraw": "withdrew everything",
        "partial_withdraw": "made a partial withdrawal",
        "hold": "chose to hold",
        "increase_deposit": "increased their deposit",
    }.get(last_action, "took no action")

    # Outcome in plain English
    tag = tags[0] if tags else None
    verdict = _OUTCOME_PLAIN.get(tag, "")

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
    deposits = f"Bank A: ${bank_a:,.0f}"
    if bank_b > 0:
        deposits += f" · Bank B: ${bank_b:,.0f}"

    # Narrative sentence: "She withdrew everything — the bank was fine."
    narrative = action_verb.capitalize()
    if verdict:
        narrative += f" — {verdict}."
    else:
        narrative += "."

    stakes_html = (
        '<div style="font-size:0.88rem;color:#555;font-style:italic;margin-bottom:0.4rem">'
        + stakes + "</div>"
    ) if stakes else ""

    st.markdown(
        '<div style="background:#F0F4FF;border:1.5px solid #4E79A7;border-radius:8px;'
        'padding:1rem 1.3rem;margin-bottom:1rem">'
        '<div style="font-weight:700;font-size:1.05rem;color:#1C3A5E;margin-bottom:0.3rem">'
        f'{arch_label} &nbsp;·&nbsp; {deposits}'
        '</div>'
        '<div style="font-size:0.92rem;color:#333;line-height:1.65;margin-bottom:0.4rem">'
        f'{bg}'
        '</div>'
        + stakes_html +
        '<div style="font-size:0.92rem;font-weight:600;color:#1C3A5E">'
        f'{narrative}'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_verdict_banner(tags: List[str]) -> None:
    if not tags:
        return
    tag_label = _OUTCOME_TAG_LABEL.get(tags[0], tags[0])
    is_good = "✅" in tag_label
    is_warn = "⚠️" in tag_label
    bg = "#E8F4EA" if is_good else "#FFF3E0" if is_warn else "#FEE8E8"
    border = "#4A6741" if is_good else "#C4873A" if is_warn else "#E15759"
    st.markdown(
        f'<div style="background:{bg};border-left:4px solid {border};'
        f'border-radius:6px;padding:0.5rem 1rem;margin-bottom:0.8rem;font-weight:600">'
        f'{tag_label}</div>',
        unsafe_allow_html=True,
    )


def _render_latest_decision(
    history: List[Dict],
    all_events: List[Dict],
) -> None:
    """Decision banner + reasoning — the centerpiece."""
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

    # Action banner
    meta_parts = [f"T+{ts:.0f}s"]
    meta_parts.append(f"Bank A: {bank_state}")
    if conf is not None:
        meta_parts.append(f"confidence {conf:.0%}")
    if trigger:
        meta_parts.append(f"triggered by {trigger}")

    st.markdown(
        f'<div style="background:{action_color}22;border-left:5px solid {action_color};'
        f'border-radius:6px;padding:0.6rem 1rem;margin-bottom:0.8rem">'
        f'<span style="font-size:1.05rem;font-weight:700">{action_label}</span>'
        f'<span style="color:#666;font-size:0.85rem;margin-left:1rem">'
        f'{" · ".join(meta_parts)}'
        f'</span></div>',
        unsafe_allow_html=True,
    )

    # Reasoning — always visible, no click required
    st.markdown("**What the AI was thinking**")
    if reasoning:
        st.markdown(
            f'<div style="background:#FAFAFA;border:1px solid #E0E0E0;'
            f'border-radius:6px;padding:0.9rem 1.1rem;font-size:0.93rem;'
            f'line-height:1.75;font-style:italic;color:#2C2C2C">'
            f'{reasoning}</div>',
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
                    f'<span style="color:#444">{narrative}</span>'
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
                st.write(reasoning)

            snap = rec.get("portfolio_snapshot", {})
            if snap:
                st.caption("Portfolio: " + " · ".join(
                    f"{k.upper()}: ${v:,.0f}" for k, v in sorted(snap.items())
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
            f'&#8220;{announcement}&#8221;</div>',
            unsafe_allow_html=True,
        )

    # LLM reasoning — the centrepiece of the CB view
    if is_llm and reasoning:
        st.markdown("**What the AI regulator was thinking**")
        st.markdown(
            f'<div style="background:#FAFAFA;border:1px solid #E0E0E0;'
            f'border-radius:6px;padding:0.9rem 1.1rem;font-size:0.93rem;'
            f'line-height:1.75;font-style:italic;color:#2C2C2C">'
            f'{reasoning}</div>',
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
            st.write(f"- T+{ts:.0f}s · **{cat}**: ${amt:,.2f} — *{desc}*")

        for uo in unrealized:
            otype = uo.get("outcome_type", "")
            amt = uo.get("amount", 0)
            desc = uo.get("description", "")
            if otype == "would_have_lost":
                st.error(f"Would have lost **${amt:,.0f}** — *{desc}*")
            else:
                st.info(f"Counterfactual: **${amt:,.0f}** — *{desc}*")


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render_inspect() -> None:
    st.header("Inspect — Agent Reasoning")

    run = st.session_state.get("run_result")
    if run is None:
        st.info("No simulation run yet. Go to **Presets** to run one.")
        return

    agent_states: Dict[str, Dict] = {
        a["agent_id"]: a for a in run.get("agent_final_states", [])
    }
    all_events: List[Dict] = run.get("events", [])

    list_col, detail_col = st.columns([1, 2], gap="medium")

    # Detect whether this run has a Central Bank
    metrics = run.get("metrics", {})
    has_cb = bool(metrics.get("cb_policy_type"))

    # ── Agent roster ──────────────────────────────────────────────────────
    with list_col:
        st.subheader("Agents")

        # Central Bank entry — shown at top when CB was present in this run
        if has_cb:
            cb_acted = any(e.get("event_type") == "central_bank_acted" for e in all_events)
            cb_policy = metrics.get("cb_policy_type", "")
            cb_icon = "🤖" if cb_policy == "llm" else "📋"
            cb_status = " ✅" if cb_acted else " —"
            is_cb_selected = st.session_state.get("selected_agent_id") == "__cb__"
            cb_btn_label = f"{'▶ ' if is_cb_selected else ''}{cb_icon} Central Bank{cb_status}"
            if st.button(cb_btn_label, key="agent_btn___cb__", use_container_width=True):
                st.session_state.selected_agent_id = "__cb__"
                st.rerun()
            st.caption("  intervened" if cb_acted else "  threshold not reached")
            st.divider()

        for arch in _ARCHETYPE_ORDER:
            arch_agents = [
                a for a in agent_states.values()
                if a.get("persona", {}).get("archetype") == arch
            ]
            if not arch_agents:
                continue

            icon = _ARCHETYPE_ICON.get(arch, "👤")
            label = _ARCHETYPE_LABEL.get(arch, arch.replace("_", " ").title())
            st.markdown(f"**{icon} {label}**")

            for agent in sorted(arch_agents, key=lambda a: a["agent_id"]):
                aid = agent["agent_id"]
                persona = agent.get("persona", {})
                name = persona.get("name", aid)

                history = agent.get("decision_history", [])
                last_action = history[-1].get("action") if history else None

                ledger = agent.get("outcome_ledger") or {}
                tags = ledger.get("outcome_tags", [])

                action_badge = {
                    "full_withdraw": " 🔴",
                    "partial_withdraw": " 🟡",
                    "hold": " ⚫",
                    "increase_deposit": " 🟢",
                }.get(last_action, "") if last_action else ""

                is_selected = st.session_state.selected_agent_id == aid
                btn_label = f"{'▶ ' if is_selected else ''}{name}{action_badge}"

                if st.button(btn_label, key=f"agent_btn_{aid}", use_container_width=True):
                    st.session_state.selected_agent_id = aid
                    st.rerun()

                if tags:
                    tag_short = {
                        "panicked_unnecessarily": "panicked unnecessarily",
                        "acted_appropriately": "acted appropriately",
                        "avoided_crisis": "avoided crisis",
                        "ignored_real_warning": "ignored warning",
                        "partial_response": "partial response",
                    }.get(tags[0], tags[0])
                    st.caption(f"  {tag_short}")

            st.divider()

    # ── Agent detail ──────────────────────────────────────────────────────
    with detail_col:
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
        tags = ledger.get("outcome_tags", [])
        portfolio = agent.get("portfolio", {})

        st.subheader(f"{icon} {name}")

        # Context card — who this is and what happened, in plain English
        summary = _build_context_summary(persona, history, ledger, tags)
        _render_context_card(summary, portfolio)

        # Outcome verdict
        _render_verdict_banner(tags)

        # Latest decision + reasoning — the centerpiece
        _render_latest_decision(history, all_events)

        st.markdown("")

        # Collapsible detail — available but not in the way
        _render_cost_function_expander(persona)
        _render_decision_history_expander(history)
        _render_outcome_ledger_expander(ledger)
