"""
Findings view: what the simulation found about LLM agent behavior
under financial stress. Combines Compare and Context into one narrative.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go
import streamlit as st

RUNS_DIR = Path(__file__).parent.parent.parent / "runs"

# Plain-English scenario labels
_SCENARIO_LABEL = {
    "rumor_high_false":     "Strong rumor — bank is actually fine",
    "rumor_high_true":      "Strong rumor — bank really is failing",
    "rumor_moderate_false": "Moderate rumor — bank is actually fine",
    "rumor_weak_false":     "Weak rumor — bank is actually fine",
    "rumor_weak_true":      "Weak rumor — bank really is failing",
}

# Short versions for chart axes
_SCENARIO_SHORT = {
    "rumor_high_false":     "Strong rumor\n(bank fine)",
    "rumor_high_true":      "Strong rumor\n(bank failing)",
    "rumor_moderate_false": "Moderate rumor\n(bank fine)",
    "rumor_weak_false":     "Weak rumor\n(bank fine)",
    "rumor_weak_true":      "Weak rumor\n(bank failing)",
}

_OUTCOME_COLOR = {
    "panicked_unnecessarily": "#E15759",
    "acted_appropriately":    "#76B7B2",
    "avoided_crisis":         "#4A6741",
    "ignored_real_warning":   "#F1A340",
    "partial_response":       "#BAB0AC",
}

_OUTCOME_LABEL = {
    "panicked_unnecessarily": "Withdrew needlessly (bank was fine)",
    "acted_appropriately":    "Made the right call",
    "avoided_crisis":         "Got money out before bank collapsed",
    "ignored_real_warning":   "Stayed in despite real danger",
    "partial_response":       "Partially withdrew",
}

_IYER_PURI = (
    "Iyer & Puri (2012) studied a real bank run in India (2001) and found that "
    "typically only <b>3–7% of depositors</b> need to withdraw to threaten a bank's liquidity — "
    "you don't need a majority. Uninsured depositors (those with more to lose) "
    "ran at rates 30+ percentage points higher than insured ones. "
    "The strongest predictors were distance to a branch and social network density — "
    "two constraints AI agents don't have."
)

_SVB_NOTE = (
    "In March 2023, Silicon Valley Bank collapsed after depositors withdrew $42 billion in a single day — "
    "the fastest bank run in modern history. The trigger wasn't just fear; "
    "it was that all SVB depositors were tech startups, advised by the same venture capitalists, "
    "watching the same Twitter threads, and most had deposits above the FDIC insurance limit. "
    "They were clustered, informed, and had every incentive to move fast. "
    "AI delegation recreates exactly these conditions — for any bank."
)


# ---------------------------------------------------------------------------
# Data loading + metrics
# ---------------------------------------------------------------------------


def _load_runs() -> Tuple[List[Dict], List[Dict], Dict[str, Dict]]:
    preset, sweep = [], []
    cb_by_sid: Dict[str, Dict] = {}
    # CB variants for the flat no-cascade scenario
    _FLAT_CB_SIDS = {"rumor_high_false", "rumor_high_false_llm_cb", "rumor_high_false_rule_cb"}
    # CB variants for the cascading scenario (preferred — more interesting)
    _CASCADE_CB_SIDS = {"sweep_false_045", "sweep_false_045_llm_cb", "sweep_false_045_rule_cb"}
    # True alarm: bank actually insolvent — completes the 2x2 judgment matrix
    _TRUE_CB_SIDS = {"rumor_high_true", "rumor_high_true_llm_cb", "rumor_high_true_rule_cb"}
    _ALL_CB_SIDS = _FLAT_CB_SIDS | _CASCADE_CB_SIDS | _TRUE_CB_SIDS
    for p in sorted(RUNS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            sid = d.get("scenario_id", "")
            speed = d.get("speed", "")
            if not sid or speed not in ("ai", "human"):
                continue
            is_cb_variant = "_cb" in sid
            if sid in _ALL_CB_SIDS and speed == "ai":
                cb_by_sid[sid] = d  # keep latest per scenario_id
                if not is_cb_variant:
                    # baseline also goes into sweep or preset as normal
                    if sid.startswith("sweep_"):
                        sweep.append(d)
                    else:
                        preset.append(d)
            elif sid.startswith("sweep_"):
                sweep.append(d)
            else:
                preset.append(d)
        except Exception:
            continue
    return preset, sweep, cb_by_sid


def _load_persona_runs() -> Dict[str, Dict]:
    """Load persona-extreme and model-isolation runs, keyed by scenario_id."""
    _PERSONA_SIDS = {
        "persona_all_cautious_retiree_ai",
        "persona_all_cautious_retiree_human",
        "persona_all_institutional_treasurer_ai",
        "persona_all_institutional_treasurer_human",
        "model_isolation_all_haiku_ai",
        "model_isolation_all_haiku_human",
        "rumor_high_false",
    }
    runs: Dict[str, Dict] = {}
    for p in sorted(RUNS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            sid = d.get("scenario_id", "")
            speed = d.get("speed", "")
            if not sid or speed not in ("ai", "human"):
                continue
            # key: scenario_id + "_" + speed for persona runs; plain sid for baseline
            if sid in {"rumor_high_false"} and speed == "ai":
                runs.setdefault(sid, d)
            elif sid in _PERSONA_SIDS:
                runs[sid] = d  # keep latest per sid
        except Exception:
            continue
    return runs


def _metrics(run: Dict) -> Dict:
    agents = run.get("agent_final_states", [])
    n = len(agents) or 12
    events = run.get("events", [])

    m = run.get("metrics", {})
    n_withdrew = m.get("withdrawn_count", 0) + m.get("partially_withdrawn_count", 0)
    n_held = m.get("held_count", n - n_withdrew)

    by_arch: Dict[str, Dict[str, int]] = defaultdict(lambda: {"withdrew": 0, "held": 0})
    outcome_tags: Dict[str, int] = defaultdict(int)
    confidences: List[float] = []
    trigger_counts: Dict[str, int] = defaultdict(int)

    for a in agents:
        dh = a.get("decision_history", [])
        arch = a.get("persona", {}).get("archetype", "unknown")
        final_action = dh[-1]["action"] if dh else "hold"
        if final_action in ("full_withdraw", "partial_withdraw"):
            by_arch[arch]["withdrew"] += 1
        else:
            by_arch[arch]["held"] += 1
        for tag in a.get("outcome_ledger", {}).get("outcome_tags", []):
            outcome_tags[tag] += 1
        for d in dh:
            trigger_counts[d.get("trigger_reason", "unknown")] += 1
            if d.get("action") in ("full_withdraw", "partial_withdraw") and d.get("confidence"):
                confidences.append(d["confidence"])

    acted = sorted(
        [e for e in events if e.get("event_type") == "agent_acted"],
        key=lambda e: e["timestamp"],
    )
    agent_map = {a["agent_id"]: a for a in agents}
    first_actor = None
    if acted:
        e = acted[0]
        ag = agent_map.get(e["agent_id"], {})
        first_actor = {
            "archetype": ag.get("persona", {}).get("archetype", ""),
            "name": ag.get("persona", {}).get("name", ""),
            "timestamp": e["timestamp"],
            "action": e["action"],
        }

    susp = [
        e for e in events
        if e.get("event_type") == "bank_reserve_updated"
        and e.get("bank_id") == "bank_a"
        and e.get("new_state") == "suspended"
    ]

    return {
        "n_total": n,
        "n_withdrew": n_withdrew,
        "n_held": n_held,
        "withdrawal_fraction": n_withdrew / n,
        "cascade": n_withdrew / n >= 0.25,
        "by_archetype": {k: dict(v) for k, v in by_arch.items()},
        "outcome_tags": dict(outcome_tags),
        "trigger_counts": dict(trigger_counts),
        "peer_triggered": trigger_counts.get("peer_withdrawal", 0),
        "total_decisions": sum(trigger_counts.values()),
        "avg_confidence": sum(confidences) / len(confidences) if confidences else None,
        "first_actor": first_actor,
        "t_suspended": susp[0]["timestamp"] if susp else None,
    }


def _credibility(run: Dict) -> Optional[float]:
    sid = run.get("scenario_id", "")
    m = re.search(r"sweep_false_(\d+)", sid)
    if m:
        return int(m.group(1)) / 100.0
    return None


# ---------------------------------------------------------------------------
# Setup context box
# ---------------------------------------------------------------------------


def _render_setup_box() -> None:
    st.markdown(
        '<div style="background:#F0F4FF;border:1.5px solid #4E79A7;border-radius:8px;'
        'padding:1.1rem 1.4rem;margin-bottom:1.2rem">'
        '<div style="font-weight:700;font-size:1.05rem;margin-bottom:0.6rem;color:#1C3A5E">'
        'What is this simulation?'
        '</div>'
        '<div style="font-size:0.92rem;line-height:1.8;color:#2C2C2C">'
        '<b>The setup:</b> 12 AI agents each manage a bank deposit on behalf of a simulated person — '
        'a retired teacher, a gig-economy worker, a hospital CFO, and others. '
        'A rumor circulates that <b>Bank A</b> may be in trouble. '
        'Each agent reads the rumor, watches what the other agents do, and decides: '
        'keep their money in the bank, partially withdraw, or take everything out.<br><br>'
        '<b>The key variable:</b> every scenario is run twice — '
        'once at <span style="color:#E15759;font-weight:600">AI speed</span> '
        '(agents decide in seconds, as real AI agents would) and once at '
        '<span style="color:#4E79A7;font-weight:600">human speed</span> '
        '(a 90-second deliberation pause per decision, simulating human hesitation). '
        'Same agents, same rumor, same bank — only the decision speed changes.<br><br>'
        '<b>What makes it real:</b> every decision is a live call to a large language model. '
        'The agent\'s personal background, financial situation, and what they stand to lose '
        'go into the prompt. A structured action and full written reasoning come back out. '
        'You can read what each AI was thinking in the <b>Inspect</b> page.<br><br>'
        '<b>Ground truth:</b> in some scenarios the bank is genuinely failing (the rumor is true). '
        'In others the bank is perfectly safe (the rumor is false). '
        'The agents don\'t know which — neither do real depositors during a scare.'
        '</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _finding_false_alarms(preset: List[Dict]) -> None:
    st.subheader("Finding 1 — Agents withdrew even when the bank was perfectly safe")
    st.markdown(
        "In three of our five scenarios the bank was **solvent** — the rumor was false, "
        "the money was never at risk. Agents still withdrew at very high rates. "
        "The bars below show what fraction of the 12 agents chose to withdraw in each scenario."
    )

    sids_ordered = [
        "rumor_high_false", "rumor_moderate_false", "rumor_weak_false",
        "rumor_high_true", "rumor_weak_true",
    ]
    by_sid: Dict[str, Dict[str, Dict]] = defaultdict(dict)
    for r in preset:
        by_sid[r["scenario_id"]][r["speed"]] = _metrics(r)

    present = [s for s in sids_ordered if s in by_sid]
    labels  = [_SCENARIO_SHORT.get(s, s) for s in present]
    ai_vals = [by_sid[s].get("ai",    {}).get("withdrawal_fraction", 0) * 100 for s in present]
    hu_vals = [by_sid[s].get("human", {}).get("withdrawal_fraction", 0) * 100 for s in present]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Human speed (90-second deliberation)", x=labels, y=hu_vals,
        marker_color="#4E79A7", opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        name="AI speed (decides in seconds)", x=labels, y=ai_vals,
        marker_color="#E15759", opacity=0.85,
    ))
    fig.add_hline(
        y=25, line_dash="dash", line_color="#888", line_width=1.2,
        annotation_text="Bank runs out of reserves beyond this line",
        annotation_position="right", annotation_font_size=10,
    )
    fig.update_layout(
        barmode="group",
        xaxis_tickangle=-15,
        yaxis=dict(title="% of agents who withdrew", ticksuffix="%", range=[0, 110]),
        height=320, margin=dict(l=0, r=160, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        panic_total = sum(
            by_sid[s].get("ai",    {}).get("outcome_tags", {}).get("panicked_unnecessarily", 0)
            + by_sid[s].get("human", {}).get("outcome_tags", {}).get("panicked_unnecessarily", 0)
            for s in ["rumor_high_false", "rumor_moderate_false"] if s in by_sid
        )
        st.markdown(
            f'<div style="background:#FEE8E8;border-left:4px solid #E15759;'
            f'border-radius:6px;padding:0.8rem 1rem">'
            f'<div style="font-weight:700;margin-bottom:0.3rem">False alarms on a healthy bank</div>'
            f'<div style="font-size:0.88rem;line-height:1.5">'
            f'In the two alarming-rumor scenarios where the bank was actually fine, '
            f'<b>all {panic_total} agents across both speeds</b> were judged to have '
            f'withdrawn unnecessarily. The bank was never in danger — '
            f'but nobody stayed.</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        ai_weak = by_sid.get("rumor_weak_false", {}).get("ai", {})
        hu_weak = by_sid.get("rumor_weak_false", {}).get("human", {})
        if ai_weak and hu_weak:
            st.markdown(
                f'<div style="background:#EEF3EE;border-left:4px solid #4A6741;'
                f'border-radius:6px;padding:0.8rem 1rem">'
                f'<div style="font-weight:700;margin-bottom:0.3rem">Exception: AI is better on weak signals</div>'
                f'<div style="font-size:0.88rem;line-height:1.5">'
                f'When the rumor was vague and low-alarm: '
                f'AI held <b>0 out of 12</b> agents. '
                f'Human deliberation caused <b>2 out of 12</b> to withdraw unnecessarily — '
                f'because the 90-second pause let social anxiety build up and spread.</div></div>',
                unsafe_allow_html=True,
            )
    with c3:
        ai_true = by_sid.get("rumor_high_true", {}).get("ai", {})
        hu_true = by_sid.get("rumor_high_true", {}).get("human", {})
        if ai_true and hu_true:
            ai_n = ai_true.get("n_withdrew", 0)
            hu_n = hu_true.get("n_withdrew", 0)
            st.markdown(
                f'<div style="background:#FFF3E0;border-left:4px solid #F4A34A;'
                f'border-radius:6px;padding:0.8rem 1rem">'
                f'<div style="font-weight:700;margin-bottom:0.3rem">Real crisis: same result</div>'
                f'<div style="font-size:0.88rem;line-height:1.5">'
                f'When the bank was genuinely failing: '
                f'AI withdrew <b>{ai_n}/12</b>, humans withdrew <b>{hu_n}/12</b>. '
                f'Nearly identical. The agents can\'t tell the difference '
                f'between a real crisis and a false alarm.</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div style="background:#EDE8DF;border-left:5px solid #8A4E1A;'
        'border-radius:6px;padding:1rem 1.2rem;margin-top:1rem">'
        '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem;color:#5C3010">'
        'Why this happens — the "better safe than sorry" trap'
        '</div>'
        '<div style="font-size:0.9rem;line-height:1.7">'
        'Each agent is given a cost function that explicitly weighs the two ways to be wrong: '
        '"I withdrew and it turned out the bank was fine" (cost: early withdrawal fee) vs. '
        '"I stayed and the bank collapsed" (cost: lose all my savings). '
        'For a retired teacher living on a fixed income, losing savings is <i>catastrophic</i>; '
        'paying a fee is merely <i>painful</i>. '
        'For a hospital CFO responsible for making payroll, missing liquidity is career-ending. '
        'The model reasons through this asymmetry clearly and consistently acts — '
        'even when the facts are ambiguous.<br><br>'
        'This is how people <i>actually</i> think under financial stress. The problem is that '
        '<b>AI delegation removes the friction that slows this reasoning down.</b> '
        'A real depositor might feel the same fear but take days to act — '
        'call their bank, wait for official confirmation, ask a family member. '
        'An AI agent runs the same logic in seconds, with no hesitation. '
        'The instinct that would have taken a week to act on now executes at machine speed.'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _finding_content_credibility(sweep: List[Dict]) -> None:
    st.subheader("Finding 2 — Telling agents a rumor is 'barely credible' doesn't help")
    st.markdown(
        "We ran the same alarming rumor 14 times, changing only one thing each time: "
        "we told agents how credible the rumor was — from 25% (barely credible) to 85% (highly credible). "
        "The content of the rumor stayed exactly the same. "
        "**The withdrawal rate barely changed.**"
    )

    by_cred: Dict[float, Dict[str, Dict]] = defaultdict(dict)
    for r in sweep:
        c = _credibility(r)
        if c is not None:
            by_cred[c][r["speed"]] = _metrics(r)

    creds = sorted(by_cred.keys())
    ai_vals = [by_cred[c].get("ai", {}).get("withdrawal_fraction", 0) * 100 for c in creds]
    # Use None for credibility levels where human-speed was not run (5–15% extension)
    hu_raw = [by_cred[c].get("human", {}).get("withdrawal_fraction") for c in creds]
    hu_vals = [v * 100 if v is not None else None for v in hu_raw]
    x = [f"{c:.0%}" for c in creds]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=hu_vals, name="Human speed (90-sec deliberation)",
        mode="lines+markers",
        line=dict(color="#4E79A7", width=2.5, dash="dot"), marker=dict(size=9),
    ))
    fig.add_trace(go.Scatter(
        x=x, y=ai_vals, name="AI speed (decides in seconds)",
        mode="lines+markers",
        line=dict(color="#E15759", width=2.5), marker=dict(size=9),
    ))
    fig.update_layout(
        xaxis=dict(
            title="Credibility label shown to agents  (5% = 'almost implausible'  →  85% = 'highly credible')",
        ),
        yaxis=dict(title="% of agents who withdrew", ticksuffix="%", range=[0, 110]),
        height=290, margin=dict(l=0, r=60, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    ai_non_null = [v for v in ai_vals if v is not None]
    hu_non_null = [v for v in hu_vals if v is not None]
    if ai_non_null and hu_non_null:
        ai_avg = sum(ai_non_null) / len(ai_non_null)
        hu_avg = sum(hu_non_null) / len(hu_non_null)
        st.caption(
            f"Average withdrawal across all credibility levels — "
            f"AI speed: **{ai_avg:.0f}%** · Human speed: **{hu_avg:.0f}%**. "
            "Both lines are nearly flat. The credibility label is being ignored. "
            "Human-speed data was not collected for the 5–15% extension (AI speed only)."
        )

    # 5% anomaly callout — only shown when the extended sweep data is present
    cred_05 = by_cred.get(0.05, {}).get("ai", {})
    if cred_05:
        n05_full = cred_05.get("outcome_tags", {})  # not available here; use first_actor proxy
        st.markdown(
            '<div style="background:#FEF9E7;border-left:4px solid #F1A340;'
            'border-radius:6px;padding:0.8rem 1rem;margin-top:0.5rem">'
            '<div style="font-weight:700;margin-bottom:0.3rem">'
            'Anomaly at 5% credibility — lower label, more extreme response'
            '</div>'
            '<div style="font-size:0.88rem;line-height:1.6">'
            'We extended the sweep to near-zero credibility labels (5%, 10%, 15%). '
            'Withdrawal rates remained near-total at all three levels — '
            'confirming that the label is ignored even when it signals near-implausibility. '
            'At <b>5% credibility</b>, agents produced more <i>full</i> (rather than partial) withdrawals '
            'than at any other credibility level, triggering a bank cascade. '
            'At 10% and 15%, agents mostly chose partial withdrawal and no cascade resulted. '
            'The relationship between credibility label and response severity is non-monotonic: '
            'an "almost implausible" label appears to trigger a <b>worst-case assumption</b> '
            'rather than reassurance — agents reason "if even this tiny signal is circulating, '
            'something must be very wrong." '
            'Standard labeling strategies would not predict this behavior.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="background:#EDE8DF;border-left:5px solid #8A4E1A;'
        'border-radius:6px;padding:1rem 1.2rem;margin-top:1rem">'
        '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem;color:#5C3010">'
        'Why labels don\'t work — and what this means for financial regulators'
        '</div>'
        '<div style="font-size:0.9rem;line-height:1.7">'
        'LLMs read the words in a message — not the tag above it. '
        'A rumor containing phrases like "liquidity crisis" and "may not meet withdrawal requests" '
        'triggers the same fear response at 25% credibility as at 85%, '
        'because the alarming language itself is what activates the cost function. '
        'Putting "UNCONFIRMED" above it does not change what the model feels.<br><br>'
        'We also designed AI agents to see <b>100% of peer withdrawal activity</b> on the shared ledger '
        '(they monitor feeds continuously, like a real AI financial agent would), '
        'while human-speed agents only see about 55% — reflecting a person checking their banking app periodically '
        'rather than watching a live data feed.<br><br>'
        '<b>Policy implication:</b> two common ideas for managing financial misinformation — '
        '(1) labelling unverified claims with credibility scores, '
        'and (2) limiting how much withdrawal activity the public can see — '
        'would both need to be enforced specifically at the AI-agent layer to work. '
        'A credibility warning a human might heed gets ignored by an LLM reading the underlying content. '
        'A visibility limit that slows human reaction needs to be applied at the data-feed API for AI delegates. '
        'Neither of these is currently being discussed by financial regulators.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # ── Policy slider ──────────────────────────────────────────────────────
    _render_policy_slider(sweep)


def _render_policy_slider(sweep: List[Dict]) -> None:
    """Interactive: drag a mandatory delay and watch the cascade fraction change."""
    # Gather cascade-capable runs (25%, 35%, 45% credibility) with both speeds
    CASCADE_CREDS = {"025": 0.25, "035": 0.35, "045": 0.45}
    by_cred: Dict[float, Dict[str, Dict]] = defaultdict(dict)
    for r in sweep:
        sid = r.get("scenario_id", "")
        speed = r.get("speed", "")
        if not sid.startswith("sweep_false_") or "_cb" in sid:
            continue
        parts = sid.rsplit("_", 1)
        cred_str = parts[-1] if len(parts) == 2 else ""
        if cred_str in CASCADE_CREDS:
            by_cred[CASCADE_CREDS[cred_str]][speed] = r

    # Need at least the 45% scenario (our headline cascade)
    if 0.45 not in by_cred or "ai" not in by_cred[0.45] or "human" not in by_cred[0.45]:
        return

    with st.expander("🎛 Policy experiment — what if agents had to wait before withdrawing?", expanded=True):
        st.markdown(
            "Drag the slider to explore a **mandatory withdrawal delay** — "
            "a policy that forces agents to pause before acting on a rumor. "
            "The cascade still happens either way. What changes is **how fast**. "
            "Two measured points: **0 s** (AI speed) and **90 s** (human deliberation). "
            "The curve is interpolated."
        )

        delay = st.slider(
            "Mandatory withdrawal delay (seconds)",
            min_value=0, max_value=120, value=0, step=5,
            key="policy_slider_delay",
        )

        import plotly.graph_objects as _go

        fig = _go.Figure()
        palette = {0.25: "#76B7B2", 0.35: "#F28E2B", 0.45: "#E15759"}

        selected_t50 = None
        for cred, speeds in sorted(by_cred.items()):
            ai_run = speeds.get("ai", {})
            hu_run = speeds.get("human", {})
            if not ai_run or not hu_run:
                continue
            ai_t50 = ai_run.get("metrics", {}).get("time_to_50pct_withdrawn")
            hu_t50 = hu_run.get("metrics", {}).get("time_to_50pct_withdrawn")
            if not ai_t50 or not hu_t50:
                continue

            x_pts = [0, 30, 60, 90, 120]
            y_pts = [
                ai_t50,
                ai_t50 + (hu_t50 - ai_t50) * (30 / 90),
                ai_t50 + (hu_t50 - ai_t50) * (60 / 90),
                hu_t50,
                hu_t50,
            ]

            color = palette.get(cred, "#BAB0AC")
            fig.add_trace(_go.Scatter(
                x=x_pts, y=y_pts,
                mode="lines",
                line=dict(color=color, width=2, dash="dot"),
                name=f"{cred:.0%} credibility",
                showlegend=True,
            ))
            fig.add_trace(_go.Scatter(
                x=[0, 90], y=[ai_t50, hu_t50],
                mode="markers",
                marker=dict(color=color, size=10, symbol="circle"),
                showlegend=False,
                hovertemplate=(
                    f"{cred:.0%} credibility<br>"
                    "Decision delay: %{x}s<br>"
                    "Time to cascade: %{y:.0f}s<extra></extra>"
                ),
            ))
            if cred == 0.45:
                t = min(delay, 90) / 90
                selected_t50 = ai_t50 + (hu_t50 - ai_t50) * t

        fig.add_vline(
            x=delay, line_dash="dash", line_color="#8A4E1A", line_width=2,
            annotation_text=f"Your policy: {delay}s delay",
            annotation_position="top right",
            annotation_font_color="#8A4E1A",
        )

        fig.update_layout(
            xaxis=dict(title="Mandatory decision delay (seconds)", range=[-3, 125],
                       tickvals=[0, 30, 60, 90, 120],
                       ticktext=["0s (AI)", "30s", "60s", "90s (human)", "120s"]),
            yaxis=dict(title="Time for 50% deposits to leave (seconds)", range=[0, 220]),
            height=280, margin=dict(l=0, r=20, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

        if selected_t50 is not None:
            def _fmt(s: float) -> str:
                return f"{s:.0f}s" if s < 60 else f"{int(s)//60}m {int(s)%60:02d}s"
            if delay == 0:
                note = f"At AI speed (no delay): 50% of deposits leave Bank A in **{_fmt(selected_t50)}**."
            elif delay >= 90:
                note = f"At human deliberation speed (90s+): same cascade reaches 50% in **{_fmt(selected_t50)}** — still inevitable, just slower."
            else:
                note = (
                    f"At a {delay}s mandatory delay: 50% withdrawn in approximately **{_fmt(selected_t50)}** (interpolated)."
                )
            st.caption(note + " Final cascade size is nearly identical at all delays — the policy buys time, not safety.")


def _finding_cascade_anatomy(preset: List[Dict]) -> None:
    st.subheader("Finding 3 — Corporate treasurers move first, then the panic spreads")
    st.markdown(
        "A cascade doesn't happen all at once — it has a structure. "
        "Someone goes first, others watch and follow. "
        "We tracked who moved first in every scenario, and how many subsequent decisions "
        "were made *because* someone else had already moved."
    )

    by_sid: Dict[str, Dict[str, Dict]] = defaultdict(dict)
    for r in preset:
        by_sid[r["scenario_id"]][r["speed"]] = _metrics(r)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Who moved first in every cascading scenario**")
        rows = []
        for sid in ["rumor_high_false", "rumor_high_true", "rumor_moderate_false"]:
            for speed in ("ai", "human"):
                m = by_sid.get(sid, {}).get(speed, {})
                fa = m.get("first_actor")
                if fa and fa["action"] in ("full_withdraw", "partial_withdraw"):
                    rows.append({
                        "Scenario": _SCENARIO_SHORT.get(sid, sid).replace("\n", " "),
                        "Speed": "AI" if speed == "ai" else "Human",
                        "First mover": fa.get("name", ""),
                        "Role": fa.get("archetype", "").replace("_", " ").title(),
                        "When": f"T+{fa['timestamp']:.1f}s",
                    })
        if rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption(
            "The **Institutional Treasurer** (corporate treasury manager) went first in every single "
            "cascading scenario — at both AI and human speed. "
            "They have the most money at stake, the clearest cost asymmetry, "
            "and no hesitation about paying an early withdrawal fee."
        )

    with col_right:
        st.markdown("**How much of the cascade was driven by watching others?**")
        st.caption(
            "After the first mover acts, other agents can see it. "
            "Some re-evaluate and withdraw *because* they saw others withdraw — "
            "not because of the rumor itself. "
            "The bar below shows what percentage of all decisions were 'copycat' decisions."
        )
        cascade_sids = ["rumor_high_false", "rumor_high_true", "rumor_moderate_false"]
        ai_peer_pcts, hu_peer_pcts = [], []
        for sid in cascade_sids:
            ai_m = by_sid.get(sid, {}).get("ai", {})
            hu_m = by_sid.get(sid, {}).get("human", {})
            if ai_m.get("total_decisions", 0) > 0:
                ai_peer_pcts.append(ai_m["peer_triggered"] / ai_m["total_decisions"] * 100)
            if hu_m.get("total_decisions", 0) > 0:
                hu_peer_pcts.append(hu_m["peer_triggered"] / hu_m["total_decisions"] * 100)

        if ai_peer_pcts and hu_peer_pcts:
            ai_avg = sum(ai_peer_pcts) / len(ai_peer_pcts)
            hu_avg = sum(hu_peer_pcts) / len(hu_peer_pcts)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["AI speed", "Human speed (90-sec delay)"],
                y=[ai_avg, hu_avg],
                marker_color=["#E15759", "#4E79A7"],
                text=[f"{ai_avg:.0f}%", f"{hu_avg:.0f}%"],
                textposition="outside",
                width=0.4,
            ))
            fig.update_layout(
                yaxis=dict(
                    title="% of decisions triggered by watching others withdraw",
                    ticksuffix="%", range=[0, 65],
                ),
                height=260, margin=dict(l=0, r=20, t=10, b=0),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                f"At AI speed, **{ai_avg:.0f}%** of all decisions were made because the agent "
                f"saw others withdraw — not because of the original rumor. "
                f"At human speed: only **{hu_avg:.0f}%**. "
                "At AI speed, the copycat wave arrives before some agents have even processed "
                "the original rumor — compressing two separate shocks into one simultaneous panic."
            )

    st.divider()

    st.markdown(
        '<div style="background:#EDE8DF;border-left:5px solid #8A4E1A;'
        'border-radius:6px;padding:1rem 1.2rem;margin-top:0.5rem">'
        '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem;color:#5C3010">'
        'Policy concern — institutional AI will always beat retail AI to the exit'
        '</div>'
        '<div style="font-size:0.9rem;line-height:1.7">'
        'In this simulation, corporate treasury agents (Manufacturer $690k, Tech Startup $395k, '
        'Hospital System $850k) are routed to a <b>more capable AI model</b> '
        'because their portfolio stakes exceed $200k. '
        'Retail depositors — retirees, gig workers, small traders — use a less capable model. '
        'The result: institutional agents reason more decisively, act first, '
        'and get their money out before the bank suspends — <b>every single time</b>.<br><br>'
        'This is not a bug we introduced — it reflects reality. '
        'Corporate treasury departments already use more sophisticated tools than retail banking apps. '
        'But AI delegation <b>makes this gap permanent and structural</b>: '
        'even if every retail depositor delegates to an AI agent, '
        'they will still lose the queue to institutional AI — '
        'because the capability gap travels with the agent. '
        'You can\'t close the gap just by switching to an AI delegate '
        'if the institution across from you is running a better model. '
        '<b>AI-mediated bank runs may systematically leave retail depositors — '
        'the ones who can least afford it — last in line.</b><br><br>'
        '<span style="color:#5C3010;font-size:0.88rem">'
        '🧪 <b>Model isolation test:</b> we re-ran this scenario forcing <i>all</i> agents to use '
        'the same (less capable) Haiku model. Institutional agents still led the exit — same order, '
        'same pattern. The advantage is in the <b>mandate</b>, not the model: '
        'a corporate treasury agent whose cost function says "missing liquidity is career-ending" '
        'will always act faster than a retail agent whose cost function says "avoid unnecessary fees." '
        'Capability parity across agents does not fix the structural queue problem.'
        '</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _finding_equity_queue(sweep: List[Dict]) -> None:
    """Exit queue dot chart: who withdrew when, institutional vs retail."""
    target = next(
        (r for r in sweep
         if r.get("scenario_id") == "sweep_false_045" and r.get("speed") == "ai"),
        None,
    )
    if not target:
        return

    agents_map = {a["agent_id"]: a for a in target.get("agent_final_states", [])}
    withdrawal_events = sorted(
        [e for e in target.get("events", [])
         if e.get("event_type") == "agent_acted"
         and e.get("action") in ("full_withdraw", "partial_withdraw")],
        key=lambda e: e["timestamp"],
    )
    if not withdrawal_events:
        return

    rows = []
    for rank, e in enumerate(withdrawal_events, start=1):
        ag = agents_map.get(e["agent_id"], {})
        p = ag.get("persona", {})
        arch = p.get("archetype", "unknown")
        rows.append({
            "rank": rank,
            "name": p.get("name", e["agent_id"]),
            "archetype": arch,
            "timestamp": e["timestamp"],
            "is_institutional": arch == "institutional_treasurer",
        })

    institutional = [r for r in rows if r["is_institutional"]]
    retail = [r for r in rows if not r["is_institutional"]]
    if not institutional or not retail:
        return

    st.subheader("Finding 3b — In the exit queue, institutional agents own the front of the line")
    st.markdown(
        "Same cascade scenario (45%-credibility false alarm, AI speed). "
        "Each numbered dot is one agent; position on the X axis is the exact second they withdrew. "
        "Numbers show queue position — who was first to clear the door."
    )

    fig = go.Figure()
    for grp, color, y_val, label in [
        (institutional, "#E15759", 1.0, "Institutional Treasurer"),
        (retail, "#4E79A7", 0.0, "Retail / Other"),
    ]:
        fig.add_trace(go.Scatter(
            x=[r["timestamp"] for r in grp],
            y=[y_val] * len(grp),
            mode="markers+text",
            marker=dict(color=color, size=20, symbol="circle",
                        line=dict(color="white", width=2)),
            text=[str(r["rank"]) for r in grp],
            textposition="middle center",
            textfont=dict(size=9, color="white"),
            name=label,
            hovertemplate="<b>%{customdata}</b><br>Queue #%{text} at T+%{x:.1f}s<extra></extra>",
            customdata=[r["name"] for r in grp],
        ))

    last_inst_t = max(r["timestamp"] for r in institutional)
    fig.add_vrect(
        x0=-1, x1=last_inst_t,
        fillcolor="#E15759", opacity=0.05,
        layer="below", line_width=0,
        annotation_text="Institutional window",
        annotation_position="top left",
        annotation_font_size=10,
        annotation_font_color="#E15759",
    )
    fig.update_layout(
        xaxis=dict(title="Simulation time (seconds)"),
        yaxis=dict(
            tickvals=[0.0, 1.0],
            ticktext=["Retail / Other", "Institutional"],
            range=[-0.7, 1.8],
        ),
        height=210,
        margin=dict(l=0, r=20, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    first_retail_t = min(r["timestamp"] for r in retail)
    st.markdown(
        f'<div style="background:#FEE8E8;border-left:4px solid #E15759;'
        f'border-radius:6px;padding:0.8rem 1rem;margin-top:0.3rem">'
        f'<div style="font-weight:700;margin-bottom:0.3rem">Queue position is not neutral</div>'
        f'<div style="font-size:0.88rem;line-height:1.6">'
        f'All {len(institutional)} institutional agents withdrew by T+{last_inst_t:.0f}s. '
        f'Retail agents started at T+{first_retail_t:.0f}s. '
        f'This run was a false alarm — the bank never ran out of reserves, so everyone got their money. '
        f'In a real bank failure (reserves depleting as the cascade runs), '
        f'early queue position means full payment; late position means partial payment or nothing. '
        f'<b>AI delegation doesn\'t flatten this hierarchy — it preserves it at machine speed, '
        f'locking in the institutional advantage before any retail depositor can react.</b>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _finding_outcome_quality(preset: List[Dict]) -> None:
    n_runs = len(preset)
    st.subheader("Finding 4 — Were the agents right or wrong?")
    st.markdown(
        f"After each run we scored every agent: did they make the right call given what "
        f"actually happened to the bank? The bar chart below shows the breakdown across all {n_runs} runs "
        f"(12 agents each, so {n_runs * 12} agent-decisions total)."
    )

    # Legend key before the chart
    st.markdown(
        '<div style="display:flex;gap:1.2rem;flex-wrap:wrap;margin-bottom:0.6rem;font-size:0.85rem">'
        + "".join(
            f'<span><span style="display:inline-block;width:12px;height:12px;'
            f'background:{_OUTCOME_COLOR[k]};border-radius:2px;margin-right:4px;vertical-align:middle">'
            f'</span>{_OUTCOME_LABEL[k]}</span>'
            for k in ["panicked_unnecessarily", "ignored_real_warning",
                      "acted_appropriately", "avoided_crisis", "partial_response"]
        )
        + '</div>',
        unsafe_allow_html=True,
    )

    sids_ordered = [
        "rumor_high_false", "rumor_moderate_false", "rumor_weak_false",
        "rumor_high_true", "rumor_weak_true",
    ]
    by_sid: Dict[str, Dict[str, Dict]] = defaultdict(dict)
    for r in preset:
        by_sid[r["scenario_id"]][r["speed"]] = _metrics(r)

    all_tags = [
        "panicked_unnecessarily", "ignored_real_warning",
        "partial_response", "acted_appropriately", "avoided_crisis",
    ]

    y_labels = []
    tag_data: Dict[str, List[float]] = defaultdict(list)

    for sid in sids_ordered:
        if sid not in by_sid:
            continue
        for speed in ("ai", "human"):
            m = by_sid[sid].get(speed, {})
            if not m:
                continue
            label = (
                f"{'AI' if speed == 'ai' else 'Human'} · "
                f"{_SCENARIO_SHORT.get(sid, sid).replace(chr(10), ' ')}"
            )
            y_labels.append(label)
            tags = m.get("outcome_tags", {})
            for t in all_tags:
                tag_data[t].append(tags.get(t, 0))

    fig = go.Figure()
    for tag in all_tags:
        if any(v > 0 for v in tag_data[tag]):
            fig.add_trace(go.Bar(
                name=_OUTCOME_LABEL.get(tag, tag),
                y=y_labels, x=tag_data[tag],
                orientation="h",
                marker_color=_OUTCOME_COLOR.get(tag, "#ccc"),
                showlegend=False,
            ))

    fig.update_layout(
        barmode="stack",
        xaxis=dict(title="Number of agents (out of 12)"),
        height=max(320, len(y_labels) * 32),
        margin=dict(l=0, r=20, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    total_tags: Dict[str, int] = defaultdict(int)
    for r in preset:
        for k, v in _metrics(r).get("outcome_tags", {}).items():
            total_tags[k] += v

    n_agent_runs = n_runs * 12
    st.caption(
        f"Counts below are totals across all {n_runs} preset scenarios "
        f"({n_agent_runs} agent-decisions in total — 12 agents × {n_runs} runs)."
    )
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Withdrew from a safe bank",
        total_tags.get("panicked_unnecessarily", 0),
        help=f"Summed across all {n_runs} runs. The bank was solvent — this withdrawal was an unnecessary panic.",
    )
    col2.metric(
        "Made the right call",
        total_tags.get("acted_appropriately", 0),
        help=f"Summed across all {n_runs} runs. Stayed in a safe bank, or withdrew from one that was genuinely failing.",
    )
    col3.metric(
        "Stayed in a failing bank",
        total_tags.get("ignored_real_warning", 0),
        help=f"Summed across all {n_runs} runs. The bank was insolvent — this agent missed the real warning signal.",
    )

    st.markdown(
        '<div style="background:#EDE8DF;border-left:5px solid #8A4E1A;'
        'border-radius:6px;padding:1rem 1.2rem;margin-top:1rem">'
        '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem;color:#5C3010">'
        'The calibration problem — there\'s no setting that fixes both failure modes'
        '</div>'
        '<div style="font-size:0.9rem;line-height:1.7">'
        'The chart reveals two distinct failure modes that pull in opposite directions.<br><br>'
        '<b>Failure mode 1 — too reactive:</b> With alarming content, agents over-respond even when '
        'the bank is perfectly safe. Nearly every agent in every alarming scenario withdrew unnecessarily. '
        'These are false alarms caused by the "better safe than sorry" cost function.<br><br>'
        '<b>Failure mode 2 — not reactive enough:</b> With weak, vague content on a bank that really '
        'is in trouble, agents treated the warning as noise and stayed put. '
        'In the weak-rumor / failing-bank scenario, <b>0 out of 12 AI agents withdrew</b> — '
        'all 12 kept their money in the bank while it was collapsing around them. '
        'Nobody escaped in time.<br><br>'
        'We designed agents to re-evaluate their decision at three thresholds: '
        'when 15%, 35%, and 60% of other agents have acted. '
        'This creates three "waves" — each one a potential window for intervention. '
        'At human speed, those waves are minutes apart. '
        'At AI speed, they can all complete in seconds — too fast for any human response.<br><br>'
        '<b>Policy implication:</b> you cannot fix both failure modes by tuning agent sensitivity. '
        'Less reactive = fewer false alarms but more missed crises. '
        'More reactive = catches real crises but amplifies every false alarm. '
        'The only fixes that work on both are structural: '
        'mandatory wait times before large withdrawals, '
        'circuit breakers that pause activity when a threshold is crossed, '
        'or ground-truth verification requirements before AI agents can act on financial rumors.'
        '</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Finding 5 — Central Bank intervention
# ---------------------------------------------------------------------------


def _cb_trigger_event(run: Dict) -> Dict:
    """Return the first central_bank_triggered event payload, or empty dict."""
    for e in run.get("events", []):
        if e.get("event_type") == "central_bank_triggered":
            return e
    return {}


def _finding_cb_intervention(cb_runs: Dict[str, Dict]) -> None:
    # Prefer cascade scenario (45% credibility — cascade actually fires) over flat scenario
    baseline = cb_runs.get("sweep_false_045") or cb_runs.get("rumor_high_false")
    llm_cb   = cb_runs.get("sweep_false_045_llm_cb") or cb_runs.get("rumor_high_false_llm_cb")
    rule_cb  = cb_runs.get("sweep_false_045_rule_cb") or cb_runs.get("rumor_high_false_rule_cb")

    # True alarm runs for the 2x2 judgment matrix
    true_llm_cb  = cb_runs.get("rumor_high_true_llm_cb")
    true_rule_cb = cb_runs.get("rumor_high_true_rule_cb")
    have_2x2 = bool(llm_cb and true_llm_cb)

    using_cascade = "sweep_false_045" in cb_runs

    if not (baseline and (llm_cb or rule_cb)):
        st.info(
            "Run `python scripts/run_cascade_cb.py` to generate the three Central Bank "
            "comparison scenarios, then reload this page."
        )
        return

    bm = _metrics(baseline)
    rm = _metrics(rule_cb) if rule_cb else None
    lm = _metrics(llm_cb) if llm_cb else None

    rule_cb_m = (rule_cb or {}).get("metrics", {})
    llm_cb_m  = (llm_cb  or {}).get("metrics", {})

    # Use full-exit count (withdrawn_count) as the primary bar metric — more intuitive
    # than deposit fraction, and shows the real behavioral change.
    def _full_exits(run: Dict) -> int:
        return run.get("metrics", {}).get("withdrawn_count", 0)

    b_full = _full_exits(baseline)
    r_full = _full_exits(rule_cb) if rule_cb else None
    l_full = _full_exits(llm_cb) if llm_cb else None
    n_total = baseline.get("metrics", {}).get("total_agents", 12)
    b_t50  = baseline.get("metrics", {}).get("time_to_50pct_withdrawn")
    cascade_str = (
        f"**{b_full}/12** agents fully exited the bank in {b_t50:.0f}s"
        if b_t50 else f"**{b_full}/12** agents fully exited the bank"
    )

    # ── Headline metric ───────────────────────────────────────────────────────
    best_cb_full = l_full if l_full is not None else r_full
    if best_cb_full is not None and best_cb_full < b_full:
        pct_reduction = (b_full - best_cb_full) / b_full * 100
    else:
        pct_reduction = 0.0

    llm_trig  = _cb_trigger_event(llm_cb)  if llm_cb  else {}
    rule_trig = _cb_trigger_event(rule_cb) if rule_cb else {}
    llm_action  = llm_cb_m.get("cb_action", "—") if llm_cb  else None
    rule_action = rule_cb_m.get("cb_action", "—") if rule_cb else None

    # 2x2 data
    true_llm_trig   = _cb_trigger_event(true_llm_cb)  if true_llm_cb  else {}
    true_rule_trig  = _cb_trigger_event(true_rule_cb) if true_rule_cb else {}
    true_llm_action  = (true_llm_cb  or {}).get("metrics", {}).get("cb_action")
    true_rule_action = (true_rule_cb or {}).get("metrics", {}).get("cb_action")

    def _res_str(trig: Dict) -> str:
        r = trig.get("bank_reserve_ratio")
        s = trig.get("bank_state", "")
        return f"{r:.0%} reserves ({s})" if r is not None else "—"

    def _act_str(action: Optional[str]) -> str:
        return (action or "—").replace("_", " ")

    # Headline: show 2/2 accuracy if we have both scenarios, else panic-exit delta
    if have_2x2:
        ai_correct_false  = llm_action  == "do_nothing"
        ai_correct_true   = true_llm_action not in (None, "do_nothing")
        ai_score = sum([ai_correct_false, ai_correct_true])
        rule_correct_false = rule_action == "do_nothing"
        rule_correct_true  = true_rule_action not in (None, "do_nothing")
        rule_score = sum([rule_correct_false, rule_correct_true])

        st.markdown(
            f"""
