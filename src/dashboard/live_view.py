"""
Live View: scrub through a pre-rendered simulation run.

Layout:
  - Top bar: key metrics (agents withdrew, Bank A reserve, cascade flag)
  - Playback controls: time slider, play/pause, step, speed
  - Left column: Plotly graph (agent nodes + bank nodes + deposit edges)
  - Right column: scrolling event timeline (most-recent first)

The graph reflects agent state at the current scrub position: node color
encodes the last action taken, edge color shows active vs withdrawn deposit.

Playback state is stored in st.session_state["playback_slider"], which is also
the key for the slider widget. This lets auto-play programmatically advance the
slider by setting session_state before st.rerun().
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

_ARCHETYPE_BASE_COLOR: Dict[str, str] = {
    "cautious_retiree": "#4E79A7",
    "aggressive_trader": "#F28E2B",
    "gig_worker": "#59A14F",
    "institutional_treasurer": "#B07AA1",
}

_ACTION_COLOR: Dict[str, str] = {
    "full_withdraw": "#E15759",
    "partial_withdraw": "#F1A340",
    "hold": "#BAB0AC",
    "increase_deposit": "#76B7B2",
}

_ARCHETYPE_ICON: Dict[str, str] = {
    "cautious_retiree": "🧓",
    "aggressive_trader": "📈",
    "gig_worker": "🚗",
    "institutional_treasurer": "🏛️",
}

_ARCHETYPE_ORDER = [
    "cautious_retiree",
    "aggressive_trader",
    "gig_worker",
    "institutional_treasurer",
]

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_live_view() -> None:
    st.header("Live View — Simulation Playback")

    run = st.session_state.get("run_result")
    if run is None:
        st.info("No simulation run yet. Go to **Configure** to run one.")
        return

    events: List[Dict] = run.get("events", [])
    agent_states: Dict[str, Dict] = {a["agent_id"]: a for a in run.get("agent_final_states", [])}
    bank_states: Dict[str, Dict] = {b["bank_id"]: b for b in run.get("bank_final_states", [])}
    metrics: Dict = run.get("metrics", {})

    _TIMELINE_TYPES = {
        "rumor_published", "agent_acted",
        "social_signal_emitted", "rumor_truth_revealed",
        "central_bank_acted",
    }

    # Emit a single card the first time each bank transitions to distressed/suspended
    _seen_bank_states: dict = {}
    _state_transition_events = []
    for _e in events:
        if _e.get("event_type") == "bank_reserve_updated":
            _bid = _e.get("bank_id", "")
            _new = _e.get("new_state", "healthy")
            _prev = _seen_bank_states.get(_bid, "healthy")
            if _new != _prev and _new in ("distressed", "suspended"):
                _state_transition_events.append({**_e, "event_type": "bank_state_transition"})
            _seen_bank_states[_bid] = _new

    timeline_events = [e for e in events if e.get("event_type") in _TIMELINE_TYPES]
    timeline_events.extend(_state_transition_events)
    timeline_events.sort(key=lambda e: e["timestamp"])

    max_time = max((e["timestamp"] for e in events), default=1.0)

    # Ensure playback_slider is initialised
    if "playback_slider" not in st.session_state:
        st.session_state.playback_slider = 0.0

    # ── Auto-play advancement — MUST run before any widget renders ────────
    # Streamlit forbids writing a widget key after the widget is instantiated,
    # so we advance the slider value here, before st.slider() is called below.
    if st.session_state.is_playing:
        current_for_autoplay = st.session_state.playback_slider
        play_speed_val = st.session_state.get("play_speed_select", 1.0)
        future = [e["timestamp"] for e in timeline_events if e["timestamp"] > current_for_autoplay]
        if future:
            next_time = min(future)
            gap = next_time - current_for_autoplay
            sleep_s = min(gap / play_speed_val, 3.0)
            time.sleep(max(sleep_s, 0.2))
            st.session_state.playback_slider = next_time   # safe: slider not rendered yet
        else:
            st.session_state.is_playing = False

    # ── Header + metrics (all time-aware — reflect current scrub position) ─
    # agent_action is built below from events ≤ current_time, but we need the
    # current_time value first. Compute a preliminary version here just for metrics;
    # the same dict is rebuilt identically after the slider renders.
    _preliminary_time = st.session_state.get("playback_slider", 0.0)
    _preliminary_action: Dict[str, Dict] = {}
    for _e in events:
        if _e.get("event_type") == "agent_acted" and _e["timestamp"] <= _preliminary_time:
            _preliminary_action[_e["agent_id"]] = _e

    n = len(agent_states) or metrics.get("total_agents", 0)
    n_ran = sum(
        1 for ev in _preliminary_action.values()
        if ev.get("action") in ("full_withdraw", "partial_withdraw")
    )
    n_held = sum(1 for ev in _preliminary_action.values() if ev.get("action") == "hold")
    n_undecided = n - len(_preliminary_action)

    # Bank A current state
    _ba_state, _ba_rr = _bank_state_at_time(events, "bank_a", _preliminary_time,
                                             bank_states.get("bank_a", {}))
    _state_badge = {"healthy": "🟢 healthy", "distressed": "🟡 distressed",
                    "suspended": "🔴 suspended"}.get(_ba_state, _ba_state)

    speed_label = {"ai": "AI speed", "human": "Human speed"}.get(run.get("speed", ""), run.get("speed", ""))
    st.caption(f"{run.get('scenario_name', '—')}  ·  {speed_label}")

    mc = st.columns(4)
    mc[0].metric("Withdrew", f"{n_ran} / {n}")
    mc[1].metric("Holding", f"{n_held} / {n}")
    mc[2].metric("Yet to decide", f"{n_undecided} / {n}")
    mc[3].metric("Bank A", _state_badge)
    st.divider()

    # ── Playback controls (single compact row) ───────────────────────────
    pb = st.columns([1, 1, 1, 2, 4])
    with pb[0]:
        if st.button("⏮", help="Reset to start"):
            st.session_state.playback_slider = 0.0
            st.session_state.is_playing = False
            st.rerun()
    with pb[1]:
        if st.button("⏸" if st.session_state.is_playing else "▶", help="Play / Pause"):
            st.session_state.is_playing = not st.session_state.is_playing
            st.rerun()
    with pb[2]:
        if st.button("→", help="Step to next event"):
            st.session_state.is_playing = False
            cur = st.session_state.playback_slider
            nxt = [e["timestamp"] for e in timeline_events if e["timestamp"] > cur]
            if nxt:
                st.session_state.playback_slider = min(nxt)
            st.rerun()
    with pb[3]:
        st.select_slider(
            "Speed",
            options=[0.5, 1.0, 2.0, 4.0],
            value=st.session_state.get("play_speed_select", 1.0),
            format_func=lambda x: f"{x}×",
            key="play_speed_select",
            label_visibility="collapsed",
        )
    with pb[4]:
        st.slider(
            "T",
            min_value=0.0,
            max_value=float(max_time),
            step=1.0,
            format="T+%.0fs",
            key="playback_slider",
            label_visibility="collapsed",
        )

    current_time: float = st.session_state.playback_slider

    # ── Reconstruct agent actions at current_time ─────────────────────
    agent_action: Dict[str, Dict] = {}
    for e in events:
        if e.get("event_type") == "agent_acted" and e["timestamp"] <= current_time:
            agent_action[e["agent_id"]] = e

    # ── Main layout ───────────────────────────────────────────────────
    graph_col, timeline_col = st.columns([5, 4])

    with graph_col:
        st.subheader("Agent–Bank Network")
        fig = _build_graph(agent_states, bank_states, agent_action, events, current_time)
        st.plotly_chart(fig, use_container_width=True)
        leg_cols = st.columns(4)
        for col, (label, color) in zip(leg_cols, [
            ("No decision", "#AAAAAA"), ("Full withdraw", "#E15759"),
            ("Partial withdraw", "#F1A340"), ("Hold", "#BAB0AC"),
        ]):
            col.markdown(
                f'<span style="display:inline-block;width:12px;height:12px;'
                f'border-radius:50%;background:{color};margin-right:5px;'
                f'vertical-align:middle"></span><span style="font-size:0.82rem">{label}</span>',
                unsafe_allow_html=True,
            )

    with timeline_col:
        st.subheader("What agents decided")
        visible = [e for e in timeline_events if e["timestamp"] <= current_time]
        if not visible:
            st.caption("No events yet — press Play or drag the slider.")
        else:
            for e in reversed(visible[-20:]):
                _render_timeline_card(e, agent_states, bank_states)

    # ── Auto-play: trigger next tick ──────────────────────────────────
    # The actual advancement happened at the top of this function (before slider
    # rendered). Here we just schedule another rerun if still playing.
    if st.session_state.is_playing:
        st.rerun()


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def _bank_state_at_time(
    events: List[Dict], bank_id: str, current_time: float, fallback: Dict
) -> Tuple[str, float]:
    """Return (state, reserve_ratio) for a bank at current_time."""
    state = "healthy"
    rr = fallback.get("reserve_ratio", 1.0)
    for e in events:
        if (e.get("event_type") == "bank_reserve_updated"
                and e.get("bank_id") == bank_id
                and e.get("timestamp", 9e9) <= current_time):
            state = e.get("new_state", state)
            if e.get("new_reserve_ratio") is not None:
                rr = e["new_reserve_ratio"]
    return state, rr


def _agent_positions(agent_states: Dict[str, Dict]) -> Dict[str, Tuple[float, float]]:
    """Assign fixed (x, y) positions for all agents, grouped by archetype."""
    positions: Dict[str, Tuple[float, float]] = {}

    y_centres = {
        "cautious_retiree": 0.87,
        "aggressive_trader": 0.62,
        "gig_worker": 0.38,
        "institutional_treasurer": 0.13,
    }
    x_base = [0.08, 0.18, 0.28]

    for arch in _ARCHETYPE_ORDER:
        arch_agents = sorted(
            [a for a in agent_states.values() if a.get("persona", {}).get("archetype") == arch],
            key=lambda a: a["agent_id"],
        )
        y_c = y_centres.get(arch, 0.5)
        for i, agent in enumerate(arch_agents):
            x = x_base[i % len(x_base)]
            y = y_c + (i - 1) * 0.08
            positions[agent["agent_id"]] = (x, y)

    return positions


def _build_graph(
    agent_states: Dict[str, Dict],
    bank_states: Dict[str, Dict],
    agent_action: Dict[str, Dict],
    events: List[Dict],
    current_time: float,
) -> go.Figure:
    fig = go.Figure()
    agent_pos = _agent_positions(agent_states)

    bank_pos = {
        "bank_a": (0.80, 0.70),
        "bank_b": (0.80, 0.30),
    }

    # ── Deposit edges ─────────────────────────────────────────────────
    for agent in agent_states.values():
        aid = agent["agent_id"]
        if aid not in agent_pos:
            continue
        ax, ay = agent_pos[aid]

        acted_ev = agent_action.get(aid)
        acted_bank = acted_ev.get("bank_id") if acted_ev else None
        acted_action = acted_ev.get("action") if acted_ev else None

        # Use first decision's portfolio snapshot for initial deposit size
        history = agent.get("decision_history", [])
        if history:
            portfolio = history[0].get("portfolio_snapshot", agent.get("portfolio", {}))
        else:
            portfolio = agent.get("portfolio", {})

        for key, amount in portfolio.items():
            if ":" not in key:
                continue
            bank_id, _ = key.split(":", 1)
            if bank_id not in bank_pos or amount <= 0:
                continue
            bx, by = bank_pos[bank_id]

            withdrew = acted_action in ("full_withdraw", "partial_withdraw") and acted_bank == bank_id
            line_color = "rgba(225, 87, 89, 0.55)" if withdrew else "rgba(120, 120, 120, 0.22)"
            dash = "dash" if withdrew else "solid"
            width = 2.0 if withdrew else 1.0

            fig.add_trace(go.Scatter(
                x=[ax, bx, None],
                y=[ay, by, None],
                mode="lines",
                line=dict(color=line_color, width=width, dash=dash),
                hoverinfo="skip",
                showlegend=False,
            ))

    # ── Bank nodes (time-aware state) ─────────────────────────────────
    for bank_id, (bx, by) in bank_pos.items():
        bs = bank_states.get(bank_id, {})
        name = bs.get("name", bank_id)
        total_dep = bs.get("total_deposits", 0.0)
        state, rr = _bank_state_at_time(events, bank_id, current_time, bs)
        state_color = {
            "healthy": "#2C3E50",
            "distressed": "#E67E22",
            "suspended": "#E74C3C",
        }.get(state, "#2C3E50")

        fig.add_trace(go.Scatter(
            x=[bx],
            y=[by],
            mode="markers+text",
            marker=dict(size=48, color=state_color, symbol="square", line=dict(color="white", width=2)),
            text=[f"🏦 {name}"],
            textposition="top center",
            textfont=dict(size=11),
            hovertemplate=(
                f"<b>{name}</b><br>"
                f"State: {state}<br>"
                f"Reserve ratio: {rr:.1%}<br>"
                f"Total deposits: ${total_dep:,.0f}"
                "<extra></extra>"
            ),
            showlegend=False,
        ))
        fig.add_annotation(
            x=bx, y=by - 0.09,
            text=f"{rr:.0%} reserves  ·  {state}",
            showarrow=False,
            font=dict(size=10, color="#666"),
            xanchor="center",
            xref="x",
            yref="y",
        )

    # ── Agent nodes ───────────────────────────────────────────────────
    for agent in agent_states.values():
        aid = agent["agent_id"]
        if aid not in agent_pos:
            continue
        ax, ay = agent_pos[aid]
        persona = agent.get("persona", {})
        arch = persona.get("archetype", "")
        name = persona.get("name", aid)
        first_name = name.split()[0]
        icon = _ARCHETYPE_ICON.get(arch, "👤")

        acted_ev = agent_action.get(aid)
        color = _ACTION_COLOR.get(acted_ev.get("action", "hold"), "#999") if acted_ev else "#AAAAAA"

        reasoning = (acted_ev.get("reasoning", "") or "") if acted_ev else ""
        hover = f"<b>{name}</b><br>{arch.replace('_', ' ').title()}<br>"
        if acted_ev:
            action_str = acted_ev.get("action", "—").replace("_", " ")
            hover += f"Decision: <b>{action_str}</b>"
            if reasoning:
                hover += f"<br><i>\"{reasoning[:140]}...\"</i>"
        else:
            hover += "Awaiting decision"

        fig.add_trace(go.Scatter(
            x=[ax],
            y=[ay],
            mode="markers+text",
            marker=dict(size=26, color=color, line=dict(color="white", width=2)),
            text=[f"{icon} {first_name}"],
            textposition="bottom center",
            textfont=dict(size=10),
            hovertemplate=hover + "<extra></extra>",
            showlegend=False,
        ))

    fig.update_layout(
        height=560,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(range=[-0.22, 1.05], visible=False),
        yaxis=dict(range=[-0.15, 1.08], visible=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", bordercolor="#ccc", font_size=12),
    )

    # Archetype group labels — pinned to left margin, centred on each group
    for label, y in [
        ("Cautious Retirees", 0.87),
        ("Aggressive Traders", 0.62),
        ("Gig Workers", 0.38),
        ("Institutional Treasurers", 0.13),
    ]:
        fig.add_annotation(
            x=-0.04, y=y,
            text=f"<b>{label}</b>",
            showarrow=False,
            font=dict(size=9, color="#888"),
            xanchor="right",
            xref="x",
            yref="y",
        )

    return fig


# ---------------------------------------------------------------------------
# Timeline event cards
# ---------------------------------------------------------------------------


def _render_timeline_card(event: Dict, agent_states: Dict[str, Dict], bank_states: Dict[str, Dict] = {}) -> None:
    etype = event.get("event_type", "")
    ts = event.get("timestamp", 0.0)
    ts_str = f"T+{ts:.0f}s"

    def _card(bg: str, border: str, body: str) -> None:
        st.markdown(
            f'<div style="background:{bg};border-left:3px solid {border};'
            f'padding:0.6rem 0.9rem;border-radius:4px;margin:0.35rem 0;'
            f'font-size:0.88rem;line-height:1.55">{body}</div>',
            unsafe_allow_html=True,
        )

    if etype == "rumor_published":
        cred = event.get("credibility", 0)
        content = event.get("content", "")
        _card(
            "#F5EDD8", "#C4873A",
            f'<span style="color:#7A5C1E;font-weight:600">{ts_str} — Rumor enters the environment</span>'
            f'<br>Credibility: <b>{cred:.0%}</b>'
            f'<br><span style="font-style:italic">&#8220;{content[:220]}&#8221;</span>',
        )

    elif etype == "agent_acted":
        aid = event.get("agent_id", "")
        agent = agent_states.get(aid, {})
        persona = agent.get("persona", {})
        name = persona.get("name", aid)
        arch = persona.get("archetype", "")
        action = event.get("action", "hold")
        icon = _ARCHETYPE_ICON.get(arch, "👤")
        action_str = action.replace("_", " ")
        border = {"full_withdraw": "#C0392B", "partial_withdraw": "#D4880A", "hold": "#999", "increase_deposit": "#4A6741"}.get(action, "#999")
        bg = {"full_withdraw": "#FAF0EE", "partial_withdraw": "#FBF5EC", "hold": "#F4F2EF", "increase_deposit": "#EEF3EE"}.get(action, "#F4F2EF")
        reasoning = (event.get("reasoning", "") or "")
        # Two sentences max, ~200 chars
        snippet = reasoning[:220].rsplit(" ", 1)[0] + "…" if len(reasoning) > 220 else reasoning

        st.markdown(
            f'<div style="background:{bg};border-left:3px solid {border};'
            f'padding:0.65rem 0.9rem;border-radius:4px;margin:0.4rem 0;line-height:1.6">'
            f'<span style="font-size:0.8rem;color:#666">{ts_str}</span>'
            f'<span style="float:right;font-size:0.8rem;color:#666">{arch.replace("_"," ").title()}</span><br>'
            f'<b>{icon} {name}</b> — <b>{action_str}</b>'
            + (f'<br><span style="font-size:0.87rem;font-style:italic;color:#444">&#8220;{snippet}&#8221;</span>' if snippet else "")
            + "</div>",
            unsafe_allow_html=True,
        )
        key_suffix = (event.get("event_id") or aid or str(ts))[:12]
        if st.button("Read full reasoning →", key=f"goto_{key_suffix}", type="secondary"):
            st.session_state.selected_agent_id = aid
            st.session_state.nav_page = "Inspect"
            st.rerun()

    elif etype == "social_signal_emitted":
        src = event.get("source_agent_id", "?")
        action = event.get("action", "")
        src_agent = agent_states.get(src, {})
        src_name = src_agent.get("persona", {}).get("name", src)
        _card(
            "#EEF0EC", "#8A9E80",
            f'<span style="color:#4A6741;font-weight:600">{ts_str} — Social signal</span>'
            f'<br>{src_name} → <i>{action.replace("_", " ")}</i> — visible to other agents',
        )

    elif etype == "rumor_truth_revealed":
        is_true = event.get("rumor_was_true", False)
        if is_true:
            _card(
                "#FAF0EE", "#C0392B",
                f'<span style="color:#8B1A1A;font-weight:600">{ts_str} — Truth revealed: rumor was TRUE</span>'
                f'<br>Bank A was insolvent. Agents who withdrew avoided real losses.',
            )
        else:
            _card(
                "#EEF3EE", "#4A6741",
                f'<span style="color:#2E4D28;font-weight:600">{ts_str} — Truth revealed: rumor was FALSE</span>'
                f'<br>Bank A was solvent. Agents who withdrew paid fees unnecessarily.',
            )

    elif etype == "central_bank_acted":
        action = event.get("action", "do_nothing")
        policy_type = event.get("policy_type", "llm")
        reasoning = (event.get("reasoning", "") or "")
        snippet = reasoning[:200].rsplit(" ", 1)[0] + "…" if len(reasoning) > 200 else reasoning
        action_label = {
            "announce_guarantee": "issued a deposit guarantee",
            "inject_liquidity":   "injected emergency liquidity",
            "do_nothing":         "monitored but did not intervene",
        }.get(action, action.replace("_", " "))
        policy_badge = "🤖 AI-powered CB" if policy_type == "llm" else "📋 Rule-based CB"
        announcement = event.get("announcement_text", "")
        st.markdown(
            f'<div style="background:#FDF6E3;border-left:4px solid #B8860B;'
            f'padding:0.65rem 0.9rem;border-radius:4px;margin:0.4rem 0;line-height:1.6">'
            f'<span style="font-size:0.8rem;color:#7A6010">{ts_str}</span>'
            f'<span style="float:right;font-size:0.8rem;color:#7A6010">{policy_badge}</span><br>'
            f'<b>🏛 Central Bank</b> — <b>{action_label}</b>'
            + (f'<br><span style="font-size:0.87rem;font-style:italic;color:#5A4E20">'
               f'&#8220;{snippet}&#8221;</span>' if snippet else "")
            + (f'<br><span style="font-size:0.85rem;background:#FFF8DC;padding:2px 6px;'
               f'border-radius:3px;color:#3D2E00">{announcement}</span>'
               if announcement else "")
            + "</div>",
            unsafe_allow_html=True,
        )

    elif etype == "bank_state_transition":
        bank_id = event.get("bank_id", "").replace("_", " ").title()
        new_state = event.get("new_state", "")
        new_ratio = event.get("new_reserve_ratio", 0.0)
        if new_state == "suspended":
            _card(
                "#FAF0EE", "#C0392B",
                f'<span style="color:#8B1A1A;font-weight:600">{ts_str} — {bank_id} suspended</span>'
                f'<br>Reserves exhausted ({new_ratio:.1%}). '
                f'Withdrawal requests after this point received <b>$0</b>.',
            )
        elif new_state == "distressed":
            _card(
                "#FBF5EC", "#D4880A",
                f'<span style="color:#7A4F00;font-weight:600">{ts_str} — {bank_id} under stress</span>'
                f'<br>Reserve ratio dropped to <b>{new_ratio:.1%}</b> — bank is distressed.',
            )
