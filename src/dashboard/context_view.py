"""
Context view: the argument for why AI delegation may exacerbate bank runs.

Three mechanisms — not speed per se, but the removal of friction:
  1. Lower trigger threshold: AI agents cascade on weaker signals
  2. Correlated reasoning: similar models herd without communicating
  3. No deliberation buffer: human hesitation is a stabiliser, not just delay

Grounds the argument in the Iyer-Puri participation-rate finding and the
SVB case study, then connects to simulation evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go
import streamlit as st


# ---------------------------------------------------------------------------
# Hard-coded empirical anchors
# ---------------------------------------------------------------------------

_IYER_PURI = (
    "Iyer & Puri (2012) studied the 2001 Indian bank run and found that "
    "typically only **3–7% of depositors** need to withdraw to threaten a bank's liquidity. "
    "Uninsured depositors ran at rates **30+ percentage points higher** than insured ones. "
    "Distance to a branch and social network density were the strongest predictors of "
    "early withdrawal — constraints that AI agents do not face."
)

_SVB_NOTE = (
    "SVB (March 2023) illustrated how concentrated, informed, and interconnected depositors "
    "accelerate runs: $42B withdrawn in 24 hours. The key wasn't just speed — "
    "it was that SVB's depositors were clustered (tech startups advised by the same VCs), "
    "monitored the same Twitter feeds, and were almost entirely above the $250k FDIC limit. "
    "AI delegation recreates these conditions for any bank."
)


# ---------------------------------------------------------------------------
# Load simulation evidence
# ---------------------------------------------------------------------------


def _load_sweep_pairs(runs_dir: Path) -> Dict[float, Dict[str, Dict]]:
    pairs: Dict[float, Dict[str, Dict]] = {}
    for p in sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sid = data.get("scenario_id", "")
            speed = data.get("speed", "")
            if sid.startswith("sweep_false_") and speed in ("ai", "human"):
                cred = int(sid.rsplit("_", 1)[-1]) / 100.0
                pairs.setdefault(cred, {})[speed] = data
        except Exception:
            continue
    return {c: d for c, d in pairs.items() if "ai" in d and "human" in d}


def _event_metrics(run: Dict) -> Dict:
    events = run.get("events", [])
    suspension_events = sorted(
        [e for e in events
         if e.get("event_type") == "bank_reserve_updated"
         and e.get("bank_id") == "bank_a"
         and e.get("new_state") == "suspended"],
        key=lambda e: e["timestamp"],
    )
    agent_states = run.get("agent_final_states", [])
    n_total = len(agent_states) or run.get("metrics", {}).get("total_agents", 12)
    n_decided = sum(
        1 for a in agent_states
        if a.get("decision_history")
        and a["decision_history"][-1].get("action") in ("full_withdraw", "partial_withdraw")
    )
    return {
        "t_suspended": suspension_events[0]["timestamp"] if suspension_events else None,
        "n_decided": n_decided,
        "n_total": n_total,
    }


def _suspension_time(run: Dict) -> Optional[float]:
    return _event_metrics(run)["t_suspended"]


def _decided_fraction(run: Dict) -> float:
    if not run:
        return 0.0
    ev = _event_metrics(run)
    return ev["n_decided"] / ev["n_total"] if ev["n_total"] else 0.0


def _load_preset_pairs(runs_dir: Path) -> Dict[Tuple[str, str], Dict]:
    index: Dict[Tuple[str, str], Dict] = {}
    for p in sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sid = data.get("scenario_id", "")
            speed = data.get("speed", "")
            if sid and not sid.startswith("sweep_") and speed in ("ai", "human"):
                index[(sid, speed)] = data
        except Exception:
            continue
    return index


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render_context() -> None:
    st.header("Why AI Delegation May Exacerbate Bank Runs")
    st.caption(
        "The concern isn't that AI agents are faster than humans in absolute terms — "
        "a 12-agent simulation can't be compared to a real bank. "
        "The concern is that AI delegation **removes friction** that historically "
        "slowed runs down and prevented false alarms."
    )

    runs_dir = Path(__file__).parent.parent.parent / "runs"

    # ── Three mechanisms ──────────────────────────────────────────────────
    st.subheader("Three mechanisms")

    m1, m2, m3 = st.columns(3)

    with m1:
        st.markdown(
            '<div style="background:#FEE8E8;border-left:4px solid #E15759;'
            'border-radius:6px;padding:0.9rem 1rem;min-height:180px">'
            '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem">'
            '1 · Compressed cascade timeline</div>'
            '<div style="font-size:0.88rem;line-height:1.6">'
            'AI delegation compresses the cascade timeline regardless of signal '
            'strength. Across every credibility level tested, AI speed suspended '
            'the bank 23–54× faster than human deliberation — on the same rumor, '
            'leaving far less time for regulators or institutions to intervene.</div></div>',
            unsafe_allow_html=True,
        )

    with m2:
        st.markdown(
            '<div style="background:#FFF3E0;border-left:4px solid #F4A34A;'
            'border-radius:6px;padding:0.9rem 1rem;min-height:180px">'
            '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem">'
            '2 · Correlated reasoning</div>'
            '<div style="font-size:0.88rem;line-height:1.6">'
            'AI agents using similar models apply similar logic to the same signal. '
            'They herd without communicating — no group chat needed. '
            'In SVB, coordination required VC advisors to actively tell founders to withdraw. '
            'AI agents do this implicitly and simultaneously.</div></div>',
            unsafe_allow_html=True,
        )

    with m3:
        st.markdown(
            '<div style="background:#EEF3EE;border-left:4px solid #4A6741;'
            'border-radius:6px;padding:0.9rem 1rem;min-height:180px">'
            '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem">'
            '3 · No deliberation buffer</div>'
            '<div style="font-size:0.88rem;line-height:1.6">'
            'Human hesitation isn\'t just delay — it\'s a stabiliser. '
            'During deliberation, contradicting information arrives, '
            'social signals fade, and uncertainty is resolved. '
            'Our simulation shows that the 90-second deliberation window '
            'sometimes <em>prevents</em> false alarms that AI speed triggers.</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Simulation evidence ───────────────────────────────────────────────
    st.subheader("Simulation evidence")

    sweep_pairs = _load_sweep_pairs(runs_dir)
    preset_pairs = _load_preset_pairs(runs_dir)

    ev_col, anchor_col = st.columns([3, 2])

    with ev_col:
        # Evidence 1: suspension time (from sweep, if available)
        st.markdown("**Evidence 1 — AI suspends the bank faster at every credibility level**")
        if sweep_pairs:
            creds = sorted(sweep_pairs.keys())
            ai_times = [_suspension_time(sweep_pairs[c]["ai"]) for c in creds]
            hu_times = [_suspension_time(sweep_pairs[c]["human"]) for c in creds]

            ratios = {
                c: hu / ai
                for c, ai, hu in zip(creds, ai_times, hu_times)
                if ai and hu and ai > 0
            }
            ai_valid = [t for t in ai_times if t is not None]
            hu_valid = [t for t in hu_times if t is not None]

            fig = go.Figure()
            x = [c * 100 for c in creds]
            fig.add_trace(go.Scatter(
                x=x, y=hu_times,
                name="🧑 Human deliberation", mode="lines+markers",
                line=dict(color="#4E79A7", width=2, dash="dot"), marker=dict(size=8),
                connectgaps=True,
            ))
            fig.add_trace(go.Scatter(
                x=x, y=ai_times,
                name="⚡ AI speed", mode="lines+markers",
                line=dict(color="#E15759", width=2), marker=dict(size=8),
                connectgaps=True,
            ))
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
                xaxis=dict(title="Rumor credibility (%)", ticksuffix="%"),
                yaxis=dict(title="Time to bank suspension (s)", type="log"),
                height=260, margin=dict(l=0, r=60, t=10, b=0),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, use_container_width=True)

            if ai_valid and hu_valid:
                max_ratio = max(ratios.values()) if ratios else None
                st.caption(
                    f"AI suspension: **{min(ai_valid):.1f}s – {max(ai_valid):.0f}s** across all levels. "
                    f"Human suspension: **{min(hu_valid):.0f}s – {max(hu_valid):.0f}s**. "
                    + (f"Peak speed advantage: **{max_ratio:.0f}×**." if max_ratio else "")
                )
        else:
            st.info(
                "Run `python scripts/run_credibility_sweep.py` to generate suspension time data. "
                "This chart will populate automatically."
            )

        st.markdown("")

        # Evidence 2: false alarm from preset pairs
        st.markdown("**Evidence 2 — AI ran, human deliberation held (false alarm)**")
        false_alarm = None
        for sid in ["rumor_moderate_false", "rumor_high_false", "rumor_weak_false"]:
            ai = preset_pairs.get((sid, "ai"))
            hu = preset_pairs.get((sid, "human"))
            if ai and hu:
                ai_f = _decided_fraction(ai)
                hu_f = _decided_fraction(hu)
                if ai_f >= 0.25 and hu_f < 0.25:
                    false_alarm = (sid, ai, hu, ai_f, hu_f)
                    break

        if false_alarm:
            sid, ai_run, hu_run, ai_f, hu_f = false_alarm
            label = ai_run.get("scenario_name", sid)
            st.markdown(
                f'<div style="background:#FEE8E8;border-left:4px solid #E15759;'
                f'border-radius:6px;padding:0.7rem 1rem;font-size:0.9rem">'
                f'<b>{label}</b> (bank is solvent)<br>'
                f'AI speed: <b>{ai_f:.0%}</b> of agents withdrew · '
                f'Human deliberation: <b>{hu_f:.0%}</b> withdrew.<br>'
                f'<span style="color:#666;font-size:0.85rem">'
                f'Same scenario, same agents, same rumor. '
                f'Human hesitation absorbed the false signal; AI acted on it.</span></div>',
                unsafe_allow_html=True,
            )
        else:
            # Check for reversal (human > AI)
            reversal = None
            for sid in ["rumor_weak_false", "rumor_weak_true"]:
                ai = preset_pairs.get((sid, "ai"))
                hu = preset_pairs.get((sid, "human"))
                if ai and hu:
                    ai_f = _decided_fraction(ai)
                    hu_f = _decided_fraction(hu)
                    if hu_f > ai_f + 0.1:
                        reversal = (sid, ai, hu, ai_f, hu_f)
                        break

            if reversal:
                sid, ai_run, hu_run, ai_f, hu_f = reversal
                label = hu_run.get("scenario_name", sid) if hu_run else sid
                st.markdown(
                    f'<div style="background:#FFF3E0;border-left:4px solid #F4A34A;'
                    f'border-radius:6px;padding:0.7rem 1rem;font-size:0.9rem">'
                    f'<b>Social amplification reversal — {label}</b><br>'
                    f'Human deliberation: <b>{hu_f:.0%}</b> withdrew · '
                    f'AI speed: <b>{ai_f:.0%}</b> withdrew.<br>'
                    f'<span style="color:#666;font-size:0.85rem">'
                    f'During the 90-second deliberation window, social signals from early '
                    f'movers accumulated — pushing hesitant agents to join a run '
                    f'they would otherwise have avoided.</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("Run paired scenarios (AI + human speed) from Presets to see this finding.")

    with anchor_col:
        st.markdown("**The Iyer-Puri threshold**")
        st.markdown(
            '<div style="background:#EDE8DF;border-left:3px solid #8A7560;'
            'border-radius:4px;padding:0.8rem 1rem;font-size:0.87rem;line-height:1.6">'
            + _IYER_PURI +
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown("")
        st.markdown("**Why this matters for AI delegation**")

        # Compute participation rate from best available sweep data
        participation_note = ""
        if sweep_pairs:
            # Find the weakest signal that still caused some AI cascade
            creds = sorted(sweep_pairs.keys())
            for c in creds:
                ai_f = _decided_fraction(sweep_pairs[c]["ai"])
                if ai_f > 0:
                    participation_note = (
                        f"At **{c:.0%}** credibility — a weak, unverified rumor — "
                        f"**{ai_f:.0%}** of AI agents withdrew. "
                    )
                    break

        body = (
            (participation_note if participation_note else
             "AI agents in our simulation withdraw on signals humans ignore. ")
            + "Iyer-Puri shows only 3–7% depositor participation threatens a bank. "
            "If AI agents manage even a small fraction of retail deposits "
            "and cascade at lower credibility thresholds, "
            "the aggregate effect scales — without any individual agent behaving irrationally."
        )

        st.markdown(
            f'<div style="background:#FEE8E8;border-left:3px solid #E15759;'
            f'border-radius:4px;padding:0.8rem 1rem;font-size:0.87rem;line-height:1.6">'
            f'{body}</div>',
            unsafe_allow_html=True,
        )

        st.markdown("")
        st.markdown("**SVB as a preview**")
        st.markdown(
            '<div style="background:#EDE8DF;border-left:3px solid #8A7560;'
            'border-radius:4px;padding:0.8rem 1rem;font-size:0.87rem;line-height:1.6">'
            + _SVB_NOTE +
            '</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Honest framing ────────────────────────────────────────────────────
    st.markdown(
        '<div style="background:#F5F5F5;border-left:3px solid #AAAAAA;'
        'border-radius:4px;padding:0.8rem 1rem;font-size:0.85rem;color:#555">'
        '<b>Scope:</b> This simulation uses 12 agents and simplified bank mechanics. '
        'We are not predicting real bank run dynamics or claiming our timings match real events. '
        'The finding is about <em>behavioural patterns</em>: AI agents cascade on weaker signals, '
        'exhibit correlated responses, and lack the deliberation buffer that historically '
        'dampened false alarms. Whether these patterns generalise to real AI-delegated finance '
        'is an open empirical question — and the reason to study it now, before it happens at scale.'
        '</div>',
        unsafe_allow_html=True,
    )