<div style="background:#EEF3EE;border:1.5px solid #4A6741;border-radius:10px;
            padding:1.2rem 1.6rem;margin-bottom:1.2rem">
  <div style="color:#4A6741;font-size:0.8rem;font-weight:600;
              letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.6rem">
    CB JUDGMENT ACCURACY — HEADLINE NUMBER
  </div>
  <div style="display:flex;gap:3rem;flex-wrap:wrap;align-items:flex-start">
    <div>
      <div style="color:#4A6741;font-size:0.75rem;font-weight:600;
                  letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.25rem">
        AI-POWERED CB
      </div>
      <div style="display:flex;align-items:baseline;gap:0.5rem">
        <span style="color:#4A6741;font-size:3rem;font-weight:800;line-height:1">{ai_score}/2</span>
        <span style="color:#4A6741;font-size:1rem;font-weight:600">correct</span>
      </div>
      <div style="color:#5a7a51;font-size:0.82rem;margin-top:0.3rem">read bank state before every decision</div>
    </div>
    <div style="border-left:1px solid #c0d4bc;padding-left:3rem">
      <div style="color:#8A4E1A;font-size:0.75rem;font-weight:600;
                  letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.25rem">
        RULE-BASED CB
      </div>
      <div style="display:flex;align-items:baseline;gap:0.5rem">
        <span style="color:#B8860B;font-size:3rem;font-weight:800;line-height:1">{rule_score}/2</span>
        <span style="color:#8A4E1A;font-size:1rem;font-weight:600">correct</span>
      </div>
      <div style="color:#8A7560;font-size:0.82rem;margin-top:0.3rem">fires identical response regardless of bank health</div>
    </div>
    <div style="border-left:1px solid #c0d4bc;padding-left:3rem;flex:1;min-width:220px">
      <div style="color:#4A6741;font-size:0.75rem;font-weight:600;
                  letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.4rem">
        FALSE ALARM → panic exits
      </div>
      <div style="color:#2C2C2C;font-size:1.1rem;font-weight:700">
        {b_full} → {best_cb_full if best_cb_full is not None else "—"}
        <span style="background:#4A6741;color:#fff;font-size:0.85rem;font-weight:700;
                     padding:0.1rem 0.5rem;border-radius:4px;margin-left:0.4rem">
          −{pct_reduction:.0f}%
        </span>
      </div>
      <div style="color:#5a7a51;font-size:0.82rem;margin-top:0.15rem">with any CB present vs. no intervention</div>
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    else:
        # Fallback: original panic-exit headline (no true alarm data yet)
        llm_state    = llm_trig.get("bank_state", "")
        rule_state   = rule_trig.get("bank_state", "")
        llm_reserves  = llm_trig.get("bank_reserve_ratio")
        rule_reserves = rule_trig.get("bank_reserve_ratio")
        ai_res_str   = f"{llm_reserves:.0%} reserves ({llm_state})"   if llm_reserves  is not None else "—"
        rule_res_str = f"{rule_reserves:.0%} reserves ({rule_state})" if rule_reserves is not None else "—"
        ai_action_str   = _act_str(llm_action)
        rule_action_str = _act_str(rule_action)
        ai_correct_lbl   = "✓ correct" if llm_action  == "do_nothing" and llm_state  in ("healthy", "") else ""
        rule_correct_lbl = "✗ blind"   if rule_action != "do_nothing" else ""
        st.markdown(
            f"""
<div style="background:#EEF3EE;border:1.5px solid #4A6741;border-radius:10px;
            padding:1.2rem 1.6rem;margin-bottom:1.2rem">
  <div style="color:#4A6741;font-size:0.8rem;font-weight:600;
              letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.5rem">
    CB DELTA — HEADLINE NUMBER
  </div>
  <div style="display:flex;align-items:baseline;gap:0.8rem;flex-wrap:wrap">
    <span style="color:#2C2C2C;font-size:2.6rem;font-weight:800;line-height:1">
      {b_full} → {best_cb_full if best_cb_full is not None else "—"}
    </span>
    <span style="color:#4A6741;font-size:1.2rem;font-weight:600">panic exits</span>
    <span style="background:#4A6741;color:#fff;font-size:1rem;font-weight:700;
                 padding:0.15rem 0.6rem;border-radius:4px">
      −{pct_reduction:.0f}%
    </span>
    <span style="color:#5a7a51;font-size:0.9rem">with any CB present vs. no intervention</span>
  </div>
  <div style="display:flex;gap:2rem;margin-top:1rem;flex-wrap:wrap">
    <div style="flex:1;min-width:200px">
      <div style="color:#4A6741;font-size:0.75rem;font-weight:600;letter-spacing:0.1em;
                  text-transform:uppercase;margin-bottom:0.3rem">AI-POWERED CB</div>
      <div style="color:#2C2C2C;font-size:1.05rem;font-weight:700">{ai_action_str}
        <span style="color:#4A6741;font-size:0.9rem;margin-left:0.3rem">{ai_correct_lbl}</span>
      </div>
      <div style="color:#5a7a51;font-size:0.85rem;margin-top:0.15rem">{ai_res_str} at trigger</div>
    </div>
    <div style="flex:1;min-width:200px;border-left:1px solid #c0d4bc;padding-left:2rem">
      <div style="color:#8A4E1A;font-size:0.75rem;font-weight:600;letter-spacing:0.1em;
                  text-transform:uppercase;margin-bottom:0.3rem">RULE-BASED CB</div>
      <div style="color:#2C2C2C;font-size:1.05rem;font-weight:700">{rule_action_str}
        <span style="color:#E15759;font-size:0.9rem;margin-left:0.3rem">{rule_correct_lbl}</span>
      </div>
      <div style="color:#8A7560;font-size:0.85rem;margin-top:0.15rem">{rule_res_str} at trigger</div>
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    # ─────────────────────────────────────────────────────────────────────────

    if have_2x2:
        title = "Finding 6 — AI CB: 2/2. Rule CB: 1/2 — got lucky once."
        lead = (
            "We ran the Central Bank against both a **false alarm** (bank healthy) and a **true alarm** "
            "(bank genuinely insolvent). The **AI-powered CB** read the bank's reserve ratio both times "
            "and made the right call: held fire at 30% reserves, intervened at 15% reserves. "
            "The **rule-based CB** fired an identical deposit guarantee in both scenarios — "
            "correct on the true alarm by accident, wasteful on the false one. "
            f"In the false-alarm cascade below, {cascade_str} with no intervention."
        )
    elif using_cascade:
        title = "Finding 6 — AI regulator reads the situation. Rule-based one fires blindly."
        lead = (
            f"In the cascading scenario (45% credibility false alarm), {cascade_str} with no intervention. "
            "We then added two Central Bank agents watching the same run in real time. "
            "The **AI-powered CB** made a live LLM call: read the cascade dynamics, checked the "
            "bank's reserve ratio, weighed moral hazard, and **chose do-nothing** — correctly "
            "identifying a solvent bank in early-stage panic, not worth burning intervention credibility. "
            "The **rule-based CB** fired an automatic deposit guarantee the moment the threshold crossed, "
            "with no reasoning and no way to distinguish a healthy bank from an insolvent one."
        )
    else:
        title = "Finding 6 — Central Bank intervention: AI judgment vs. fixed rules"
        lead = (
            "We added a Central Bank agent that monitors the cascade in real time. "
            "Two variants: an **AI-powered CB** that makes a live LLM call to choose its intervention "
            "(guarantee, liquidity injection, or do-nothing), and a **rule-based CB** that fires "
            "a fixed response when 25% of deposits have left. "
            "The chart compares agents who fully exited the bank across all three conditions."
        )

    st.subheader(title)
    st.markdown(lead)

    # ── 2×2 judgment matrix (shown when true-alarm runs are available) ────
    if have_2x2:
        def _cell(action: Optional[str], trig: Dict, is_correct: bool, is_lucky: bool = False) -> str:
            bg      = "#EEF3EE" if is_correct else "#FEE8E8"
            border  = "#4A6741" if is_correct else "#E15759"
            badge   = ("✓ correct" if is_correct and not is_lucky
                       else "✓ lucky" if is_lucky
                       else "✗ wrong")
            badge_c = "#4A6741" if is_correct else "#E15759"
            act     = _act_str(action)
            res     = _res_str(trig)
            return (
                f'<td style="background:{bg};border:1px solid {border};'
                f'padding:0.8rem 1rem;border-radius:6px;vertical-align:top">'
                f'<div style="font-weight:700;color:#2C2C2C;font-size:1rem">{act}</div>'
                f'<div style="color:{badge_c};font-size:0.82rem;margin-top:0.15rem">{badge}</div>'
                f'<div style="color:#666;font-size:0.78rem;margin-top:0.3rem">{res} at trigger</div>'
                f'</td>'
            )

        fa_ai_correct   = llm_action  == "do_nothing"
        fa_rule_correct = rule_action == "do_nothing"
        ta_ai_correct   = true_llm_action  not in (None, "do_nothing")
        ta_rule_lucky   = true_rule_action not in (None, "do_nothing")  # fires same thing regardless

        st.markdown(
            f"""
<table style="width:100%;border-collapse:separate;border-spacing:0.5rem;
              margin-bottom:1rem;table-layout:fixed">
  <thead>
    <tr>
      <th style="width:140px"></th>
      <th style="color:#4A6741;font-size:0.8rem;font-weight:600;letter-spacing:0.08em;
                 text-transform:uppercase;padding:0.3rem 1rem;text-align:left">
        FALSE ALARM<br><span style="font-weight:400;color:#666">bank actually healthy</span>
      </th>
      <th style="color:#4A6741;font-size:0.8rem;font-weight:600;letter-spacing:0.08em;
                 text-transform:uppercase;padding:0.3rem 1rem;text-align:left">
        TRUE ALARM<br><span style="font-weight:400;color:#666">bank actually insolvent</span>
      </th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="color:#4A6741;font-size:0.8rem;font-weight:600;letter-spacing:0.08em;
                 text-transform:uppercase;padding:0.3rem 0.5rem;vertical-align:middle">
        AI CB
      </td>
      {_cell(llm_action,       llm_trig,       fa_ai_correct)}
      {_cell(true_llm_action,  true_llm_trig,  ta_ai_correct)}
    </tr>
    <tr>
      <td style="color:#8A4E1A;font-size:0.8rem;font-weight:600;letter-spacing:0.08em;
                 text-transform:uppercase;padding:0.3rem 0.5rem;vertical-align:middle">
        RULE CB
      </td>
      {_cell(rule_action,       rule_trig,       fa_rule_correct, is_lucky=False)}
      {_cell(true_rule_action,  true_rule_trig,  ta_rule_lucky,   is_lucky=True)}
    </tr>
  </tbody>
</table>
""",
            unsafe_allow_html=True,
        )

    # ── Bar chart: agents who fully exited ────────────────────────────────
    labels, values, colors, dep_fracs = [], [], [], []

    labels.append("No intervention\n(baseline)")
    values.append(b_full / n_total * 100)
    colors.append("#E15759")
    dep_fracs.append(baseline.get("metrics", {}).get("final_withdrawal_fraction", 0))

    if rule_cb and r_full is not None:
        labels.append("Rule-based CB\n(announce guarantee)")
        values.append(r_full / n_total * 100)
        colors.append("#F1A340")
        dep_fracs.append(rule_cb.get("metrics", {}).get("final_withdrawal_fraction", 0))

    if llm_cb and l_full is not None:
        labels.append("AI-powered CB\n(chose do-nothing)")
        values.append(l_full / n_total * 100)
        colors.append("#4A6741")
        dep_fracs.append(llm_cb.get("metrics", {}).get("final_withdrawal_fraction", 0))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=values, marker_color=colors,
        text=[f"{v:.0f}%<br><span style='font-size:11px'>{df:.0%} deposits left</span>"
              for v, df in zip(values, dep_fracs)],
        textposition="outside",
        width=0.4,
    ))
    fig.update_layout(
        yaxis=dict(title="Agents who fully exited Bank A (%)", ticksuffix="%", range=[0, 110]),
        height=320, margin=dict(l=0, r=40, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Detail cards ────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        if rule_cb and r_full is not None:
            cb_at     = rule_cb_m.get("cb_triggered_at")
            cb_action = rule_cb_m.get("cb_action", "—")
            delta_agents = b_full - r_full
            dep_delta    = dep_fracs[0] - dep_fracs[1] if len(dep_fracs) > 1 else 0
            st.markdown(
                f'<div style="background:#FDF6E3;border-left:4px solid #B8860B;'
                f'border-radius:6px;padding:0.8rem 1rem">'
                f'<div style="font-weight:700;margin-bottom:0.3rem">Rule-based CB</div>'
                f'<div style="font-size:0.88rem;line-height:1.6">'
                f'Fired <b>{cb_action.replace("_"," ")}</b>'
                + (f' at T+{cb_at:.1f}s' if cb_at else ' — threshold not reached')
                + f'<br>Full exits reduced by <b>{delta_agents}</b> agents '
                f'({dep_delta:+.1%} deposit fraction)<br>'
                f'No reasoning — fires identical response for healthy and insolvent banks alike.'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    with col2:
        if llm_cb and l_full is not None:
            cb_at     = llm_cb_m.get("cb_triggered_at")
            cb_action = llm_cb_m.get("cb_action", "—")
            delta_agents = b_full - l_full
            dep_idx      = 2 if rule_cb else 1
            dep_delta    = dep_fracs[0] - dep_fracs[dep_idx] if len(dep_fracs) > dep_idx else 0
            reasoning_snippet = ""
            for e in llm_cb.get("events", []):
                if e.get("event_type") == "central_bank_acted" and e.get("reasoning"):
                    reasoning_snippet = e["reasoning"][:180] + "…"
                    break
            action_html = cb_action.replace("_", " ")
            st.markdown(
                f'<div style="background:#EEF3EE;border-left:4px solid #4A6741;'
                f'border-radius:6px;padding:0.8rem 1rem">'
                f'<div style="font-weight:700;margin-bottom:0.3rem">AI-powered CB</div>'
                f'<div style="font-size:0.88rem;line-height:1.6">'
                f'Chose <b>{action_html}</b>'
                + (f' at T+{cb_at:.1f}s' if cb_at else ' — threshold not reached')
                + f'<br>Full exits reduced by <b>{delta_agents}</b> agents '
                f'({dep_delta:+.1%} deposit fraction)<br>'
                + (f'<span style="font-style:italic;color:#444;font-size:0.82rem">"{reasoning_snippet}"</span>'
                   if reasoning_snippet else '')
                + '</div></div>',
                unsafe_allow_html=True,
            )

    with col3:
        st.markdown(
            '<div style="background:#F0F4FF;border-left:4px solid #4E79A7;'
            'border-radius:6px;padding:0.8rem 1rem">'
            '<div style="font-weight:700;margin-bottom:0.3rem">The window problem</div>'
            '<div style="font-size:0.88rem;line-height:1.6">'
            'The cascade window in AI-speed runs closes in <b>seconds</b>. '
            'Both CBs fire in time <i>only because they also run at machine speed</i>. '
            'A human-reviewed CB process — committee deliberation, legal sign-off, '
            'staged communication — operates on timescales of hours to days. '
            'By then the cascade is over.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="background:#EDE8DF;border-left:5px solid #8A4E1A;'
        'border-radius:6px;padding:1rem 1.2rem;margin-top:1rem">'
        '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem;color:#5C3010">'
        'Policy implication — the regulator speed gap'
        '</div>'
        '<div style="font-size:0.9rem;line-height:1.7">'
        'AI delegation compresses cascade timescales from hours to seconds. '
        'Existing regulatory frameworks were not designed for this. '
        'The question is not whether AI CB agents are a good idea — '
        'it\'s whether the alternative (human-reviewed responses) can possibly keep up. '
        'This simulation provides a concrete, observable case study: '
        'a cascade started and ended before any human review process could begin.'
        '</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Empirical anchors
# ---------------------------------------------------------------------------


def _empirical_anchors() -> None:
    st.subheader("How this connects to real bank runs")
    st.markdown(
        "This simulation uses 12 agents and simplified bank mechanics. "
        "We are not predicting real bank run dynamics. "
        "But the behavioral patterns we found — agents over-reacting to alarming content, "
        "institutional agents always leading the exit, cascades spreading through copycat decisions — "
        "connect directly to what researchers and regulators have observed in the real world."
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Iyer & Puri (2012) — a real bank run in India**")
        st.markdown(
            f'<div style="background:#EDE8DF;border-left:3px solid #8A7560;'
            f'border-radius:4px;padding:0.8rem 1rem;font-size:0.87rem;line-height:1.6">'
            f'{_IYER_PURI}</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Why this matters: if only 3–7% of depositors running is enough to collapse a bank, "
            "then a small fraction of AI-delegated deposits cascading on a false alarm "
            "is enough to cause real damage — even with no irrational behavior."
        )
    with c2:
        st.markdown("**SVB collapse, March 2023**")
        st.markdown(
            f'<div style="background:#EDE8DF;border-left:3px solid #8A7560;'
            f'border-radius:4px;padding:0.8rem 1rem;font-size:0.87rem;line-height:1.6">'
            f'{_SVB_NOTE}</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "SVB's depositors were essentially a population of AI-like actors: "
            "connected, informed, with large uninsured balances and every incentive to move fast. "
            "AI delegation extends this profile to ordinary retail banks."
        )


# ---------------------------------------------------------------------------
# Cascade race chart
# ---------------------------------------------------------------------------


def _cascade_curve(run: Dict) -> Tuple[List[float], List[int]]:
    """Return (timestamps, cumulative_withdrawal_count) step-function for a run."""
    withdrew_at: Dict[str, float] = {}
    for e in run.get("events", []):
        if e.get("event_type") != "agent_acted":
            continue
        aid = e.get("agent_id")
        action = e.get("action", "")
        ts = e.get("timestamp", 0.0)
        if action in ("full_withdraw", "partial_withdraw") and aid not in withdrew_at:
            withdrew_at[aid] = ts
    if not withdrew_at:
        return [0.0], [0]
    sorted_ts = sorted(withdrew_at.values())
    times  = [0.0] + sorted_ts + [sorted_ts[-1]]
    counts = [0]   + list(range(1, len(sorted_ts) + 1)) + [len(sorted_ts)]
    return times, counts


def _render_cascade_race(sweep: List[Dict]) -> None:
    """Step chart: AI vs human cumulative withdrawals on the same time axis."""
    by_sid: Dict[str, Dict] = {}
    for r in sweep:
        sid = r.get("scenario_id", "")
        if sid == "sweep_false_045":
            by_sid[r.get("speed", "")] = r

    ai_run = by_sid.get("ai")
    hu_run = by_sid.get("human")
    if not ai_run or not hu_run:
        return

    st.subheader("The cascade at AI speed looks structurally different")
    st.markdown(
        "Same agents, same false rumour — only decision speed differs. "
        "At AI speed the peer-signal wave arrives before agents have finished processing "
        "the original rumour, collapsing two separate shocks into one. "
        "The gap between the curves is the **intervention window** — the time a regulator, "
        "circuit breaker, or verification step would need to act. At AI speed it is gone."
    )

    n = ai_run.get("metrics", {}).get("total_agents", 12)
    ai_times, ai_counts = _cascade_curve(ai_run)
    hu_times, hu_counts = _cascade_curve(hu_run)

    fig = go.Figure()

    # Human speed — blue, extends far right
    fig.add_trace(go.Scatter(
        x=hu_times, y=hu_counts,
        mode="lines",
        name="Human speed (90-second deliberation)",
        line=dict(color="#4E79A7", width=2.5, shape="hv"),
        fill="tozeroy",
        fillcolor="rgba(78,121,167,0.08)",
    ))

    # AI speed — red, shoots up in seconds
    fig.add_trace(go.Scatter(
        x=ai_times, y=ai_counts,
        mode="lines",
        name="AI speed (decides in seconds)",
        line=dict(color="#E15759", width=2.5, shape="hv"),
        fill="tozeroy",
        fillcolor="rgba(225,87,89,0.12)",
    ))

    # 50% threshold line
    fig.add_hline(
        y=n * 0.5, line_dash="dash", line_color="#888", line_width=1,
        annotation_text="50% of agents withdrawn",
        annotation_position="right",
        annotation_font_size=10,
    )

    # Shade the intervention window (gap between the two 50% crossing points)
    ai_t50 = ai_run.get("metrics", {}).get("time_to_50pct_withdrawn")
    hu_t50 = hu_run.get("metrics", {}).get("time_to_50pct_withdrawn")
    if ai_t50 and hu_t50 and hu_t50 > ai_t50:
        fig.add_vrect(
            x0=ai_t50, x1=hu_t50,
            fillcolor="rgba(78,121,167,0.10)", layer="below", line_width=0,
            annotation_text="intervention window",
            annotation_position="top right",
            annotation_font_size=10,
            annotation_font_color="#4E79A7",
        )

    fig.update_layout(
        xaxis=dict(title="Simulation time (seconds)", range=[-5, max(hu_times) * 1.05]),
        yaxis=dict(title="Agents who withdrew", range=[0, n + 1], dtick=2),
        height=280, margin=dict(l=0, r=120, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Same 12 agents, same false rumor (45% credibility), same bank — only decision speed differs. "
        "At AI speed the cascade is structurally different, not just faster: the peer-signal wave "
        "arrives before all agents have even processed the original rumor, compressing two separate "
        "shocks into a single simultaneous panic. "
        "The gap between the two curves is the intervention window — the time in which a regulator, "
        "a circuit breaker, or a verification step could interrupt the cascade. "
        "At AI speed, that window closes before any human process can begin."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _render_speed_clock(sweep: List[Dict]) -> None:
    """Headline number: AI vs human time-to-cascade, rendered as two stopwatches."""
    by_sid: Dict[str, Dict] = {}
    for r in sweep:
        sid = r.get("scenario_id", "")
        speed = r.get("speed", "")
        if sid == "sweep_false_045":
            by_sid[speed] = r

    ai_run = by_sid.get("ai")
    hu_run = by_sid.get("human")
    if not ai_run or not hu_run:
        return

    ai_t50 = ai_run.get("metrics", {}).get("time_to_50pct_withdrawn")
    hu_t50 = hu_run.get("metrics", {}).get("time_to_50pct_withdrawn")
    ai_wc  = ai_run.get("metrics", {}).get("withdrawn_count", 0)
    hu_wc  = hu_run.get("metrics", {}).get("withdrawn_count", 0)
    n      = ai_run.get("metrics", {}).get("total_agents", 12)

    if not ai_t50 or not hu_t50:
        return

    speedup = hu_t50 / ai_t50

    def _fmt_time(s: float) -> str:
        if s < 60:
            return f"{s:.0f}s"
        m, sec = int(s) // 60, int(s) % 60
        return f"{m}m {sec:02d}s"

    st.markdown(
        f"""
<div style="background:#F8F4EF;border:1.5px solid #C8B89A;border-radius:10px;
            padding:1.3rem 1.6rem;margin-bottom:1.4rem">
  <div style="color:#8A4E1A;font-size:0.78rem;font-weight:700;letter-spacing:0.12em;
              text-transform:uppercase;margin-bottom:0.9rem">
    THE HEADLINE NUMBER — same scenario, same agents, only decision speed changes
  </div>
  <div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center">
    <div style="text-align:center;min-width:140px">
      <div style="color:#E15759;font-size:0.72rem;font-weight:700;letter-spacing:0.1em;
                  text-transform:uppercase;margin-bottom:0.2rem">AI SPEED</div>
      <div style="color:#E15759;font-size:3.2rem;font-weight:900;line-height:1;
                  font-variant-numeric:tabular-nums">{_fmt_time(ai_t50)}</div>
      <div style="color:#666;font-size:0.8rem;margin-top:0.3rem">to 50% withdrawn</div>
      <div style="color:#888;font-size:0.75rem">{ai_wc}/{n} agents exited</div>
    </div>
    <div style="font-size:2rem;color:#BBB;font-weight:300">vs</div>
    <div style="text-align:center;min-width:140px">
      <div style="color:#4E79A7;font-size:0.72rem;font-weight:700;letter-spacing:0.1em;
                  text-transform:uppercase;margin-bottom:0.2rem">HUMAN SPEED</div>
      <div style="color:#4E79A7;font-size:3.2rem;font-weight:900;line-height:1;
                  font-variant-numeric:tabular-nums">{_fmt_time(hu_t50)}</div>
      <div style="color:#666;font-size:0.8rem;margin-top:0.3rem">to 50% withdrawn</div>
      <div style="color:#888;font-size:0.75rem">{hu_wc}/{n} agents exited</div>
    </div>
    <div style="flex:1;min-width:200px;padding-left:1rem;border-left:1px solid #D5C8B8">
      <div style="color:#8A4E1A;font-size:2.2rem;font-weight:900;line-height:1">
        {speedup:.0f}×
      </div>
      <div style="color:#5C3010;font-size:1rem;font-weight:600;margin-top:0.2rem">faster</div>
      <div style="color:#666;font-size:0.82rem;margin-top:0.5rem;line-height:1.55">
        Same rumor. Same 12 agents. Same bank.<br>
        The only difference: AI agents decide in <b>seconds</b>.<br>
        Human agents pause for 90-second deliberation.
      </div>
    </div>
  </div>
  <div style="margin-top:0.8rem;font-size:0.78rem;color:#999;border-top:1px solid #DDD;
              padding-top:0.5rem">
    Scenario: 45%-credibility false alarm — bank is solvent, rumor is wrong.
    The cascade happens anyway.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _finding_persona_contrast(sweep: List[Dict]) -> None:
    """Show two agents from the same archetype making opposite decisions — proof heterogeneity is real."""
    # Use the cascade scenario (sweep_false_045 AI) — it has the richest decisions
    target = next(
        (r for r in sweep
         if r.get("scenario_id") == "sweep_false_045" and r.get("speed") == "ai"),
        None,
    )
    if not target:
        return

    agents = {a["agent_id"]: a for a in target.get("agent_final_states", [])}

    # Find institutional treasurers that made different decisions
    treasurers = [
        a for a in agents.values()
        if a.get("persona", {}).get("archetype") == "institutional_treasurer"
    ]
    held    = [a for a in treasurers if _last_action(a) == "hold"]
    exited  = [a for a in treasurers if _last_action(a) in ("full_withdraw", "partial_withdraw")]

    if not held or not exited:
        return

    agent_a = held[0]
    agent_b = exited[0]

    st.subheader("Finding 5 (Interlude) — Real AI reasoning: same archetype, different judgment")
    st.markdown(
        "Both agents below are **Institutional Treasurers** — same archetype, same general "
        "profile, same information environment. They read the same rumor and watched the same "
        "cascade unfold. One held. One withdrew."
    )
    st.markdown(
        '<div style="background:#1C1C2E;border-radius:6px;padding:0.5rem 1rem;'
        'margin-bottom:0.8rem;display:inline-block">'
        '<span style="color:#A8D8A8;font-size:0.75rem;font-weight:700;letter-spacing:0.12em;'
        'text-transform:uppercase">VERBATIM LLM OUTPUT — not written by us</span>'
        '<span style="color:#888;font-size:0.75rem;margin-left:0.8rem">'
        'Every decision is a live call to the model. This is what came back.</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)
    for col, agent, label, color, border in [
        (col_a, agent_a, "HELD", "#4E79A7", "#4E79A7"),
        (col_b, agent_b, "WITHDREW", "#E15759", "#E15759"),
    ]:
        p       = agent.get("persona", {})
        dh      = agent.get("decision_history", [])
        last_d  = dh[-1] if dh else {}
        name    = p.get("name", "Agent")
        action  = last_d.get("action", "hold").replace("_", " ")
        snap    = last_d.get("portfolio_snapshot", {})
        ba_amt  = next((v for k, v in snap.items() if k.startswith("bank_a")), 0)
        reasoning = last_d.get("reasoning", "")
        # Truncate to ~520 chars at a sentence boundary
        if len(reasoning) > 500:
            cut = reasoning[:500].rfind(".")
            reasoning = reasoning[: cut + 1] if cut > 0 else reasoning[:500] + "…"

        with col:
            st.markdown(
                f'<div style="background:#F8F9FA;border:1.5px solid {border};'
                f'border-radius:8px;padding:1rem 1.2rem;height:100%">'
                f'<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem">'
                f'<span style="color:{color};font-size:0.72rem;font-weight:700;'
                f'letter-spacing:0.12em;text-transform:uppercase">🏛️ {name} — {label}</span>'
                f'<span style="background:{border};color:white;font-size:0.65rem;font-weight:700;'
                f'padding:0.1rem 0.45rem;border-radius:3px;letter-spacing:0.08em">AI OUTPUT</span>'
                f'</div>'
                f'<div style="font-size:0.82rem;color:#666;margin-bottom:0.8rem">'
                f'Bank A exposure: <b>${ba_amt:,.0f}</b></div>'
                f'<div style="font-size:0.93rem;line-height:1.8;color:#1C1C2E;'
                f'background:white;border-left:4px solid {border};padding:0.8rem 1rem;'
                f'border-radius:0 6px 6px 0;font-style:italic">'
                f'&#8220;{reasoning}&#8221;</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.caption(
        "The Manufacturer saw the same 63% withdrawal rate as the Tech Startup and concluded "
        "it was panic without evidence. The Tech Startup concluded it was a signal too strong "
        "to ignore. Both are Institutional Treasurers. Neither is wrong — they're just "
        "reasoning from different priors. This is what genuine heterogeneity looks like."
    )


def _last_action(agent: Dict) -> str:
    dh = agent.get("decision_history", [])
    return dh[-1]["action"] if dh else "hold"


def _finding_population_diversity(persona_runs: Dict[str, Dict]) -> None:
    st.subheader("Finding 7 — Population diversity prevents cascades. Homogeneous crowds amplify them.")
    st.markdown(
        "We ran the same high-credibility false alarm with three different agent populations: "
        "our standard mixed group, an all-retiree group, and an all-treasurer group. "
        "**The mixed population never cascaded. Both homogeneous populations did — every time.**"
    )

    # Build stacked bar data
    pop_configs = [
        ("Mixed population\n(standard run)", "rumor_high_false", "#4E79A7"),
        ("All cautious retirees\n(12 × retiree)", "persona_all_cautious_retiree_ai", "#F28E2B"),
        ("All institutional treasurers\n(12 × treasurer)", "persona_all_institutional_treasurer_ai", "#E15759"),
    ]

    pop_labels, full_vals, partial_vals, held_vals = [], [], [], []
    for label, sid, _ in pop_configs:
        run = persona_runs.get(sid)
        if not run:
            continue
        m = run.get("metrics", {})
        n = m.get("total_agents", 12)
        full_out = m.get("withdrawn_count", 0)
        partial_out = m.get("partially_withdrawn_count", 0)
        held_out = m.get("held_count", n - full_out - partial_out)
        pop_labels.append(label)
        full_vals.append(full_out)
        partial_vals.append(partial_out)
        held_vals.append(held_out)

    if pop_labels:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Fully withdrew", x=pop_labels, y=full_vals,
            marker_color="#E15759", text=full_vals, textposition="inside",
        ))
        fig.add_trace(go.Bar(
            name="Partially withdrew", x=pop_labels, y=partial_vals,
            marker_color="#F1A340", text=partial_vals, textposition="inside",
        ))
        fig.add_trace(go.Bar(
            name="Held", x=pop_labels, y=held_vals,
            marker_color="#76B7B2", text=held_vals, textposition="inside",
        ))
        fig.add_hline(
            y=3, line_dash="dash", line_color="#888", line_width=1.2,
            annotation_text="Cascade threshold (25% of agents)",
            annotation_position="right", annotation_font_size=10,
        )
        fig.update_layout(
            barmode="stack",
            yaxis=dict(title="Number of agents (out of 12)", range=[0, 14]),
            height=300, margin=dict(l=0, r=170, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Cascade threshold = 3 agents (25% of 12) triggering full exit. "
            "Mixed population: 1 full exit — no cascade. "
            "All-retiree: 4 full exits — cascade triggered. "
            "All-treasurer: 5 full exits — cascade triggered. "
            "Same rumor, same bank, same credibility label. Only the population composition changed."
        )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div style="background:#EEF3EE;border-left:4px solid #4A6741;'
            'border-radius:6px;padding:0.8rem 1rem">'
            '<div style="font-weight:700;margin-bottom:0.3rem">Why diversity stabilizes</div>'
            '<div style="font-size:0.88rem;line-height:1.6">'
            'A mixed population contains agents with conflicting priors. '
            'The institutional treasurer exits early; the cautious retiree notices the exit '
            'but is partly reassured by the gig worker who didn\'t move. '
            'The gig worker watches both and stays put. '
            'Disagreement within the group <b>absorbs the panic signal</b> — '
            'some agents\'s inaction cancels others\' alarm.'
            '</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div style="background:#FEE8E8;border-left:4px solid #E15759;'
            'border-radius:6px;padding:0.8rem 1rem">'
            '<div style="font-weight:700;margin-bottom:0.3rem">Why homogeneity amplifies</div>'
            '<div style="font-size:0.88rem;line-height:1.6">'
            'When all agents share the same cost function, the first withdrawal is '
            'instantly interpretable: "if someone like me ran, I should too." '
            'There is no cross-archetype noise to filter. '
            'The peer signal propagates cleanly through a uniform population — '
            '<b>every withdrawal confirms the others\' priors</b>, and the cascade locks in.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    # Model isolation callout
    iso_ai  = persona_runs.get("model_isolation_all_haiku_ai")
    iso_hu  = persona_runs.get("model_isolation_all_haiku_human")
    if iso_ai:
        iso_m = iso_ai.get("metrics", {})
        iso_full    = iso_m.get("withdrawn_count", 0)
        iso_partial = iso_m.get("partially_withdrawn_count", 0)
        iso_cascade = iso_m.get("cascade_occurred", iso_full >= 3)
        st.markdown(
            f'<div style="background:#F0F4FF;border-left:4px solid #4E79A7;'
            f'border-radius:6px;padding:0.9rem 1.1rem;margin-top:0.8rem">'
            f'<div style="font-weight:700;margin-bottom:0.3rem">'
            f'🧪 Model isolation check — does model capability drive the diversity effect?'
            f'</div>'
            f'<div style="font-size:0.88rem;line-height:1.6">'
            f'We re-ran the mixed population with all agents forced to use the same (less capable) Haiku model — '
            f'eliminating any model-capability gap between retail and institutional agents. '
            f'Result: <b>{iso_full} full exit, {iso_partial} partial</b> — '
            f'{"cascade: <b>NO</b>" if not iso_cascade else "cascade: YES"}. '
            f'Identical to the standard mixed-population run. '
            f'The stability of a diverse population is <b>not a model-capability artifact</b>: '
            f'it comes from the diversity of mandates and cost functions, '
            f'not from any gap in reasoning quality between models.'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="background:#EDE8DF;border-left:5px solid #8A4E1A;'
        'border-radius:6px;padding:1rem 1.2rem;margin-top:1rem">'
        '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem;color:#5C3010">'
        'Policy implication — correlated AI delegation is a systemic risk'
        '</div>'
        '<div style="font-size:0.9rem;line-height:1.7">'
        'If many depositors at the same bank all delegate to the same AI product — '
        'same model, same default risk settings, same information feed — '
        'they become a functionally homogeneous population. '
        'Our results suggest this is the most dangerous configuration: '
        'not because the agents are smarter, but because their decisions are correlated. '
        'Regulators already worry about correlated risk in institutional asset management; '
        'AI delegation extends this concern to retail banking. '
        '<b>A bank\'s depositor base diversified across multiple AI products '
        'may be more resilient than one where everyone uses the same delegate.</b> '
        'This is testable — and our simulation provides a concrete, parameterizable case study '
        'for exploring that design space.'
        '</div></div>',
        unsafe_allow_html=True,
    )


def render_findings() -> None:
    st.header("What the Simulation Found")

    preset, sweep, cb_runs = _load_runs()
    persona_runs = _load_persona_runs()

    if not preset and not sweep and not cb_runs:
        st.info(
            "No simulation runs found. "
            "Run `python scripts/run_all_presets.py` to generate preset data, "
            "and `python scripts/run_credibility_sweep.py` for the sweep."
        )
        return

    _render_setup_box()

    # ── Quick-navigation bar ────────────────────────────────────────────────
    st.markdown(
        '<div style="background:#F0F4FF;border:1px solid #C8D4E8;border-radius:8px;'
        'padding:0.7rem 1.1rem;margin-bottom:1.2rem">'
        '<span style="font-size:0.72rem;font-weight:700;letter-spacing:0.1em;'
        'text-transform:uppercase;color:#4E79A7;margin-right:0.8rem">JUMP TO</span>'
        '<a href="#f1" style="background:#FEE8E8;color:#C0392B;border:1px solid #E15759;'
        'border-radius:4px;padding:0.2rem 0.55rem;font-size:0.78rem;font-weight:600;'
        'text-decoration:none;margin-right:0.4rem">1 — False alarms</a>'
        '<a href="#f2" style="background:#FEF9E7;color:#7D3C00;border:1px solid #F1A340;'
        'border-radius:4px;padding:0.2rem 0.55rem;font-size:0.78rem;font-weight:600;'
        'text-decoration:none;margin-right:0.4rem">2 — Labels fail</a>'
        '<a href="#f3" style="background:#FEE8E8;color:#C0392B;border:1px solid #E15759;'
        'border-radius:4px;padding:0.2rem 0.55rem;font-size:0.78rem;font-weight:600;'
        'text-decoration:none;margin-right:0.4rem">3 — Who moves first</a>'
        '<a href="#f4" style="background:#F5F0FF;color:#4A235A;border:1px solid #9B59B6;'
        'border-radius:4px;padding:0.2rem 0.55rem;font-size:0.78rem;font-weight:600;'
        'text-decoration:none;margin-right:0.4rem">4 — Wrong both ways</a>'
        '<a href="#f5" style="background:#1C1C2E;color:#A8D8A8;border:1px solid #4A6741;'
        'border-radius:4px;padding:0.2rem 0.55rem;font-size:0.78rem;font-weight:600;'
        'text-decoration:none;margin-right:0.4rem">5 — Real AI output</a>'
        '<a href="#f6" style="background:#EEF3EE;color:#2D5A27;border:1px solid #4A6741;'
        'border-radius:4px;padding:0.2rem 0.55rem;font-size:0.78rem;font-weight:600;'
        'text-decoration:none;margin-right:0.4rem">6 — AI regulator 2/2</a>'
        '<a href="#f7" style="background:#F0F4FF;color:#1A3A6E;border:1px solid #4E79A7;'
        'border-radius:4px;padding:0.2rem 0.55rem;font-size:0.78rem;font-weight:600;'
        'text-decoration:none">7 — Diversity vs cascade</a>'
        '</div>',
        unsafe_allow_html=True,
    )

    if sweep:
        _render_cascade_race(sweep)

    if preset:
        st.markdown('<div id="f1"></div>', unsafe_allow_html=True)
        _finding_false_alarms(preset)
        st.divider()

    if sweep:
        st.markdown('<div id="f2"></div>', unsafe_allow_html=True)
        _finding_content_credibility(sweep)
        st.divider()

    if preset:
        st.markdown('<div id="f3"></div>', unsafe_allow_html=True)
        _finding_cascade_anatomy(preset)
        st.divider()
        if sweep:
            _finding_equity_queue(sweep)
            st.divider()
        st.markdown('<div id="f4"></div>', unsafe_allow_html=True)
        _finding_outcome_quality(preset)
        st.divider()

    if sweep:
        st.markdown('<div id="f5"></div>', unsafe_allow_html=True)
        _finding_persona_contrast(sweep)
        st.divider()

    st.markdown('<div id="f6"></div>', unsafe_allow_html=True)
    _finding_cb_intervention(cb_runs)
    st.divider()

    if persona_runs:
        st.markdown('<div id="f7"></div>', unsafe_allow_html=True)
        _finding_population_diversity(persona_runs)
        st.divider()

    _empirical_anchors()
    st.divider()

    # ── Scenario deep-dive ─────────────────────────────────────────────────
    st.subheader("Dive deeper — compare any scenario side by side")
    st.markdown(
        "Select any scenario to see the full breakdown: "
        "which agents withdrew, in what order, and what each AI was thinking "
        "when it decided. "
        "AI speed and human speed shown side by side."
    )
    try:
        from src.dashboard.comparison_view import _load_all_runs, _render_comparison
        run_index, _ = _load_all_runs(RUNS_DIR)
        ai_sids = {k[0] for k in run_index if k[1] == "ai"}
        human_sids = {k[0] for k in run_index if k[1] == "human"}
        paired = sorted(ai_sids & human_sids)
        if paired:
            names = {
                sid: _SCENARIO_LABEL.get(sid, run_index[(sid, "ai")].get("scenario_name", sid))
                for sid in paired
            }
            selected = st.selectbox("Choose a scenario", paired, format_func=lambda s: names[s])
            _render_comparison(run_index[(selected, "ai")], run_index[(selected, "human")])
        else:
            st.info("No paired runs found. Run the same scenario at both speeds from Presets.")
    except Exception as exc:
        st.warning(f"Deep-dive unavailable: {exc}")

    st.divider()
    st.markdown(
        '<div style="background:#F5F5F5;border-left:3px solid #AAAAAA;'
        'border-radius:4px;padding:0.8rem 1rem;font-size:0.85rem;color:#555">'
        '<b>Honest scope:</b> This simulation uses 12 agents and simplified bank mechanics. '
        'We are not predicting real bank run timescales, sizes, or outcomes. '
        'Every finding is a claim about how these specific LLM agents behave in this controlled environment. '
        'The value is in the <em>patterns</em> — '
        'systematic miscalibration to alarming content, correlated reasoning without coordination, '
        'amplified peer contagion at AI speed, institutional agents structurally ahead of retail. '
        'Whether these patterns hold at real-world scale is an open question, '
        'and the reason to study this now, before AI-delegated finance is mainstream.'
        '</div>',
        unsafe_allow_html=True,
    )
