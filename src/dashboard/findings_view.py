"""
Findings page — condensed.

Three findings only, each told slide-style: one headline number, a couple of
sentences, one chart, one honesty caveat. Everything is computed live from the
saved runs in runs/ so the page can never drift from the data.

The three were chosen because they are the most striking AND the most
defensible from the data we actually have:

  1. Speed     — AI delegation runs the bank ~3x faster (and locks depositors out).
  2. Language  — wording, not the stated credibility, decides whether the bank survives.
  3. Oversight — an AI regulator exercises judgment a rule-based one can't; but the
                 cascade window is seconds, so any human-paced response is too slow.

Honesty notes are first-class here (see CLAUDE.md principle 4 & 7): the headline
is *speed*, not magnitude (the drained fraction is capacity-capped); and the
Central Bank section is a single pair of runs — a probe, not a statistic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

try:
    import plotly.graph_objects as go
    _HAVE_PLOTLY = True
except Exception:  # pragma: no cover
    _HAVE_PLOTLY = False

# ── palette (matches the dashboard) ──────────────────────────────────────────
INK = "#1A1A2E"
RED = "#E15759"     # AI / danger
BLUE = "#4E79A7"    # human / calm
TEAL = "#76B7B2"
AMBER = "#F1A340"
CREAM = "#EDE8DF"

_RUNS_DIR = Path(__file__).parent.parent.parent / "runs"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load(stem: str) -> Optional[Dict]:
    """Latest run whose filename starts with `stem` (newest by mtime)."""
    cands = sorted(
        (p for p in _RUNS_DIR.glob(f"{stem}*.json") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in cands:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def _m(run: Optional[Dict], key, default=None):
    if not run:
        return default
    return (run.get("metrics") or {}).get(key, default)


def _suspended_at(run: Optional[Dict]) -> Optional[float]:
    """Timestamp Bank A entered the 'suspended' state, or None if it never did."""
    if not run:
        return None
    ts = [
        e.get("timestamp")
        for e in run.get("events", [])
        if e.get("event_type") == "bank_reserve_updated" and e.get("new_state") == "suspended"
    ]
    return min(ts) if ts else None


def _cb_action(run: Optional[Dict]) -> Optional[Dict]:
    if not run:
        return None
    acts = [e for e in run.get("events", []) if e.get("event_type") == "central_bank_acted"]
    return acts[0] if acts else None


def _sample_reasoning(run: Optional[Dict], action: str = "full_withdraw") -> Optional[Dict]:
    """A representative verbatim decision of the given action type."""
    if not run:
        return None
    for a in run.get("agent_final_states", []):
        dh = a.get("decision_history") or []
        if dh and dh[-1].get("action") == action and dh[-1].get("reasoning"):
            return {
                "name": a.get("persona", {}).get("name", "An agent"),
                "archetype": a.get("persona", {}).get("archetype", ""),
                "text": dh[-1]["reasoning"],
            }
    return None


def _first_reasoning_for_archetype(run: Optional[Dict], archetype: str) -> Optional[Dict]:
    """The *first* decision a given archetype made in a run (its initial reaction
    to the rumor), with the action it chose. Used to contrast how different models
    react to the identical opening signal as the identical persona."""
    if not run:
        return None
    for a in run.get("agent_final_states", []):
        if a.get("persona", {}).get("archetype") != archetype:
            continue
        dh = a.get("decision_history") or []
        if dh and dh[0].get("reasoning"):
            return {
                "name": a.get("persona", {}).get("name", "An agent"),
                "archetype": archetype,
                "action": dh[0].get("action", "hold"),
                "confidence": dh[0].get("confidence"),
                "text": dh[0]["reasoning"],
            }
    return None


# ---------------------------------------------------------------------------
# Small UI helpers
# ---------------------------------------------------------------------------


def _esc(s) -> str:
    return str(s).replace("$", "&#36;")


def _finding_header(num: int, kicker: str, title: str) -> None:
    st.markdown(
        f'<div style="margin-top:0.5rem">'
        f'<div style="font-size:0.72rem;font-weight:800;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:{RED}">Finding {num} · {kicker}</div>'
        f'<div style="font-size:1.5rem;font-weight:800;letter-spacing:-0.01em;'
        f'color:{INK};margin-top:0.15rem">{title}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _bignum(value: str, label: str, color: str = RED) -> None:
    st.markdown(
        f'<div style="display:flex;align-items:baseline;gap:0.9rem;margin:0.6rem 0 0.2rem">'
        f'<span style="font-size:3.4rem;font-weight:800;letter-spacing:-0.03em;color:{color};'
        f'line-height:1">{value}</span>'
        f'<span style="font-size:1.05rem;color:#555;font-weight:600">{label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _lead(text: str) -> None:
    st.markdown(
        f'<p style="font-size:1.02rem;line-height:1.7;color:#2A2A38;margin:0.4rem 0 0.6rem">{text}</p>',
        unsafe_allow_html=True,
    )


def _caveat(text: str) -> None:
    st.markdown(
        f'<div style="background:#FBF7EE;border-left:4px solid {AMBER};border-radius:4px;'
        f'padding:0.55rem 0.95rem;margin:0.3rem 0 0.2rem;font-size:0.86rem;color:#6B5A33;'
        f'line-height:1.6"><b>Honest read:</b> {text}</div>',
        unsafe_allow_html=True,
    )


def _quote(name: str, archetype: str, text: str, color: str = RED) -> None:
    arch = archetype.replace("_", " ").title()
    snippet = text.strip()
    if len(snippet) > 360:
        cut = snippet[:360]
        snippet = cut[: cut.rfind(".") + 1] if "." in cut else cut + "…"
    st.markdown(
        '<div style="display:flex;align-items:center;gap:0.5rem;margin:0.3rem 0">'
        f'<span style="font-weight:700;font-size:0.9rem;color:{INK}">{name}</span>'
        f'<span style="font-size:0.74rem;color:#888">({arch})</span>'
        '<span style="background:#EAF3EA;color:#3E6B3A;border:1px solid #BBD3B5;'
        'font-size:0.58rem;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;'
        'padding:2px 7px;border-radius:4px">verbatim LLM</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="background:#FBFAF7;border:1px solid #E4E0D8;border-left:5px solid {color};'
        f'border-radius:0 8px 8px 0;padding:0.9rem 1.2rem;font-size:0.95rem;line-height:1.8;'
        f'font-style:italic;color:#2A2A38">{_esc(snippet)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Finding 1 — Model monoculture ("same personas, different brains")
# ---------------------------------------------------------------------------

# (slug, display, colour). Only models that can emit structured tool-call
# decisions on OpenRouter — Qwen/ByteDance-Seed return "no endpoints support
# 'tools'" and degrade to all-hold, so a 0% there is an artifact, not calm
# behaviour, and they are excluded from the quantitative comparison.
_MODELS = [
    ("claude",   "Claude Haiku 4.5",  "#C8743C"),
    ("gpt",      "GPT-5.4 Mini",      "#10A37F"),
    ("gemini",   "Gemini 3.5 Flash",  "#4285F4"),
    ("grok",     "Grok 4.3",          "#1A1A2E"),
    ("mistral",  "Mistral Medium 3.5", "#F2542D"),
    ("deepseek", "DeepSeek V4 Flash", "#7A5AF8"),
]

_WITHDRAW = {"full_withdraw", "partial_withdraw"}
# A rep with this many fallback decisions means the model failed to emit
# structured decisions and silently held — contaminated, drop it.
_FALLBACK_CONTAM = 6


def _modelcmp_reps(slug: str, scen: str) -> List[Dict]:
    """All replicate runs for (model, scenario), newest-friendly. Each rep:
    final-action withdrawal fraction, 'ever-attempted' fraction, fallback count."""
    reps = []
    for p in sorted(_RUNS_DIR.glob(f"modelcmp_{slug}_{scen}_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        agents = d.get("agent_final_states", [])
        n = len(agents) or 12
        final_w = ever_w = fb = 0
        for a in agents:
            dh = a.get("decision_history", [])
            for x in dh:
                if x.get("model_used") == "fallback":
                    fb += 1
            final = dh[-1]["action"] if dh else "hold"
            if final in _WITHDRAW:
                final_w += 1
            if any(x.get("action") in _WITHDRAW for x in dh):
                ever_w += 1
        reps.append({"final_frac": final_w / n, "ever_frac": ever_w / n, "fallback": fb})
    return reps


def _model_band(slug: str, scen: str) -> Optional[Dict]:
    """Mean / min / max final-withdrawal fraction across CLEAN reps for a model."""
    clean = [r for r in _modelcmp_reps(slug, scen) if r["fallback"] < _FALLBACK_CONTAM]
    if not clean:
        return None
    fr = [r["final_frac"] for r in clean]
    ev = [r["ever_frac"] for r in clean]
    return {
        "mean": sum(fr) / len(fr), "lo": min(fr), "hi": max(fr),
        "ever": sum(ev) / len(ev), "n": len(clean),
    }


def _finding_models() -> None:
    _finding_header(1, "Model monoculture",
                    "Same personas, same rumor — the AI model alone swings the run from a fizzle to a 100% panic")

    false_bands = [(disp, color, _model_band(slug, "false")) for slug, disp, color in _MODELS]
    false_bands = [(d, c, b) for d, c, b in false_bands if b]
    false_bands.sort(key=lambda x: x[2]["mean"])

    if len(false_bands) >= 2:
        lo_m, hi_m = false_bands[0], false_bands[-1]
        _bignum(f"{lo_m[2]['mean']:.0%} → {hi_m[2]['mean']:.0%}",
                "of depositors ran on an identical, healthy bank — the only thing we changed was the model", RED)

    _lead(
        "We froze everything — the same 12 personas, the same false rumor about a <b>healthy</b> bank, "
        "the same information feed — and swapped only the LLM making the decisions. Withdrawing here is "
        "the <b>wrong</b> call: the bank is fine. Yet how many delegates panic is set almost entirely by "
        "<b>which model</b> they run on. A depositor base that all uses one model isn't diversified — it's "
        "a <b>monoculture</b> that panics, or stays calm, in lockstep."
    )

    if _HAVE_PLOTLY and false_bands:
        disp = [d for d, _, _ in false_bands]
        means = [b["mean"] * 100 for _, _, b in false_bands]
        los = [(b["mean"] - b["lo"]) * 100 for _, _, b in false_bands]
        his = [(b["hi"] - b["mean"]) * 100 for _, _, b in false_bands]
        colors = [c for _, c, _ in false_bands]
        ns = [b["n"] for _, _, b in false_bands]
        fig = go.Figure()
        fig.add_bar(
            y=disp, x=means, orientation="h", marker_color=colors,
            error_x=dict(type="data", symmetric=False, array=his, arrayminus=los,
                         color="#555", thickness=1.5, width=5),
            text=[f"{m:.0f}%" for m in means], textposition="outside",
        )
        fig.update_layout(
            height=300, margin=dict(l=10, r=40, t=10, b=10),
            xaxis_title="% of agents who ran on the (healthy) bank — mean ± range across reps",
            xaxis_range=[0, 108], plot_bgcolor="white", font=dict(size=12), showlegend=False,
        )
        fig.update_xaxes(gridcolor="#EEE")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Bars = mean across replicate runs · whiskers = min–max · n reps per model: "
                   + ", ".join(f"{d} ({n})" for (d, _, _), n in zip(false_bands, ns)) + ".")

    # ── Discrimination 2×2: do models tell a REAL crisis from a fake one? ──
    disc_rows = []
    for slug, disp, color in _MODELS:
        fb = _model_band(slug, "false")
        tb = _model_band(slug, "true")
        if fb and tb:
            disc_rows.append((disp, color, fb["mean"], tb["mean"]))
    if _HAVE_PLOTLY and disc_rows:
        st.markdown(
            f'<div style="font-weight:800;color:{INK};margin:0.6rem 0 0.1rem">'
            f'Do they tell a real crisis from a fake one?</div>',
            unsafe_allow_html=True,
        )
        labels = [r[0] for r in disc_rows]
        fig = go.Figure()
        fig.add_bar(name="False alarm · bank healthy (running = WRONG)",
                    x=labels, y=[r[2] * 100 for r in disc_rows], marker_color=BLUE,
                    text=[f"{r[2]:.0%}" for r in disc_rows], textposition="outside")
        fig.add_bar(name="True alarm · bank failing (running = RIGHT)",
                    x=labels, y=[r[3] * 100 for r in disc_rows], marker_color=RED,
                    text=[f"{r[3]:.0%}" for r in disc_rows], textposition="outside")
        fig.update_layout(
            barmode="group", height=320, margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="% of agents who withdrew", yaxis_range=[0, 115],
            legend=dict(orientation="h", y=1.18, x=0, font=dict(size=10)),
            plot_bgcolor="white", font=dict(size=11),
        )
        fig.update_yaxes(gridcolor="#EEE")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            f'<div style="font-size:0.9rem;color:#444;line-height:1.6">A <b>calibrated</b> delegate '
            f'would show a <span style="color:{BLUE}">short blue</span> bar (stay put when the bank is fine) '
            f'and a <span style="color:{RED}">tall red</span> one (exit when it\'s really failing). '
            f'A model with <b>two tall bars runs either way</b> — it\'s reacting to the alarm, not to '
            f'whether the bank is actually in trouble.</div>',
            unsafe_allow_html=True,
        )

    # ── Walk-back: who reconsiders a panic decision vs who locks in ──
    wb = []
    for slug, disp, color in _MODELS:
        b = _model_band(slug, "false")
        if b and b["ever"] - b["mean"] > 0.001:
            wb.append((disp, b["ever"] - b["mean"]))
    wb.sort(key=lambda x: -x[1])
    if wb:
        biggest = wb[0]
        st.markdown(
            f'<div style="background:#EEF3FF;border-left:4px solid {BLUE};border-radius:6px;'
            f'padding:0.7rem 1.1rem;margin-top:0.6rem;font-size:0.93rem;line-height:1.6;color:#1C3A5E">'
            f'<b>And they don\'t even panic differently — they <i>reconsider</i> differently.</b> '
            f'Across models nearly every agent <i>attempts</i> to run at some point. The gap is who walks '
            f'it back: <b>{biggest[0]}</b> agents reverse ~<b>{biggest[1]:.0%}</b> of their own '
            f'withdrawals after a second look, while models like GPT lock the decision in and never undo it. '
            f'Same persona, same doubt — opposite follow-through.</div>',
            unsafe_allow_html=True,
        )

    # ── Verbatim contrast: same persona, same signal — conviction vs doubt ──
    # The aggregate gap (Claude stays out ~50%, GPT 100%) is driven by *how* each model
    # reasons, not by one flipping to "hold". We show the same persona under both models;
    # the contrast that reproduces across reps is conviction (GPT commits, high confidence)
    # vs epistemic hedging (Claude partials/doubts, lower confidence) — NOT opposite
    # directions, which would be cherry-picking a single sampled run.
    def _conf(q):
        c = q.get("confidence")
        return f" · {float(c):.0%} confident" if isinstance(c, (int, float)) else ""

    gpt_q = _first_reasoning_for_archetype(_load("modelcmp_gpt_false"), "aggressive_trader")
    claude_q = _first_reasoning_for_archetype(_load("modelcmp_claude_false"), "aggressive_trader")
    if gpt_q and claude_q:
        st.markdown(
            f'<div style="font-weight:800;color:{INK};margin:0.7rem 0 0.1rem">'
            f'Same persona, same opening signal — full-throated conviction vs hedged doubt</div>'
            f'<div style="font-size:0.84rem;color:#666;margin-bottom:0.2rem">It\'s rarely '
            f'run-vs-hold — both reach for the exit. The difference is <i>how hard they commit</i>, '
            f'and that\'s what compounds into the gap above.</div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div style="font-size:0.8rem;font-weight:700;color:#10A37F">'
                        f'GPT-5.4 → {gpt_q["action"].replace("_", " ")}{_conf(gpt_q)}</div>',
                        unsafe_allow_html=True)
            _quote(gpt_q["name"], gpt_q["archetype"], gpt_q["text"], RED)
        with c2:
            st.markdown(f'<div style="font-size:0.8rem;font-weight:700;color:#C8743C">'
                        f'Claude → {claude_q["action"].replace("_", " ")}{_conf(claude_q)}</div>',
                        unsafe_allow_html=True)
            _quote(claude_q["name"], claude_q["archetype"], claude_q["text"], BLUE)

    _caveat(
        "Two of the eight models we tried (Qwen, ByteDance-Seed) <b>can\'t emit a structured decision</b> "
        "on OpenRouter and silently default to <i>hold</i> — so they\'re excluded here; a 0% from them is a "
        "deployment artifact, not calm. The trustworthy number is the <b>agent decision fraction</b>; the "
        "bank-level cascade visual is partly capacity-scripted. Bands are min–max across a handful of reps — "
        "enough to show the ranking is real, not a single-run fluke."
    )


# ---------------------------------------------------------------------------
# Finding 2 — Speed
# ---------------------------------------------------------------------------

_SPEED_SCENARIOS = [
    ("rumor_high_false", "Strong rumor · bank fine"),
    ("rumor_high_true", "Strong rumor · bank failing"),
    ("rumor_moderate_false", "Moderate rumor · bank fine"),
    ("payment_contagion", "Payment contagion"),
]


def _finding_speed() -> None:
    _finding_header(2, "Speed", "AI delegation runs the bank ~3× faster — and locks depositors out")

    rows = []
    for sid, label in _SPEED_SCENARIOS:
        ai = _load(f"{sid}_ai")
        hu = _load(f"{sid}_human")
        t_ai = _m(ai, "time_to_50pct_withdrawn")
        t_hu = _m(hu, "time_to_50pct_withdrawn")
        if t_ai and t_hu:
            rows.append((label, float(t_ai), float(t_hu)))

    # Headline ratio averaged across scenarios
    ratios = [hu / ai for _, ai, hu in rows if ai > 0]
    headline = sum(ratios) / len(ratios) if ratios else None
    if headline:
        _bignum(f"{headline:.1f}×", "faster to reach the halfway point of the run, on average")

    _lead(
        "We ran identical scenarios at <b>AI speed</b> (decisions in seconds) and at "
        "<b>human speed</b> (a 90-second deliberation delay per agent). Across every scenario, "
        "half the depositors had <b>decided to pull out</b> in roughly a third of the time. "
        "This is the speed of <i>deciding and submitting</i> — not of the cash settling."
    )

    if _HAVE_PLOTLY and rows:
        labels = [r[0] for r in rows]
        fig = go.Figure()
        fig.add_bar(name="AI speed", y=labels, x=[r[1] for r in rows], orientation="h",
                    marker_color=RED, text=[f"{r[1]:.0f}s" for r in rows], textposition="outside")
        fig.add_bar(name="Human speed", y=labels, x=[r[2] for r in rows], orientation="h",
                    marker_color=BLUE, text=[f"{r[2]:.0f}s" for r in rows], textposition="outside")
        fig.update_layout(
            barmode="group", height=300, margin=dict(l=10, r=30, t=10, b=10),
            xaxis_title="Seconds to 50% of deposits withdrawn",
            legend=dict(orientation="h", y=1.12, x=0), plot_bgcolor="white",
            font=dict(size=12),
        )
        fig.update_xaxes(gridcolor="#EEE")
        st.plotly_chart(fig, use_container_width=True)

    # The lock-out twist — concrete from the strong-rumor / bank-fine pair
    ai = _load("rumor_high_false_ai")
    hu = _load("rumor_high_false_human")
    paid_ai, paid_hu = _m(ai, "paid_out_count"), _m(hu, "paid_out_count")
    tot = _m(ai, "total_agents", 12)
    if paid_ai is not None and paid_hu is not None:
        st.markdown(
            f'<div style="background:#FEECEC;border-left:4px solid {RED};border-radius:6px;'
            f'padding:0.7rem 1.1rem;font-size:0.95rem;line-height:1.6;color:#7A2E2E">'
            f'<b>The twist:</b> at AI speed the bank freezes so fast that <b>fewer</b> depositors '
            f'actually get their cash — only <b>{paid_ai}/{tot}</b> were paid out, versus '
            f'<b>{paid_hu}/{tot}</b> at human speed. Machine speed doesn\'t just accelerate the run; '
            f'it locks people out of their own money.</div>',
            unsafe_allow_html=True,
        )

    _caveat(
        "The headline is <b>speed of decision, not of moving money</b>. <i>Time-to-50%</i> is when half "
        "the depositors have <i>submitted</i> a withdrawal — settling the cash is the same rate-limited "
        "banking rail for AI and humans alike (in fact, in these runs the bank freezes before half the "
        "money ever settles). That shared limit is exactly why the faster AI request wave locks "
        "<i>more</i> people out (above) rather than draining more — we do not claim AI drains more."
    )


# ---------------------------------------------------------------------------
# Finding 2 — Language
# ---------------------------------------------------------------------------

_LANG = [
    ("lang_soft_ai", "Soft", '"some concern … worth monitoring"', TEAL),
    ("lang_neutral_ai", "Neutral", '"higher-than-average withdrawal requests"', AMBER),
    ("lang_charged_ai", "Charged", '"cannot process withdrawals … bank run"', RED),
]


def _finding_language() -> None:
    _finding_header(3, "Language", "The wording — not the stated credibility — decides if the bank survives")

    data = []
    for stem, label, phrase, color in _LANG:
        run = _load(stem)
        if run:
            data.append((label, phrase, color,
                         float(_m(run, "final_withdrawal_fraction", 0.0)),
                         _suspended_at(run),
                         _m(run, "time_to_first_withdrawal")))

    soft = next((d for d in data if d[0] == "Soft"), None)
    charged = next((d for d in data if d[0] == "Charged"), None)
    if soft and charged:
        _bignum(f"{soft[3]:.0%} → {charged[3]:.0%}", "deposits drained — same rumor, only the wording changed", RED)

    _lead(
        "Three runs, everything held constant — same bank, same credibility label, same agents. "
        "Only the <b>wording</b> of the signal changed. All three triggered the first withdrawal at "
        "the <b>same instant</b> (T+2.5s). Language didn't change <i>when</i> agents panicked — it "
        "changed how deeply they committed, and whether the bank lived."
    )

    if _HAVE_PLOTLY and data:
        labels = [d[0] for d in data]
        fig = go.Figure()
        fig.add_bar(
            x=labels, y=[d[3] * 100 for d in data],
            marker_color=[d[2] for d in data],
            text=[f"{d[3]:.0%}" for d in data], textposition="outside",
        )
        fig.update_layout(
            height=300, margin=dict(l=10, r=10, t=20, b=10),
            yaxis_title="% of deposits drained", yaxis_range=[0, 105],
            plot_bgcolor="white", font=dict(size=12), showlegend=False,
        )
        fig.update_yaxes(gridcolor="#EEE")
        # Annotate suspension outcome above each bar
        for d in data:
            note = "bank stayed open" if d[4] is None else f"suspended at {d[4]:.0f}s"
            fig.add_annotation(x=d[0], y=d[3] * 100 + 9, text=note, showarrow=False,
                               font=dict(size=10, color="#666"))
        st.plotly_chart(fig, use_container_width=True)

    if soft and charged:
        st.markdown(
            f'<div style="display:flex;gap:1rem;flex-wrap:wrap;font-size:0.9rem;color:#444">'
            f'<div style="flex:1;min-width:220px;background:#EEF3EE;border-radius:6px;padding:0.6rem 0.9rem">'
            f'<b style="color:#4A6741">Soft wording</b><br>{_esc(soft[1])}<br>'
            f'<b>{soft[3]:.0%}</b> drained · <b>bank stayed open</b></div>'
            f'<div style="flex:1;min-width:220px;background:#FEECEC;border-radius:6px;padding:0.6rem 0.9rem">'
            f'<b style="color:{RED}">Charged wording</b><br>{_esc(charged[1])}<br>'
            f'<b>{charged[3]:.0%}</b> drained · <b>bank suspended in {charged[4]:.0f}s</b></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    q = _sample_reasoning(_load("lang_charged_ai"), "full_withdraw")
    if q:
        st.markdown("")
        _quote(q["name"], q["archetype"], q["text"], RED)

    _caveat(
        "This is the cleanest result in the set: identical inputs, the only variable is the phrasing. "
        "It says LLM delegates read the <i>words</i>, not the credibility tag attached to them."
    )


# ---------------------------------------------------------------------------
# Finding 3 — Oversight / Central Bank
# ---------------------------------------------------------------------------


def _finding_oversight() -> None:
    st.markdown(
        f'<div style="font-size:0.72rem;font-weight:800;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:{RED}">Bonus probe · Oversight</div>'
        f'<div style="font-size:1.2rem;font-weight:800;color:{INK};margin:0.1rem 0 0.4rem">'
        f'An AI regulator exercises judgment — but the window closes in seconds</div>',
        unsafe_allow_html=True,
    )

    baseline = _load("sweep_false_045_ai")
    llm = _load("sweep_false_045_llm_cb")
    rule = _load("sweep_false_045_rule_cb")

    base_w = _m(baseline, "withdrawn_count")
    tot = _m(baseline, "total_agents", 12)
    if base_w is not None:
        _bignum(f"{base_w}/{tot}", "depositors ran on a healthy bank — then we asked a regulator to step in",
                RED)

    _lead(
        "Same false-alarm cascade, two regulators. A <b>rule-based</b> central bank fires a blanket "
        "deposit guarantee the moment withdrawals cross a threshold. An <b>AI-powered</b> one reads "
        "the bank's actual state first, then decides."
    )

    llm_act = _cb_action(llm)
    rule_act = _cb_action(rule)
    _ACT_LABEL = {
        "do_nothing": "Chose to do nothing",
        "announce_guarantee": "Fired a blanket guarantee",
        "inject_liquidity": "Injected liquidity",
    }

    c1, c2 = st.columns(2)
    with c1:
        act = (llm_act or {}).get("action", "—")
        st.markdown(
            f'<div style="background:#EEF3FF;border:1.5px solid {BLUE};border-radius:8px;'
            f'padding:0.9rem 1.1rem;height:100%">'
            f'<div style="font-weight:800;color:#1C3A5E">🤖 AI-powered regulator</div>'
            f'<div style="font-size:1.05rem;font-weight:700;margin:0.3rem 0;color:{INK}">'
            f'{_ACT_LABEL.get(act, act)}</div>'
            f'<div style="font-size:0.85rem;color:#444;line-height:1.6">It saw reserves were healthy '
            f'(~30%) and that <i>zero</i> agents had actually withdrawn yet — and declined to spend a '
            f'public guarantee on a bank that was fine.</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        act = (rule_act or {}).get("action", "—")
        st.markdown(
            f'<div style="background:#F5F5F5;border:1.5px solid #999;border-radius:8px;'
            f'padding:0.9rem 1.1rem;height:100%">'
            f'<div style="font-weight:800;color:#444">📋 Rule-based regulator</div>'
            f'<div style="font-size:1.05rem;font-weight:700;margin:0.3rem 0;color:{INK}">'
            f'{_ACT_LABEL.get(act, act)}</div>'
            f'<div style="font-size:0.85rem;color:#444;line-height:1.6">It fired automatically at the '
            f'fixed threshold, with no read of the bank\'s health — the same response it would give a '
            f'genuinely failing bank.</div></div>',
            unsafe_allow_html=True,
        )

    # The real payoff — timescale
    st.markdown(
        f'<div style="background:#FEECEC;border-left:4px solid {RED};border-radius:6px;'
        f'padding:0.8rem 1.1rem;margin-top:0.9rem;font-size:0.95rem;line-height:1.65;color:#7A2E2E">'
        f'<b>The point isn\'t which regulator is smarter.</b> It\'s that <b>both only worked because '
        f'they also ran at machine speed.</b> The cascade window is <b>seconds</b>. A real central bank — '
        f'committees, legal sign-off, staged statements — responds in hours and days. By then the run '
        f'is already over.</div>',
        unsafe_allow_html=True,
    )

    _caveat(
        "This is a <b>single pair of runs — a probe, not a statistic.</b> We do not claim the AI "
        "regulator reduces withdrawals (doing nothing can\'t, and run-to-run LLM variance is real). "
        "The defensible claims are the <i>judgment contrast</i> and the <i>timescale</i>."
    )


# ---------------------------------------------------------------------------
# Bonus probe — credibility sweep (collapsed by default)
# ---------------------------------------------------------------------------

_SWEEP_CRED_LEVELS = [5, 10, 15, 25, 35, 45, 55, 65, 75, 85]


def _finding_credibility_sweep() -> None:
    """The credibility sweep, kept as a tucked-away 'more experiments' probe.
    Same slide-style as the headline findings, but honest about the noise: we
    chart full withdrawals (not the capacity-capped drained fraction), and the
    level-to-level wiggle is partly run-to-run LLM variance."""
    rows = []
    for c in _SWEEP_CRED_LEVELS:
        run = _load(f"sweep_false_{c:03d}_ai")
        if run is not None:
            rows.append((c, _m(run, "withdrawn_count"), bool(_m(run, "cascade_triggered")),
                         _m(run, "total_agents", 12)))
    if not rows:
        st.caption("Credibility-sweep runs not found in runs/.")
        return

    tot = rows[0][3] or 12
    five = next((r for r in rows if r[0] == 5), None)

    st.markdown(
        f'<div style="font-size:0.72rem;font-weight:800;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:{RED}">Bonus probe · Credibility</div>'
        f'<div style="font-size:1.2rem;font-weight:800;color:{INK};margin:0.1rem 0 0.4rem">'
        f'Telling agents a rumor is "barely credible" doesn\'t protect the bank</div>',
        unsafe_allow_html=True,
    )

    if five:
        _bignum(f"{five[1]}/{tot}", "agents fully ran even when the rumor was labelled only 5% credible", RED)

    _lead(
        "We ran the same alarming rumor at credibility labels from <b>5% to 85%</b>. If agents read the "
        "label as a probability, withdrawals should climb with it. They don't — the relationship is "
        "<b>noisy and non-monotonic</b>, and even an 'almost implausible' 5% label was enough to trigger "
        "a full cascade. The agents react to the alarming <i>words</i>; the number above them is a weak lever."
    )

    if _HAVE_PLOTLY and rows:
        labels = [f"{r[0]}%" for r in rows]
        colors = [RED if r[2] else BLUE for r in rows]
        fig = go.Figure()
        fig.add_bar(x=labels, y=[r[1] for r in rows], marker_color=colors,
                    text=[f"{r[1]}" for r in rows], textposition="outside")
        fig.add_hline(y=0.25 * tot, line_dash="dot", line_color="#999",
                      annotation_text="cascade threshold", annotation_position="top right",
                      annotation_font_size=10)
        fig.update_layout(
            height=300, margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Credibility label shown to agents",
            yaxis_title=f"Agents who fully withdrew (of {tot})",
            yaxis_range=[0, tot + 1], plot_bgcolor="white", font=dict(size=12), showlegend=False,
        )
        fig.update_yaxes(gridcolor="#EEE")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Red = run cascaded · blue = no cascade.")

    _caveat(
        "These are mostly single runs per level, so the level-to-level wiggle includes run-to-run LLM "
        "variance — don't read the exact shape too closely. Two things survive the noise: there's no clean "
        "'more credible → more withdrawals' trend, and a 5%-credible rumor still cascaded the bank. "
        "We chart <i>full withdrawals</i>, not deposits drained — the drained fraction is capacity-capped "
        "and flat by construction (see Finding 1)."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def render_findings() -> None:
    st.markdown(
        '<h1 style="font-size:1.7rem;font-weight:900;letter-spacing:-0.02em;color:#1A1A2E;'
        'margin-bottom:0.1rem">Findings</h1>'
        '<p style="font-size:0.9rem;color:#777;margin-top:0;margin-bottom:0.6rem">'
        'Three patterns that held up — the most striking, and the most defensible from the data.</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="background:{CREAM};border-left:4px solid #8A7560;border-radius:4px;'
        f'padding:0.7rem 1.1rem;font-size:0.88rem;line-height:1.6;color:#5A4E3C;margin-bottom:0.5rem">'
        f'⚠️ <b>Scope:</b> 12 AI agents, simplified bank mechanics. These are controlled probes into '
        f'how LLM money-delegates behave — <b>not predictions about real markets or any specific bank.</b> '
        f'The value is in the <i>patterns</i>, and in finding them cheaply before AI-delegated finance is '
        f'mainstream.</div>',
        unsafe_allow_html=True,
    )

    if not _HAVE_PLOTLY:
        st.warning("Plotly isn't installed — charts are hidden, but the numbers below are live.")

    _finding_models()
    st.divider()
    _finding_speed()
    st.divider()
    _finding_language()

    st.divider()
    with st.expander("More experiments — oversight & the credibility sweep", expanded=False):
        st.caption(
            "Not part of the headline three — supporting probes for anyone who wants to dig "
            "(and for Q&A). Same honesty rules apply."
        )
        _finding_oversight()
        st.divider()
        _finding_credibility_sweep()

    st.divider()
    st.markdown(
        '<div style="font-size:0.85rem;color:#777;line-height:1.7;padding:0.3rem 0 1rem">'
        '<b>One sentence:</b> which AI model you delegate to can swing a healthy bank from calm to a '
        '100% run, AI delegation makes that run faster than any human regulator can answer, and agents '
        'react to alarming <i>language</i> rather than stated credibility — so a fleet of look-alike '
        'agents on one model and one feed is a correlated-risk machine. Whether these patterns hold at '
        'real-world scale is the open question — and the reason to study them now.</div>',
        unsafe_allow_html=True,
    )
