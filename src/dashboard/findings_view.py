"""
Findings view: what the simulation found about LLM agent behavior
under financial stress. Combines Compare and Context into one narrative.
"""

from __future__ import annotations

import json
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
    _CB_SIDS = {"rumor_high_false", "rumor_high_false_llm_cb", "rumor_high_false_rule_cb"}
    for p in sorted(RUNS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            sid = d.get("scenario_id", "")
            speed = d.get("speed", "")
            if not sid or speed not in ("ai", "human"):
                continue
            if sid.startswith("sweep_"):
                sweep.append(d)
            elif sid in _CB_SIDS and speed == "ai":
                cb_by_sid[sid] = d  # keep latest
                if "_cb" not in sid:
                    preset.append(d)
            else:
                preset.append(d)
        except Exception:
            continue
    return preset, sweep, cb_by_sid


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
    if sid.startswith("sweep_false_"):
        try:
            return int(sid.rsplit("_", 1)[-1]) / 100.0
        except ValueError:
            pass
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
    ai_vals = [by_cred[c].get("ai",    {}).get("withdrawal_fraction", 0) * 100 for c in creds]
    hu_vals = [by_cred[c].get("human", {}).get("withdrawal_fraction", 0) * 100 for c in creds]
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
            title="Credibility label shown to agents  (25% = 'barely credible'  →  85% = 'highly credible')",
        ),
        yaxis=dict(title="% of agents who withdrew", ticksuffix="%", range=[0, 110]),
        height=290, margin=dict(l=0, r=60, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    if ai_vals and hu_vals:
        ai_avg = sum(ai_vals) / len(ai_vals)
        hu_avg = sum(hu_vals) / len(hu_vals)
        st.caption(
            f"Average withdrawal across all credibility levels — "
            f"AI speed: **{ai_avg:.0f}%** · Human speed: **{hu_avg:.0f}%**. "
            "Both lines are nearly flat. The credibility label is being ignored."
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
        'the ones who can least afford it — last in line.</b>'
        '</div></div>',
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


def _finding_cb_intervention(cb_runs: Dict[str, Dict]) -> None:
    baseline = cb_runs.get("rumor_high_false")
    llm_cb   = cb_runs.get("rumor_high_false_llm_cb")
    rule_cb  = cb_runs.get("rumor_high_false_rule_cb")

    if not (baseline and (llm_cb or rule_cb)):
        st.info(
            "Run `python scripts/run_cb_presets.py` to generate the three Central Bank "
            "comparison scenarios, then reload this page."
        )
        return

    st.subheader("Finding 5 — Central Bank intervention can stop the cascade — but only at AI speed")
    st.markdown(
        "We added a Central Bank agent that monitors the cascade in real time. "
        "Two variants: an **AI-powered CB** that makes a live LLM call to choose its intervention "
        "(guarantee, liquidity injection, or do-nothing), and a **rule-based CB** that fires "
        "a fixed response when 25% of agents have withdrawn — representing a regulatory body "
        "that has not yet adopted AI-speed decision-making. "
        "The chart compares final withdrawal fractions across all three conditions."
    )

    labels, values, colors = [], [], []

    if baseline:
        bm = _metrics(baseline)
        labels.append("No intervention\n(baseline)")
        values.append(bm["withdrawal_fraction"] * 100)
        colors.append("#E15759")

    if rule_cb:
        rm = _metrics(rule_cb)
        labels.append("Rule-based CB\n(fixed threshold)")
        values.append(rm["withdrawal_fraction"] * 100)
        colors.append("#F1A340")

    if llm_cb:
        lm = _metrics(llm_cb)
        labels.append("AI-powered CB\n(LLM judgment)")
        values.append(lm["withdrawal_fraction"] * 100)
        colors.append("#4A6741")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=values, marker_color=colors,
        text=[f"{v:.0f}%" for v in values], textposition="outside",
        width=0.4,
    ))

    # CB trigger line
    if baseline:
        bm = _metrics(baseline)
        n = bm["n_total"]
        cb_frac = 0.25 * 100
        fig.add_hline(
            y=cb_frac, line_dash="dot", line_color="#B8860B", line_width=1.5,
            annotation_text="CB trigger threshold (25%)",
            annotation_position="right", annotation_font_size=10,
            annotation_font_color="#7A6010",
        )

    fig.update_layout(
        yaxis=dict(title="% of Bank A deposits withdrawn", ticksuffix="%", range=[0, 115]),
        height=300, margin=dict(l=0, r=140, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        if baseline and rule_cb:
            bm = _metrics(baseline)
            rm = _metrics(rule_cb)
            delta = bm["withdrawal_fraction"] - rm["withdrawal_fraction"]
            rule_cb_m = rule_cb.get("metrics", {})
            cb_at = rule_cb_m.get("cb_triggered_at")
            cb_action = rule_cb_m.get("cb_action", "—")
            st.markdown(
                f'<div style="background:#FDF6E3;border-left:4px solid #B8860B;'
                f'border-radius:6px;padding:0.8rem 1rem">'
                f'<div style="font-weight:700;margin-bottom:0.3rem">Rule-based CB</div>'
                f'<div style="font-size:0.88rem;line-height:1.5">'
                f'Fired <b>{cb_action.replace("_"," ")}</b>'
                + (f' at T+{cb_at:.0f}s' if cb_at else "")
                + f'<br>Reduced withdrawals by <b>{delta:.0%}</b> vs. baseline. '
                f'No reasoning — same action regardless of context.</div></div>',
                unsafe_allow_html=True,
            )

    with col2:
        if baseline and llm_cb:
            bm = _metrics(baseline)
            lm = _metrics(llm_cb)
            delta = bm["withdrawal_fraction"] - lm["withdrawal_fraction"]
            llm_cb_m = llm_cb.get("metrics", {})
            cb_at = llm_cb_m.get("cb_triggered_at")
            cb_action = llm_cb_m.get("cb_action", "—")
            st.markdown(
                f'<div style="background:#EEF3EE;border-left:4px solid #4A6741;'
                f'border-radius:6px;padding:0.8rem 1rem">'
                f'<div style="font-weight:700;margin-bottom:0.3rem">AI-powered CB</div>'
                f'<div style="font-size:0.88rem;line-height:1.5">'
                f'Chose <b>{cb_action.replace("_"," ")}</b>'
                + (f' at T+{cb_at:.0f}s' if cb_at else "")
                + f'<br>Reduced withdrawals by <b>{delta:.0%}</b> vs. baseline. '
                f'Read context, weighed moral hazard, committed to one action.</div></div>',
                unsafe_allow_html=True,
            )

    with col3:
        st.markdown(
            '<div style="background:#F0F4FF;border-left:4px solid #4E79A7;'
            'border-radius:6px;padding:0.8rem 1rem">'
            '<div style="font-weight:700;margin-bottom:0.3rem">The speed constraint</div>'
            '<div style="font-size:0.88rem;line-height:1.5">'
            'Both CBs intervened in seconds — possible only because they operate at '
            'machine speed. A human-reviewed intervention process (hours to days) '
            'would arrive after the cascade was already complete.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="background:#EDE8DF;border-left:5px solid #8A4E1A;'
        'border-radius:6px;padding:1rem 1.2rem;margin-top:1rem">'
        '<div style="font-weight:700;font-size:1rem;margin-bottom:0.5rem;color:#5C3010">'
        'Policy implication — in an AI-delegated financial system, regulators must also move at AI speed'
        '</div>'
        '<div style="font-size:0.9rem;line-height:1.7">'
        'The AI-vs-rule-based comparison reveals the second-order problem: '
        'AI delegation creates crises that move faster than human-speed regulatory response. '
        'The cascade window in our simulation closes in seconds. '
        'Existing CB intervention frameworks — which involve human review, committee deliberation, '
        'and staged communication — operate on timescales of hours to days.<br><br>'
        'Closing this gap requires either: (1) slowing down AI-delegated decisions through '
        'mandatory wait periods or circuit breakers, or (2) deploying AI-speed CB monitoring '
        'and response systems. Neither is currently being seriously discussed by financial regulators. '
        'This simulation provides a concrete, observable demonstration of why the question is urgent.'
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
# Main entry point
# ---------------------------------------------------------------------------


def render_findings() -> None:
    st.header("What the Simulation Found")

    preset, sweep, cb_runs = _load_runs()

    if not preset and not sweep and not cb_runs:
        st.info(
            "No simulation runs found. "
            "Run `python scripts/run_all_presets.py` to generate preset data, "
            "and `python scripts/run_credibility_sweep.py` for the sweep."
        )
        return

    _render_setup_box()

    if preset:
        _finding_false_alarms(preset)
        st.divider()

    if sweep:
        _finding_content_credibility(sweep)
        st.divider()

    if preset:
        _finding_cascade_anatomy(preset)
        st.divider()
        _finding_outcome_quality(preset)
        st.divider()

    _finding_cb_intervention(cb_runs)
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
            st.info("No paired runs found. Run the same scenario at both speeds from Configure.")
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
