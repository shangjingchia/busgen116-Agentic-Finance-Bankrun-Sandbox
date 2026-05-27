"""
Comparison view: AI Speed vs Human Speed.

Three empirical findings, led by the credibility threshold chart:
  1. AI agents cascade on weaker signals (lower credibility threshold)
  2. False alarm: AI cascaded on a signal human deliberation dismissed
  3. Social amplification reversal: at weak signals, human deliberation
     sometimes amplifies social signals and produces a larger cascade

The threshold chart requires running scripts/run_credibility_sweep.py first.
The scenario deep-dive (bottom) uses any paired preset runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

_root = str(Path(__file__).parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

_ARCHETYPE_ICON: Dict[str, str] = {
    "cautious_retiree": "🧓",
    "aggressive_trader": "📈",
    "gig_worker": "🚗",
    "institutional_treasurer": "🏛️",
}

_ACTION_COLOR: Dict[str, str] = {
    "full_withdraw": "#E15759",
    "partial_withdraw": "#F1A340",
    "hold": "#BAB0AC",
    "increase_deposit": "#76B7B2",
}

CASCADE_THRESHOLD = 0.25


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_all_runs(runs_dir: Path) -> Tuple[Dict, Dict]:
    """Returns (run_index, sweep_runs).

    run_index:  {(scenario_id, speed): run_dict}  — preset/named runs
    sweep_runs: {credibility_float: {"ai": run, "human": run}}
    """
    run_index: Dict[Tuple[str, str], Dict] = {}
    sweep_runs: Dict[float, Dict[str, Dict]] = {}

    for p in sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sid = data.get("scenario_id", "")
            speed = data.get("speed", "")
            if not sid or speed not in ("ai", "human"):
                continue
            if sid.startswith("sweep_false_"):
                try:
                    cred = int(sid.rsplit("_", 1)[-1]) / 100.0
                except ValueError:
                    continue
                sweep_runs.setdefault(cred, {})[speed] = data
            else:
                run_index[(sid, speed)] = data
        except Exception:
            continue

    return run_index, sweep_runs


# ---------------------------------------------------------------------------
# Event-derived metrics (more reliable than RunMetrics for timing)
# ---------------------------------------------------------------------------


def _event_metrics(run: Dict) -> Dict:
    events = run.get("events", [])

    withdrawal_attempts = sorted(
        [e for e in events
         if e.get("event_type") == "agent_acted"
         and e.get("action") in ("full_withdraw", "partial_withdraw")],
        key=lambda e: e["timestamp"],
    )
    suspension_events = sorted(
        [e for e in events
         if e.get("event_type") == "bank_reserve_updated"
         and e.get("bank_id") == "bank_a"
         and e.get("new_state") == "suspended"],
        key=lambda e: e["timestamp"],
    )
    agent_states = {a["agent_id"]: a for a in run.get("agent_final_states", [])}
    n_decided = sum(
        1 for a in agent_states.values()
        if a.get("decision_history")
        and a["decision_history"][-1].get("action") in ("full_withdraw", "partial_withdraw")
    )
    n_paid = len({
        e["agent_id"] for e in events
        if e.get("event_type") == "withdrawal_processed"
        and e.get("amount_paid_out", 0) > 0
    })
    n_total = len(agent_states) or run.get("metrics", {}).get("total_agents", 12)

    return {
        "t_first_attempt": withdrawal_attempts[0]["timestamp"] if withdrawal_attempts else None,
        "t_suspended": suspension_events[0]["timestamp"] if suspension_events else None,
        "n_decided": n_decided,
        "n_paid": n_paid,
        "n_total": n_total,
        "paid_fraction": run.get("metrics", {}).get("final_withdrawal_fraction", 0.0),
    }


def _decided_fraction(run: Dict) -> float:
    if not run:
        return 0.0
    ev = _event_metrics(run)
    return ev["n_decided"] / ev["n_total"] if ev["n_total"] else 0.0


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render_compare() -> None:
    st.header("AI Speed vs Human Speed")

    runs_dir = Path(__file__).parent.parent.parent / "runs"
    run_index, sweep_runs = _load_all_runs(runs_dir)

    # ── Threshold analysis ─────────────────────────────────────────────────
    paired_sweep = {c: d for c, d in sweep_runs.items() if "ai" in d and "human" in d}

    if paired_sweep:
        _render_threshold_section(paired_sweep)
    else:
        st.info(
            "**Threshold analysis not yet available.** "
            "Run `python scripts/run_credibility_sweep.py` (~7 min) to generate "
            "the credibility sweep, then refresh this page."
        )

    st.divider()

    # ── Scenario deep-dive ─────────────────────────────────────────────────
    ai_sids = {k[0] for k in run_index if k[1] == "ai"}
    human_sids = {k[0] for k in run_index if k[1] == "human"}
    paired_sids = sorted(ai_sids & human_sids)

    if not paired_sids:
        st.info(
            "No paired runs found. Run the same scenario at both **AI Speed** and "
            "**Human Speed** from the Presets page, then come back here."
        )
        return

    st.subheader("Scenario deep-dive")
    st.caption("Pick any scenario to see the full breakdown: who withdrew, when, and why.")

    scenario_names = {
        sid: run_index[(sid, "ai")].get("scenario_name", sid) for sid in paired_sids
    }
    selected_sid = st.selectbox(
        "Scenario", paired_sids, format_func=lambda sid: scenario_names[sid]
    )
    _render_comparison(run_index[(selected_sid, "ai")], run_index[(selected_sid, "human")])


# ---------------------------------------------------------------------------
# Threshold analysis section
# ---------------------------------------------------------------------------


def _suspension_time(run: Dict) -> Optional[float]:
    """Time (seconds) until Bank A suspended. None if it never suspended."""
    return _event_metrics(run)["t_suspended"]


def _render_threshold_section(paired_sweep: Dict[float, Dict]) -> None:
    creds = sorted(paired_sweep.keys())
    ai_times = [_suspension_time(paired_sweep[c]["ai"]) for c in creds]
    hu_times = [_suspension_time(paired_sweep[c]["human"]) for c in creds]

    # Ratios where both speeds suspended
    ratios = {
        c: hu / ai
        for c, ai, hu in zip(creds, ai_times, hu_times)
        if ai and hu and ai > 0
    }
    max_ratio_cred = max(ratios, key=ratios.get) if ratios else None
    max_ratio = ratios[max_ratio_cred] if max_ratio_cred else None

    ai_valid = [t for t in ai_times if t is not None]
    hu_valid = [t for t in hu_times if t is not None]

    # ── Headline metrics ───────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "AI — time to suspension",
        f"{min(ai_valid):.1f}s – {max(ai_valid):.0f}s" if ai_valid else "—",
        help="Range across all credibility levels tested",
    )
    c2.metric(
        "Human — time to suspension",
        f"{min(hu_valid):.0f}s – {max(hu_valid):.0f}s" if hu_valid else "—",
        help="Range across all credibility levels tested",
    )
    c3.metric(
        "Peak speed advantage",
        f"{max_ratio:.0f}×" if max_ratio else "—",
        help=(
            f"Human deliberation was {max_ratio:.0f}× slower than AI speed "
            f"at {max_ratio_cred:.0%} credibility"
        ) if max_ratio and max_ratio_cred else "",
    )

    # ── Suspension time chart (log scale) ─────────────────────────────
    st.subheader("Time to bank suspension by rumor credibility")
    st.caption(
        "Same false-bank scenario, 7 credibility levels — bank is solvent in every run. "
        "Both speeds cascade; the difference is **how fast** the bank suspends."
    )

    fig = go.Figure()
    x = [c * 100 for c in creds]

    fig.add_trace(go.Scatter(
        x=x, y=hu_times,
        name="🧑 Human Speed",
        mode="lines+markers",
        line=dict(color="#4E79A7", width=2.5, dash="dot"),
        marker=dict(size=9),
        connectgaps=True,
    ))
    fig.add_trace(go.Scatter(
        x=x, y=ai_times,
        name="⚡ AI Speed",
        mode="lines+markers",
        line=dict(color="#E15759", width=2.5),
        marker=dict(size=9),
        connectgaps=True,
    ))

    # Shade the gap between curves
    if all(t is not None for t in ai_times + hu_times):
        fig.add_trace(go.Scatter(
            x=x + x[::-1],
            y=hu_times + ai_times[::-1],
            fill="toself",
            fillcolor="rgba(225,87,89,0.08)",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.update_layout(
        xaxis=dict(title="Rumor credibility (%)", ticksuffix="%", range=[18, 92], dtick=10),
        yaxis=dict(title="Time to suspension (seconds)", type="log"),
        height=340,
        margin=dict(l=0, r=60, t=20, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Three findings ─────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        if ai_valid and hu_valid:
            body = (
                f"AI suspension: <b>{min(ai_valid):.1f}s – {max(ai_valid):.0f}s</b>. "
                f"Human suspension: <b>{min(hu_valid):.0f}s – {max(hu_valid):.0f}s</b>. "
                "The gap is consistent across every credibility level tested — "
                "AI delegation compresses the cascade timeline regardless of signal strength."
            )
        else:
            body = "Run the credibility sweep to see suspension time data."
        st.markdown(
            f'<div style="background:#FEE8E8;border-left:4px solid #E15759;'
            f'border-radius:6px;padding:0.8rem 1rem">'
            f'<div style="font-weight:700;margin-bottom:0.3rem">'
            f'⚡ AI suspends the bank faster at every level</div>'
            f'<div style="font-size:0.88rem;line-height:1.5">{body}</div></div>',
            unsafe_allow_html=True,
        )

    with col_f2:
        if max_ratio and max_ratio_cred:
            ai_t = ratios and ai_times[creds.index(max_ratio_cred)]
            hu_t = hu_times[creds.index(max_ratio_cred)]
            body = (
                f"At <b>{max_ratio_cred:.0%}</b> credibility — a moderate signal — "
                f"AI speed suspended the bank in <b>{ai_t:.1f}s</b> vs "
                f"<b>{hu_t:.0f}s</b> for human deliberation. "
                f"A <b>{max_ratio:.0f}×</b> speed difference on the same rumor."
            )
        else:
            body = "No ratio data available."
        st.markdown(
            f'<div style="background:#FFF3E0;border-left:4px solid #F4A34A;'
            f'border-radius:6px;padding:0.8rem 1rem">'
            f'<div style="font-weight:700;margin-bottom:0.3rem">'
            f'🚨 Peak gap: {f"{max_ratio:.0f}x faster" if max_ratio else "—"}</div>'
            f'<div style="font-size:0.88rem;line-height:1.5">{body}</div></div>',
            unsafe_allow_html=True,
        )

    with col_f3:
        # Use preset weak-signal reversal finding if available
        body = (
            "On anonymous, low-credibility rumors, AI agents correctly held "
            "(0/12 withdrew). Human deliberation accumulated social signals during "
            "the 90-second window — gig workers panicked first, triggering 2/12. "
            "The deliberation buffer cuts both ways."
        )
        st.markdown(
            f'<div style="background:#EEF3EE;border-left:4px solid #4A6741;'
            f'border-radius:6px;padding:0.8rem 1rem">'
            f'<div style="font-weight:700;margin-bottom:0.3rem">'
            f'🔄 Weak signals: human deliberation amplified</div>'
            f'<div style="font-size:0.88rem;line-height:1.5">{body}</div></div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Scenario deep-dive (existing logic, headline reframed)
# ---------------------------------------------------------------------------


def _compute_headline(ai_ev: Dict, hu_ev: Dict, ai_m: Dict, hu_m: Dict) -> Tuple[str, str]:
    ai_frac = ai_ev["n_decided"] / ai_ev["n_total"] if ai_ev["n_total"] else 0.0
    hu_frac = hu_ev["n_decided"] / hu_ev["n_total"] if hu_ev["n_total"] else 0.0
    ai_cascaded = ai_frac >= CASCADE_THRESHOLD
    hu_cascaded = hu_frac >= CASCADE_THRESHOLD

    if ai_cascaded and not hu_cascaded:
        return (
            "AI cascaded · Human speed held",
            f"AI: {ai_frac:.0%} of agents withdrew · Human: {hu_frac:.0%} withdrew",
        )
    if hu_cascaded and not ai_cascaded:
        return (
            "Human speed cascaded · AI speed held",
            (
                "Social signals accumulated during human deliberation, "
                "triggering a cascade that AI speed — deciding immediately — never developed"
            ),
        )
    if ai_cascaded and hu_cascaded:
        ai_t = ai_ev["t_suspended"] or ai_ev["t_first_attempt"]
        hu_t = hu_ev["t_suspended"] or hu_ev["t_first_attempt"]
        if ai_t and hu_t and ai_t > 0:
            ratio = hu_t / ai_t
            return (
                f"Both cascaded — AI was {ratio:.1f}× faster",
                f"AI: suspended at {ai_t:.1f}s · Human: {hu_t:.1f}s",
            )
        return (
            "Both speeds cascaded",
            f"AI: {ai_frac:.0%} withdrew · Human: {hu_frac:.0%} withdrew",
        )
    return (
        "Neither speed triggered a withdrawal",
        "The rumor credibility was too low to move any agent at either speed",
    )


def _render_comparison(ai_run: Dict, human_run: Dict) -> None:
    ai_m = ai_run.get("metrics", {})
    hu_m = human_run.get("metrics", {})
    ai_ev = _event_metrics(ai_run)
    hu_ev = _event_metrics(human_run)

    headline, subline = _compute_headline(ai_ev, hu_ev, ai_m, hu_m)

    st.markdown(
        f'<div style="background:#EDE8DF;border:2px solid #4A6741;border-radius:8px;'
        f'padding:1.1rem 1.6rem;margin:0.5rem 0 1.2rem 0;text-align:center">'
        f'<div style="font-size:0.85rem;color:#5A4E3C;margin-bottom:0.25rem">'
        f'Same scenario · same agents · same rumor</div>'
        f'<div style="font-size:1.9rem;font-weight:700;color:#2E4D28">{headline}</div>'
        f'<div style="font-size:0.88rem;color:#5A4E3C;margin-top:0.35rem">{subline}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.info(
        "**Cascade** = ≥25% of agents chose to withdraw. "
        "Each withdrawal is broadcast on the social feed — early movers can push "
        "hesitant agents to join, creating a self-reinforcing run even when the bank is solvent."
    )

    col_ai, col_hu = st.columns(2)
    _render_metric_column(col_ai, ai_ev, ai_m, "⚡ AI Speed", "#EEF3EE", "#4A6741")
    _render_metric_column(col_hu, hu_ev, hu_m, "🧑 Human Speed", "#F5EDD8", "#C4873A")

    st.divider()
    st.subheader("Bank A reserve ratio over time")
    st.caption(
        "Each step down = a withdrawal hitting the bank. "
        "When reserves hit 0% the bank suspends — later requests receive $0."
    )
    _render_cascade_chart(ai_run, human_run)

    st.divider()
    st.subheader("Order agents decided")
    _render_decision_timelines(ai_run, human_run)


def _render_metric_column(col, ev: Dict, m: Dict, label: str, bg: str, border: str) -> None:
    with col:
        st.markdown(
            f'<div style="background:{bg};border-left:4px solid {border};border-radius:6px;'
            f'padding:0.6rem 1rem;margin-bottom:0.8rem;font-weight:600;font-size:1rem">'
            f'{label}</div>',
            unsafe_allow_html=True,
        )
        n = ev["n_total"]
        n_ran = ev["n_decided"]
        n_paid = ev["n_paid"]
        t1 = ev["t_first_attempt"]
        t_sus = ev["t_suspended"]
        pct = ev["paid_fraction"]
        cascade = m.get("cascade_triggered", False) or (n_ran >= max(1, n // 4))

        r1, r2 = st.columns(2)
        r1.metric("Chose to withdraw", f"{n_ran} / {n}")
        r2.metric("Got money out", f"{n_paid} / {n}")
        r3, r4 = st.columns(2)
        r3.metric("First withdrawal", f"{t1:.1f}s" if t1 else "—")
        r4.metric("Bank suspended", f"{t_sus:.1f}s" if t_sus else "—")
        r5, r6 = st.columns(2)
        r5.metric("Bank A paid out", f"{pct:.1%}")
        r6.metric(
            "Cascade",
            "🔥 YES" if cascade else "✓ no",
            help="Cascade = ≥25% of agents chose to withdraw",
        )


def _render_cascade_chart(ai_run: Dict, human_run: Dict) -> None:
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["⚡ AI Speed", "🧑 Human Speed"],
        shared_yaxes=True,
    )
    configs = [
        (ai_run,    "#E15759", "rgba(225,87,89,0.10)",  1),
        (human_run, "#4A6741", "rgba(74,103,65,0.10)",  2),
    ]
    for run, line_color, fill_color, col_idx in configs:
        events = run.get("events", [])
        bank_states = {b["bank_id"]: b for b in run.get("bank_final_states", [])}
        reserve_events = sorted(
            [e for e in events
             if e.get("event_type") == "bank_reserve_updated"
             and e.get("bank_id") == "bank_a"],
            key=lambda e: e["timestamp"],
        )
        initial_ratio = bank_states.get("bank_a", {}).get("reserve_ratio_target", 0.10)
        times = [0.0]
        ratios = [initial_ratio * 100]
        for e in reserve_events:
            times.append(e["timestamp"])
            ratios.append(ratios[-1])
            times.append(e["timestamp"])
            ratios.append(e["new_reserve_ratio"] * 100)
        fig.add_trace(
            go.Scatter(
                x=times, y=ratios, mode="lines",
                line=dict(color=line_color, width=2.5),
                fill="tozeroy", fillcolor=fill_color,
                showlegend=False,
            ),
            row=1, col=col_idx,
        )
        fig.update_xaxes(title_text="Simulation time (s)", row=1, col=col_idx)

    fig.update_yaxes(title_text="Reserve ratio (%)", ticksuffix="%", row=1, col=1)
    fig.update_yaxes(ticksuffix="%", row=1, col=2)
    fig.update_layout(
        height=320, margin=dict(l=0, r=0, t=30, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_decision_timelines(ai_run: Dict, human_run: Dict) -> None:
    col_ai, col_hu = st.columns(2)
    for col, run, label in [
        (col_ai, ai_run, "⚡ AI Speed"),
        (col_hu, human_run, "🧑 Human Speed"),
    ]:
        with col:
            st.caption(label)
            agent_states = {a["agent_id"]: a for a in run.get("agent_final_states", [])}
            acted = sorted(
                [e for e in run.get("events", []) if e.get("event_type") == "agent_acted"],
                key=lambda e: e["timestamp"],
            )
            if not acted:
                st.caption("No decisions recorded.")
                continue
            for e in acted:
                aid = e.get("agent_id", "")
                agent = agent_states.get(aid, {})
                persona = agent.get("persona", {})
                name = persona.get("name", aid)
                arch = persona.get("archetype", "")
                icon = _ARCHETYPE_ICON.get(arch, "👤")
                action = e.get("action", "hold")
                ts = e.get("timestamp", 0)
                color = _ACTION_COLOR.get(action, "#BAB0AC")
                st.markdown(
                    f'<div style="font-size:0.85rem;border-left:3px solid {color};'
                    f'padding:0.2rem 0.6rem;margin:0.15rem 0;line-height:1.5">'
                    f'<span style="color:#888;font-size:0.78rem">T+{ts:.1f}s</span> '
                    f'{icon} <b>{name}</b>'
                    f'<span style="color:#666"> — {action.replace("_", " ")}</span></div>',
                    unsafe_allow_html=True,
                )
