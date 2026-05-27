"""
Live View — redesigned for narrative impact.

Layout:
  ┌──────────────────────────────────────────────────────────────┐
  │  HEADLINE  (evolves: rumor → cascade → bank suspended →      │
  │            truth revealed)                                   │
  │  Bank A health bar  ████████░░░░░░ 15% · DISTRESSED         │
  │  💰 $629k moved · ⏱ 8.5s · 📊 11/12 fled                   │
  ├────────────────────────────────────────────────────────────  │
  │  ▶▶ Demo  ⏮ ▶  →  speed  ──────── slider ───────────────   │
  ├────────────────────┬─────────────────────────────────────────┤
  │  12 AGENT TILES    │  FEATURED QUOTE  (most recent reasoning)│
  │  (gray → colored   │  ─────────────────────────────────────  │
  │   as decisions     │  WITHDRAWAL CASCADE  (step chart)       │
  │   land)            │  ─────────────────────────────────────  │
  │                    │  RECENT EVENTS  (compact pills)         │
  └────────────────────┴─────────────────────────────────────────┘
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go
import streamlit as st

# ── Style constants ──────────────────────────────────────────────────────────

_ARCHETYPE_ICON: Dict[str, str] = {
    "cautious_retiree":       "🧓",
    "aggressive_trader":      "📈",
    "gig_worker":             "🚗",
    "institutional_treasurer":"🏛️",
}
_ARCHETYPE_ORDER = [
    "cautious_retiree",
    "aggressive_trader",
    "gig_worker",
    "institutional_treasurer",
]
_ARCHETYPE_LABEL: Dict[str, str] = {
    "cautious_retiree":       "Cautious Retirees",
    "aggressive_trader":      "Aggressive Traders",
    "gig_worker":             "Gig Workers",
    "institutional_treasurer":"Institutional Treasurers",
}

# (border_color, background_color, short_label)
_ACTION_STYLE: Dict[str, Tuple[str, str, str]] = {
    "full_withdraw":    ("#E15759", "#FEF0EE", "FLED"),
    "partial_withdraw": ("#F1A340", "#FBF5EC", "PARTIAL"),
    "hold":             ("#4A6741", "#EEF3EE", "HELD"),
    "increase_deposit": ("#4E79A7", "#EEF5FF", "ADDED"),
}
_ACTION_FULL: Dict[str, str] = {
    "full_withdraw":    "WITHDREW EVERYTHING",
    "partial_withdraw": "PARTIALLY WITHDREW",
    "hold":             "HELD POSITION",
    "increase_deposit": "ADDED FUNDS",
}

# ── Public entry point ───────────────────────────────────────────────────────


def render_live_view() -> None:
    run = st.session_state.get("run_result")
    if run is None:
        st.markdown(
            '<div style="text-align:center;padding:4rem;color:#999">'
            '<div style="font-size:3rem;margin-bottom:1rem">🏦</div>'
            '<div style="font-size:1.2rem;font-weight:600;color:#555">No run loaded</div>'
            '<div style="font-size:0.9rem;margin-top:0.5rem">'
            'Go to <b>Presets</b> → load a saved run or run a new scenario</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    events: List[Dict] = run.get("events", [])
    agent_states: Dict[str, Dict] = {
        a["agent_id"]: a for a in run.get("agent_final_states", [])
    }
    bank_states: Dict[str, Dict] = {
        b["bank_id"]: b for b in run.get("bank_final_states", [])
    }
    run_metrics: Dict = run.get("metrics", {})
    max_time: float = max((e["timestamp"] for e in events), default=1.0)
    n: int = len(agent_states) or run_metrics.get("total_agents", 0)

    # Pre-compute initial Bank A deposits per agent (use first decision snapshot)
    agent_ba_dep: Dict[str, float] = {}
    for aid, agent in agent_states.items():
        dh = agent.get("decision_history", [])
        port = (
            dh[0].get("portfolio_snapshot", agent.get("portfolio", {}))
            if dh else agent.get("portfolio", {})
        )
        agent_ba_dep[aid] = sum(
            v for k, v in port.items()
            if k.startswith("bank_a") and isinstance(v, (int, float))
        )

    # ── Playback state ──────────────────────────────────────────────────────
    for _k, _v in [
        ("playback_t", 0.0),
        ("playback_slider", 0.0),
        ("is_playing", False),
        ("play_speed_select", 1.0),
    ]:
        if _k not in st.session_state:
            st.session_state[_k] = _v

    # Detect manual slider scrub before any widget renders
    _slider_pos = float(st.session_state.playback_slider)
    if (not st.session_state.is_playing
            and abs(_slider_pos - st.session_state.playback_t) > 0.5):
        st.session_state.playback_t = _slider_pos

    # Fixed-increment auto-play (~30 frames per run at 1×)
    _FRAME_DT = max(0.1, max_time / 30.0)
    if st.session_state.is_playing:
        _speed = float(st.session_state.play_speed_select)
        _new_t = st.session_state.playback_t + _FRAME_DT * _speed
        if _new_t >= max_time:
            _new_t = max_time
            st.session_state.is_playing = False
        st.session_state.playback_t = _new_t
        st.session_state.playback_slider = _new_t
        time.sleep(0.05)

    # Single source of truth
    current_time: float = st.session_state.playback_t

    # ── All state computed from current_time ────────────────────────────────
    agent_action: Dict[str, Dict] = {}
    for e in events:
        if e.get("event_type") == "agent_acted" and e["timestamp"] <= current_time:
            agent_action[e["agent_id"]] = e

    n_ran = sum(
        1 for ev in agent_action.values()
        if ev.get("action") in ("full_withdraw", "partial_withdraw")
    )
    n_held = sum(1 for ev in agent_action.values() if ev.get("action") == "hold")

    ba_state, ba_rr = _bank_state_at_time(
        events, "bank_a", current_time, bank_states.get("bank_a", {})
    )

    rumor_ev = next(
        (e for e in events if e.get("event_type") == "rumor_published"), None
    )
    rumor_revealed = next(
        (e for e in events
         if e.get("event_type") == "rumor_truth_revealed"
         and e["timestamp"] <= current_time),
        None,
    )
    cb_ev = next(
        (e for e in events
         if e.get("event_type") == "central_bank_acted"
         and e["timestamp"] <= current_time),
        None,
    )

    # Money moved so far
    paid_out = sum(
        e.get("amount_paid_out", 0) for e in events
        if e.get("event_type") == "withdrawal_processed"
        and e["timestamp"] <= current_time
    )

    # ── Render ──────────────────────────────────────────────────────────────
    _render_top_banner(
        run, current_time, max_time, n_ran, n_held, n,
        ba_state, ba_rr, rumor_ev, rumor_revealed, cb_ev,
        agent_action, agent_states, paid_out,
    )
    _render_controls(max_time, events)

    left, right = st.columns([3, 2])
    with left:
        _render_agent_grid(agent_states, agent_action, agent_ba_dep)
    with right:
        _render_right_panel(events, agent_states, current_time, max_time, n)

    if st.session_state.is_playing:
        st.rerun()


# ── Top banner ───────────────────────────────────────────────────────────────


def _render_top_banner(
    run: Dict,
    current_time: float,
    max_time: float,
    n_ran: int,
    n_held: int,
    n: int,
    ba_state: str,
    ba_rr: float,
    rumor_ev: Optional[Dict],
    rumor_revealed: Optional[Dict],
    cb_ev: Optional[Dict],
    agent_action: Dict[str, Dict],
    agent_states: Dict[str, Dict],
    paid_out: float,
) -> None:
    speed = run.get("speed", "ai")
    speed_badge = "⚡ AI speed" if speed == "ai" else "🐢 Human speed"

    # Dynamic headline — evolves with the narrative arc
    if rumor_revealed:
        was_true = rumor_revealed.get("rumor_was_true", False)
        if was_true:
            headline = (
                f"✅ CONFIRMED — Bank A was genuinely failing. "
                f"{n_ran} of {n} agents escaped before collapse."
            )
            hl_color, hl_bg = "#6B1A1A", "#FEF0EE"
        else:
            headline = (
                f"⚠️ FALSE ALARM — {n_ran} of {n} agents ran on a healthy bank. "
                f"The rumor was fabricated."
            )
            hl_color, hl_bg = "#7A4F00", "#FFF8E7"
    elif cb_ev:
        cb_action = cb_ev.get("action", "do_nothing")
        cb_label = {
            "announce_guarantee": "🏛 Central Bank issued deposit guarantee — cascade halted",
            "inject_liquidity":   "🏛 Central Bank injected liquidity — panic easing",
            "do_nothing":         "🏛 Central Bank monitoring — no intervention yet",
        }.get(cb_action, "🏛 Central Bank responded")
        headline = cb_label
        hl_color, hl_bg = "#7A6010", "#FDF6E3"
    elif ba_state == "suspended":
        headline = (
            f"💥 BANK A SUSPENDED — {n_ran} of {n} agents acted. "
            f"Reserves exhausted in {current_time:.1f}s."
        )
        hl_color, hl_bg = "#6B1A1A", "#FEF0EE"
    elif n_ran >= n // 2:
        headline = f"🔥 CASCADE IN PROGRESS — {n_ran} of {n} agents have fled Bank A"
        hl_color, hl_bg = "#7A1A1A", "#FAF0EE"
    elif n_ran > 0:
        # Find first mover
        first = min(
            (e for e in agent_action.values()
             if e.get("action") in ("full_withdraw", "partial_withdraw")),
            key=lambda e: e["timestamp"],
            default=None,
        )
        if first:
            fa_name = agent_states.get(first["agent_id"], {}).get(
                "persona", {}
            ).get("name", "Unknown")
            headline = (
                f"⚡ First move at T+{first['timestamp']:.2f}s — "
                f"{fa_name} → {first['action'].replace('_', ' ')}"
            )
        else:
            headline = f"⚡ {n_ran} agent(s) have acted"
        hl_color, hl_bg = "#5A3A00", "#FBF5EC"
    else:
        cred = rumor_ev.get("credibility", 0) if rumor_ev else 0
        headline = (
            f"📰 Rumor circulating at {cred:.0%} credibility — "
            f"agents are reading…"
        )
        hl_color, hl_bg = "#2C2C2C", "#F4F2EF"

    # Bank A health bar
    rr_pct = max(0, min(100, int(ba_rr * 100)))
    bar_color = {
        "healthy":   "#59A14F",
        "distressed":"#F28E2B",
        "suspended": "#E15759",
    }.get(ba_state, "#59A14F")
    state_label = {
        "healthy":   "HEALTHY",
        "distressed":"⚠ DISTRESSED",
        "suspended": "🔴 SUSPENDED",
    }.get(ba_state, ba_state.upper())

    # Stats row
    paid_str  = f"${paid_out/1e6:.2f}M" if paid_out >= 1e6 else f"${paid_out:,.0f}"
    stats_html = (
        f'<span style="margin-right:1.2rem">💰 <b>{paid_str}</b> moved</span>'
        f'<span style="margin-right:1.2rem">⏱ <b>T+{current_time:.1f}s</b> / {max_time:.0f}s</span>'
        f'<span>👥 <b>{n_ran}</b> fled · <b>{n_held}</b> held · '
        f'<b>{n - n_ran - n_held}</b> deciding</span>'
    )
    if cb_ev:
        cb_type = cb_ev.get("policy_type", "llm")
        cb_badge_label = "🤖 AI CB" if cb_type == "llm" else "📋 Rule CB"
        stats_html += f'<span style="margin-left:1.2rem;background:#FDF6E3;padding:2px 8px;border-radius:10px;border:1px solid #C9A227;font-size:0.78rem">{cb_badge_label} intervened</span>'

    st.markdown(
        f'<div style="background:{hl_bg};border-radius:12px;padding:1rem 1.5rem;'
        f'margin-bottom:0.5rem;border:1.5px solid rgba(0,0,0,0.06)">'
        # Headline row
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        f'margin-bottom:0.75rem;gap:1rem">'
        f'<span style="font-size:1.1rem;font-weight:700;color:{hl_color};line-height:1.4">'
        f'{headline}</span>'
        f'<span style="font-size:0.75rem;background:white;border-radius:20px;'
        f'padding:3px 10px;color:#666;font-weight:500;white-space:nowrap;flex-shrink:0">'
        f'{speed_badge}</span>'
        f'</div>'
        # Bank health bar
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:0.55rem">'
        f'<span style="font-size:0.75rem;color:#666;font-weight:600;white-space:nowrap">'
        f'Bank A reserves</span>'
        f'<div style="flex:1;height:16px;background:#E0E0E0;border-radius:8px;overflow:hidden">'
        f'<div style="height:100%;width:{rr_pct}%;background:{bar_color};border-radius:8px">'
        f'</div></div>'
        f'<span style="font-size:0.8rem;font-weight:700;color:{bar_color};white-space:nowrap">'
        f'{rr_pct}% · {state_label}</span>'
        f'</div>'
        # Stats row
        f'<div style="font-size:0.8rem;color:#666">{stats_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Playback controls ────────────────────────────────────────────────────────


def _render_controls(max_time: float, events: List[Dict]) -> None:
    nav_ts = sorted(
        e["timestamp"] for e in events
        if e.get("event_type") in (
            "rumor_published", "agent_acted", "bank_state_transition",
            "rumor_truth_revealed", "central_bank_acted",
        )
    )

    current_time = st.session_state.playback_t

    pb = st.columns([1.8, 0.65, 0.65, 0.65, 1.8, 4.8])
    with pb[0]:
        if st.button("▶▶ Demo", type="primary", help="Reset to T=0 and play at 0.5×"):
            st.session_state.playback_t = 0.0
            st.session_state.playback_slider = 0.0
            st.session_state.is_playing = True
            st.session_state.play_speed_select = 0.5
            st.rerun()
    with pb[1]:
        if st.button("⏮", help="Reset to start"):
            st.session_state.playback_t = 0.0
            st.session_state.playback_slider = 0.0
            st.session_state.is_playing = False
            st.rerun()
    with pb[2]:
        _playing = st.session_state.is_playing
        if st.button("⏸" if _playing else "▶", help="Play / Pause"):
            st.session_state.is_playing = not _playing
            st.rerun()
    with pb[3]:
        if st.button("→", help="Step to next event"):
            st.session_state.is_playing = False
            nxt = [t for t in nav_ts if t > current_time]
            if nxt:
                _t = min(nxt)
                st.session_state.playback_t = _t
                st.session_state.playback_slider = _t
            st.rerun()
    with pb[4]:
        st.select_slider(
            "Speed", options=[0.25, 0.5, 1.0, 2.0, 4.0],
            value=st.session_state.play_speed_select,
            format_func=lambda x: f"{x}×",
            key="play_speed_select",
            label_visibility="collapsed",
        )
    with pb[5]:
        st.slider(
            "T", min_value=0.0, max_value=float(max_time), step=1.0,
            format="T+%.0fs", key="playback_slider", label_visibility="collapsed",
        )


# ── Agent tile grid ──────────────────────────────────────────────────────────


def _render_agent_grid(
    agent_states: Dict[str, Dict],
    agent_action: Dict[str, Dict],
    agent_ba_dep: Dict[str, float],
) -> None:
    groups: Dict[str, List] = {arch: [] for arch in _ARCHETYPE_ORDER}
    for agent in agent_states.values():
        arch = agent.get("persona", {}).get("archetype", "")
        if arch in groups:
            groups[arch].append(agent)
    for arch in groups:
        groups[arch].sort(key=lambda a: a["agent_id"])

    parts: List[str] = ['<div style="padding:2px 0">']

    for arch in _ARCHETYPE_ORDER:
        agents = groups[arch]
        icon = _ARCHETYPE_ICON.get(arch, "👤")
        label = _ARCHETYPE_LABEL.get(arch, arch)

        parts.append(
            f'<div style="font-size:0.68rem;font-weight:700;color:#999;'
            f'text-transform:uppercase;letter-spacing:0.09em;margin:10px 0 5px">'
            f'{icon} {label}</div>'
            f'<div style="display:flex;gap:7px;margin-bottom:2px">'
        )

        for agent in agents:
            aid = agent["agent_id"]
            persona = agent.get("persona", {})
            name = persona.get("name", aid)
            first = name.split()[0]
            deposit = agent_ba_dep.get(aid, 0)
            dep_str = f"${deposit:,.0f}" if deposit >= 1000 else f"${deposit:.0f}"

            acted_ev = agent_action.get(aid)
            if acted_ev:
                action = acted_ev.get("action", "hold")
                ts = acted_ev.get("timestamp", 0)
                border_c, bg_c, short = _ACTION_STYLE.get(
                    action, ("#999", "#F4F2EF", action[:6].upper())
                )
                parts.append(
                    f'<div style="flex:1;background:{bg_c};border:2px solid {border_c};'
                    f'border-radius:10px;padding:9px 7px;min-width:0;text-align:center">'
                    f'<div style="font-size:1.1rem;margin-bottom:1px">{icon}</div>'
                    f'<div style="font-weight:700;font-size:0.82rem;color:#111;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{first}</div>'
                    f'<div style="font-size:0.65rem;color:{border_c};font-weight:800;'
                    f'text-transform:uppercase;letter-spacing:0.05em;margin:3px 0">{short}</div>'
                    f'<div style="font-size:0.65rem;color:#888">T+{ts:.1f}s</div>'
                    f'</div>'
                )
            else:
                parts.append(
                    f'<div style="flex:1;background:#F3F3F3;border:2px dashed #D0D0D0;'
                    f'border-radius:10px;padding:9px 7px;min-width:0;text-align:center;'
                    f'opacity:0.6">'
                    f'<div style="font-size:1.1rem;margin-bottom:1px">{icon}</div>'
                    f'<div style="font-weight:700;font-size:0.82rem;color:#999;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{first}</div>'
                    f'<div style="font-size:0.62rem;color:#bbb;margin:3px 0">{dep_str}</div>'
                    f'<div style="font-size:0.62rem;color:#ccc">deciding…</div>'
                    f'</div>'
                )

        for _ in range(3 - len(agents)):
            parts.append('<div style="flex:1"></div>')

        parts.append("</div>")

    # Legend
    parts.append(
        '<div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:10px">'
        '<span style="font-size:0.7rem;color:#999">░░ deciding</span>'
        '<span style="font-size:0.7rem;color:#E15759">■ FLED</span>'
        '<span style="font-size:0.7rem;color:#F1A340">■ PARTIAL</span>'
        '<span style="font-size:0.7rem;color:#4A6741">■ HELD</span>'
        '</div>'
    )
    parts.append("</div>")

    st.markdown("".join(parts), unsafe_allow_html=True)


# ── Right panel: featured quote + cascade chart + event pills ────────────────


def _render_right_panel(
    events: List[Dict],
    agent_states: Dict[str, Dict],
    current_time: float,
    max_time: float,
    n: int,
) -> None:
    # ── Featured reasoning quote ──────────────────────────────────────────
    acted = sorted(
        (e for e in events
         if e.get("event_type") == "agent_acted"
         and e["timestamp"] <= current_time
         and (e.get("reasoning") or "").strip()),
        key=lambda e: e["timestamp"],
        reverse=True,
    )

    if acted:
        ev = acted[0]
        aid = ev.get("agent_id", "")
        agent = agent_states.get(aid, {})
        persona = agent.get("persona", {})
        name = persona.get("name", aid)
        arch = persona.get("archetype", "")
        action = ev.get("action", "hold")
        ts = ev.get("timestamp", 0)
        icon = _ARCHETYPE_ICON.get(arch, "👤")

        reasoning = (ev.get("reasoning") or "").strip()
        # Keep up to ~380 chars, ending on a sentence boundary
        if len(reasoning) > 380:
            sents = reasoning.split(". ")
            trimmed = ""
            for s in sents:
                candidate = (trimmed + ". " + s) if trimmed else s
                if len(candidate) <= 380:
                    trimmed = candidate
                else:
                    break
            reasoning = (trimmed.rstrip(".") + "…") if trimmed else reasoning[:380] + "…"

        border_c, bg_c, _ = _ACTION_STYLE.get(action, ("#999", "#F4F2EF", ""))
        action_full = _ACTION_FULL.get(action, action.upper())

        st.markdown(
            f'<div style="background:{bg_c};border-left:5px solid {border_c};'
            f'border-radius:0 10px 10px 0;padding:1rem 1.1rem;margin-bottom:0.9rem">'
            # Header row
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;margin-bottom:0.35rem">'
            f'<span style="font-weight:700;font-size:0.95rem;color:#111">'
            f'{icon} {name}</span>'
            f'<span style="font-size:0.68rem;color:{border_c};font-weight:800;'
            f'text-transform:uppercase;letter-spacing:0.06em;background:white;'
            f'border:1.5px solid {border_c};border-radius:10px;padding:2px 8px">'
            f'{action_full}</span>'
            f'</div>'
            f'<div style="font-size:0.72rem;color:#999;margin-bottom:0.65rem">'
            f'{arch.replace("_"," ").title()} · T+{ts:.2f}s</div>'
            f'<div style="font-size:0.87rem;line-height:1.7;color:#1a1a1a;font-style:italic">'
            f'&#8220;{reasoning}&#8221;</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#F4F2EF;border-radius:10px;padding:1.8rem;'
            'text-align:center;color:#aaa;margin-bottom:0.9rem">'
            '<div style="font-size:2rem;margin-bottom:0.4rem">🤔</div>'
            '<div style="font-size:0.88rem;font-weight:600;color:#888">'
            'Agents are processing the rumor</div>'
            '<div style="font-size:0.78rem;margin-top:0.35rem">'
            'Press ▶▶ Demo to watch reasoning unfold</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Cascade chart ─────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#666;'
        'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:2px">'
        'Withdrawal Cascade</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        _build_cascade_chart(events, current_time, max_time, n),
        use_container_width=True,
    )

    # ── Recent event pills ────────────────────────────────────────────────
    _render_event_pills(events, agent_states, current_time)


def _build_cascade_chart(
    events: List[Dict],
    current_time: float,
    max_time: float,
    n: int,
) -> go.Figure:
    withdrew_at: Dict[str, float] = {}
    for e in events:
        if e.get("event_type") == "agent_acted":
            aid = e.get("agent_id", "")
            action = e.get("action", "")
            ts = e.get("timestamp", 0.0)
            if action in ("full_withdraw", "partial_withdraw") and aid not in withdrew_at:
                withdrew_at[aid] = ts

    fig = go.Figure()

    if withdrew_at:
        sorted_ts = sorted(withdrew_at.values())
        # Full ghost line (faded, shows future path)
        ghost_x = [0.0] + sorted_ts + [sorted_ts[-1]]
        ghost_y = [0] + list(range(1, len(sorted_ts) + 1)) + [len(sorted_ts)]
        fig.add_trace(go.Scatter(
            x=ghost_x, y=ghost_y,
            mode="lines",
            line=dict(color="rgba(225,87,89,0.15)", width=2, shape="hv"),
            showlegend=False,
            hoverinfo="skip",
        ))

        # Solid line up to current_time
        visible = [ts for ts in sorted_ts if ts <= current_time]
        if visible:
            vx = [0.0] + visible + [current_time]
            vy = [0] + list(range(1, len(visible) + 1)) + [len(visible)]
            fig.add_trace(go.Scatter(
                x=vx, y=vy,
                mode="lines+markers",
                line=dict(color="#E15759", width=3, shape="hv"),
                marker=dict(size=5, color="#E15759"),
                showlegend=False,
                hovertemplate="T+%{x:.2f}s — %{y} fled<extra></extra>",
            ))

    # Current-time cursor
    fig.add_vline(
        x=current_time,
        line=dict(color="#333", width=1.5, dash="dot"),
        annotation_text=f"now",
        annotation_position="top right",
        annotation_font_size=9,
        annotation_font_color="#666",
    )

    fig.update_layout(
        height=190,
        margin=dict(l=0, r=5, t=15, b=30),
        xaxis=dict(
            title=dict(text="seconds", font=dict(size=9, color="#888")),
            range=[0, max_time * 1.05],
            gridcolor="rgba(0,0,0,0.05)",
            tickfont=dict(size=9),
            tickcolor="#ccc",
        ),
        yaxis=dict(
            title=dict(text="agents fled", font=dict(size=9, color="#888")),
            range=[0, n + 0.5],
            dtick=max(1, n // 4),
            gridcolor="rgba(0,0,0,0.05)",
            tickfont=dict(size=9),
            tickcolor="#ccc",
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _render_event_pills(
    events: List[Dict],
    agent_states: Dict[str, Dict],
    current_time: float,
) -> None:
    relevant_types = {
        "rumor_published", "agent_acted", "bank_state_transition",
        "rumor_truth_revealed", "central_bank_acted",
    }
    visible = sorted(
        (e for e in events
         if e.get("event_type") in relevant_types
         and e.get("timestamp", 0) <= current_time),
        key=lambda e: e["timestamp"],
        reverse=True,
    )[:8]

    if not visible:
        return

    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#666;'
        'text-transform:uppercase;letter-spacing:0.08em;margin:6px 0 5px">'
        'Recent events</div>',
        unsafe_allow_html=True,
    )

    pills: List[str] = []
    for e in visible:
        ts = e.get("timestamp", 0)
        etype = e.get("event_type", "")

        if etype == "rumor_published":
            cred = e.get("credibility", 0)
            pills.append(
                f'<div style="background:#F5EDD8;border:1px solid #C4873A;border-radius:6px;'
                f'padding:5px 9px;font-size:0.75rem;white-space:nowrap">'
                f'<span style="color:#7A5C1E;font-weight:600">T+{ts:.0f}s</span> '
                f'📰 Rumor ({cred:.0%})</div>'
            )
        elif etype == "agent_acted":
            aid = e.get("agent_id", "")
            action = e.get("action", "hold")
            agent = agent_states.get(aid, {})
            first = agent.get("persona", {}).get("name", aid).split()[0]
            icon_map = {"full_withdraw": "🔴", "partial_withdraw": "🟠", "hold": "🟢"}
            icon = icon_map.get(action, "⚪")
            border_c = _ACTION_STYLE.get(action, ("#999", "", ""))[0]
            pills.append(
                f'<div style="background:white;border:1px solid {border_c};border-radius:6px;'
                f'padding:5px 9px;font-size:0.75rem;white-space:nowrap">'
                f'<span style="color:#888">T+{ts:.1f}s</span> '
                f'{icon} <b>{first}</b> {action.replace("_"," ")}</div>'
            )
        elif etype == "bank_state_transition":
            bank = e.get("bank_id", "").replace("_", " ").title()
            new_st = e.get("new_state", "")
            emoji = "💥" if new_st == "suspended" else "⚠️"
            pills.append(
                f'<div style="background:#FEF0EE;border:1px solid #E15759;border-radius:6px;'
                f'padding:5px 9px;font-size:0.75rem;white-space:nowrap">'
                f'<span style="color:#888">T+{ts:.0f}s</span> '
                f'{emoji} {bank} {new_st}</div>'
            )
        elif etype == "rumor_truth_revealed":
            was_true = e.get("rumor_was_true", False)
            pills.append(
                f'<div style="background:{"#FEF0EE" if was_true else "#EEF3EE"};'
                f'border:1px solid {"#E15759" if was_true else "#4A6741"};border-radius:6px;'
                f'padding:5px 9px;font-size:0.75rem;white-space:nowrap">'
                f'<span style="color:#888">T+{ts:.0f}s</span> '
                f'{"❌ Rumor TRUE" if was_true else "✅ Rumor FALSE"}</div>'
            )
        elif etype == "central_bank_acted":
            pills.append(
                f'<div style="background:#FDF6E3;border:1px solid #C9A227;border-radius:6px;'
                f'padding:5px 9px;font-size:0.75rem;white-space:nowrap">'
                f'<span style="color:#888">T+{ts:.0f}s</span> '
                f'🏛 CB intervened</div>'
            )

    if pills:
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:5px">'
            + "".join(pills)
            + "</div>",
            unsafe_allow_html=True,
        )


# ── Utility ──────────────────────────────────────────────────────────────────


def _bank_state_at_time(
    events: List[Dict],
    bank_id: str,
    current_time: float,
    fallback: Dict,
) -> Tuple[str, float]:
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
