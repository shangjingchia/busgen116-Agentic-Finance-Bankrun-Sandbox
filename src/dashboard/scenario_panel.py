"""
Configure page: select preset, tweak parameters, run the simulation.

The simulation is run synchronously here (blocking) and the result is stored
in st.session_state for the Live View and Inspect pages to read.
Running in a separate thread avoids asyncio conflicts with Streamlit's event loop.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import json
from pathlib import Path

import streamlit as st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCENARIO_LABELS = {
    # CB variants first — must match before their base-scenario IDs (startswith logic)
    "rumor_high_false_llm_cb":  "Strong rumor — bank fine · AI Central Bank",
    "rumor_high_false_rule_cb": "Strong rumor — bank fine · Rule-Based CB",
    "rumor_high_true_llm_cb":   "Strong rumor — bank failing · AI Central Bank",
    "rumor_high_true_rule_cb":  "Strong rumor — bank failing · Rule-Based CB",
    # Base scenarios
    "rumor_high_false":     "Strong rumor — bank is actually fine",
    "rumor_high_true":      "Strong rumor — bank really is failing",
    "rumor_moderate_false": "Moderate rumor — bank is actually fine",
    "rumor_weak_false":     "Weak rumor — bank is actually fine",
    "rumor_weak_true":      "Weak rumor — bank really is failing",
}

# Curated demo runs shown in the main dropdown, in presentation order.
# Key: (scenario_id, speed).  Value: human-readable label.
_FEATURED_RUNS = {
    ("rumor_high_false",        "ai"):    "Strong rumor · Bank healthy · AI speed",
    ("rumor_high_false",        "human"): "Strong rumor · Bank healthy · Human speed",
    ("rumor_high_true",         "ai"):    "Strong rumor · Bank failing · AI speed",
    ("rumor_high_true",         "human"): "Strong rumor · Bank failing · Human speed",
    ("rumor_moderate_false",    "ai"):    "Moderate rumor · Bank healthy · AI speed",
    ("rumor_moderate_false",    "human"): "Moderate rumor · Bank healthy · Human speed",
    ("rumor_weak_false",        "ai"):    "Weak rumor · Bank healthy · AI speed",
    ("rumor_weak_false",        "human"): "Weak rumor · Bank healthy · Human speed",
    ("rumor_weak_true",         "ai"):    "Weak rumor · Bank failing · AI speed",
    ("rumor_weak_true",         "human"): "Weak rumor · Bank failing · Human speed",
    ("sweep_false_045",         "ai"):    "Cascade scenario · 45% credibility · Bank healthy · AI speed",
    ("sweep_false_045",         "human"): "Cascade scenario · 45% credibility · Bank healthy · Human speed",
    ("sweep_false_045_llm_cb",  "ai"):    "AI Central Bank · Cascade scenario · 45% credibility",
    ("sweep_false_045_rule_cb", "ai"):    "Rule-based CB · Cascade scenario · 45% credibility",
    ("rumor_high_true_llm_cb",  "ai"):    "AI Central Bank · Strong rumor · Bank failing",
    ("rumor_high_true_rule_cb", "ai"):    "Rule-based CB · Strong rumor · Bank failing",
}


def _format_run_stem(stem: str) -> str:
    """Turn a raw filename stem into a readable label."""
    for sid, label in _SCENARIO_LABELS.items():
        if stem.startswith(sid):
            rest = stem[len(sid):].lstrip("_")
            speed = "AI speed" if rest.startswith("ai") else "Human speed" if rest.startswith("human") else ""
            # Pull date from the 8-digit segment
            date_str = ""
            for part in rest.split("_"):
                if len(part) == 8 and part.isdigit():
                    date_str = f"{part[6:]}/{part[4:6]}/{part[:4]}"
                    break
            parts = [label, speed]
            if date_str:
                parts.append(date_str)
            return "  ·  ".join(p for p in parts if p)

    if stem.startswith("sweep_false_"):
        parts = stem.split("_")
        cred = next((p for p in parts[2:] if p.isdigit() and len(p) == 3), "")
        cred_label = f"Credibility sweep {int(cred)}%" if cred else "Credibility sweep"
        cb_badge = (
            " · AI Central Bank" if "_llm_cb" in stem
            else " · Rule-Based CB" if "_rule_cb" in stem
            else ""
        )
        speed = "AI speed" if "_ai_" in stem else "Human speed" if "_human_" in stem else ""
        parts_out = [cred_label + cb_badge, speed]
        return "  ·  ".join(p for p in parts_out if p)

    if stem.startswith("sweep_latency_"):
        # e.g. sweep_latency_000_ai or sweep_latency_100_hum
        _LATENCY_LABELS = {
            "000": "Latency sweep — AI speed (~1–3s)",
            "050": "Latency sweep — 0.5× human (~2–5s)",
            "100": "Latency sweep — 1.0× human (natural)",
            "200": "Latency sweep — 2.0× human (slow)",
            "400": "Latency sweep — 4.0× human (very slow)",
        }
        parts = stem.split("_")
        bucket = next((p for p in parts if p.isdigit() and len(p) == 3), "")
        return _LATENCY_LABELS.get(bucket, f"Latency sweep {bucket}")

    return stem


def _load_run_file(path: Path) -> None:
    with open(path, encoding="utf-8") as f:
        st.session_state.run_result = json.load(f)
    st.session_state.playback_slider = 0.0
    st.session_state.is_playing = False
    st.session_state.selected_agent_id = None


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------


def render_configure() -> None:
    st.markdown(
        '<h1 style="font-size:1.6rem;font-weight:900;letter-spacing:-0.02em;'
        'color:#1A1A2E;margin-bottom:0.1rem">Presets</h1>'
        '<p style="font-size:0.88rem;color:#777;margin-top:0;margin-bottom:1rem">'
        'Load a pre-computed run for an instant demo, or generate a new one with live LLM calls.</p>',
        unsafe_allow_html=True,
    )

    from src.scenarios.presets import PRESETS

    preset_ids = [pid for pid, _, _ in PRESETS]
    preset_labels = [label for _, label, _ in PRESETS]
    preset_scenarios = [s for _, _, s in PRESETS]

    runs_dir = Path(__file__).parent.parent.parent / "runs"
    saved = sorted(
        [p for p in runs_dir.glob("*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    load_tab, run_tab = st.tabs(["📂  Load saved run", "▶  Run new simulation"])

    # ── Load tab (the demo path) ─────────────────────────────────────────
    with load_tab:
        st.markdown(
            "Choose a pre-run scenario to load instantly — "
            "no LLM calls required. This is the recommended path for live demos."
        )

        if not saved:
            st.info(
                "No saved runs yet. "
                "Run `python scripts/run_all_presets.py` to generate preset data, "
                "then reload this page."
            )
        else:
            # Build index: (scenario_id, speed) -> latest path (oldest-first so newer overwrites).
            # Sandbox runs carry a unique scenario_id each, so they are never deduped away.
            _run_index = {}
            _label_by_path = {}   # friendly labels for custom sandbox runs
            for p in sorted(saved, key=lambda x: x.stat().st_mtime):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    sid = d.get("scenario_id", "")
                    spd = d.get("speed", "")
                    if sid and spd in ("ai", "human"):
                        _run_index[(sid, spd)] = p
                        if sid.startswith("custom_"):
                            nm = d.get("scenario_name") or d.get("name") or "Custom run"
                            spd_lbl = "AI speed" if spd == "ai" else "Human speed"
                            sa = d.get("started_at", "")
                            date_str = f"{sa[8:10]}/{sa[5:7]}/{sa[0:4]}" if len(sa) >= 10 else ""
                            _label_by_path[p] = "  ·  ".join(
                                x for x in [f"🧪 {nm}", spd_lbl, date_str] if x
                            )
                except Exception:
                    continue

            # Featured: ordered by _FEATURED_RUNS insertion order
            _featured_items = [(k, _run_index[k]) for k in _FEATURED_RUNS if k in _run_index]
            _featured_paths = [p for _, p in _featured_items]
            _path_to_label = {p: _FEATURED_RUNS[k] for k, p in _featured_items}

            # Research: everything not in featured
            _research_items = sorted(
                [(k, p) for k, p in _run_index.items() if k not in _FEATURED_RUNS],
                key=lambda x: x[1].stat().st_mtime, reverse=True,
            )

            selected_run = st.selectbox(
                "Saved runs",
                _featured_paths,
                format_func=lambda p: _path_to_label[p],
                label_visibility="collapsed",
            )

            # Preview the selected run's scenario description
            try:
                _preview = json.loads(selected_run.read_text(encoding="utf-8"))
                _desc = _preview.get("scenario_description") or _preview.get("description", "")
                _speed = {"ai": "AI speed (instant decisions)", "human": "Human speed (90-second deliberation)"}.get(
                    _preview.get("speed", ""), ""
                )
                _m = _preview.get("metrics", {})
                _withdrew = _m.get("withdrawn_count", "—")
                _total = _m.get("total_agents", 12)
                _cascade = _m.get("cascade_triggered")
                _cb_type = _m.get("cb_policy_type")

                def _mini(label: str, value: str) -> str:
                    return (
                        f'<div style="font-size:0.75rem;color:#888;font-weight:600;'
                        f'text-transform:uppercase;letter-spacing:0.05em">{label}</div>'
                        f'<div style="font-size:0.9rem;font-weight:600;color:#222">{value}</div>'
                    )

                if _cb_type:
                    cols = st.columns(4)
                    cols[0].markdown(_mini("Speed", _speed or "—"), unsafe_allow_html=True)
                    cols[1].markdown(_mini("CB", "🤖 AI" if _cb_type == "llm" else "📋 Rule"), unsafe_allow_html=True)
                    cols[2].markdown(_mini("Withdrew", f"{_withdrew} / {_total}"), unsafe_allow_html=True)
                    cols[3].markdown(_mini("Cascade", "🔥 yes" if _cascade else "✓ no"), unsafe_allow_html=True)
                else:
                    cols = st.columns(3)
                    cols[0].markdown(_mini("Speed", _speed or "—"), unsafe_allow_html=True)
                    cols[1].markdown(_mini("Withdrew", f"{_withdrew} / {_total}"), unsafe_allow_html=True)
                    cols[2].markdown(_mini("Cascade", "🔥 yes" if _cascade else "✓ no"), unsafe_allow_html=True)

                if _desc:
                    st.markdown(
                        f'<div style="background:#EDE8DF;border-left:3px solid #8A7560;'
                        f'border-radius:4px;padding:0.7rem 1rem;font-size:0.9rem;'
                        f'line-height:1.6;margin:0.4rem 0">{_desc}</div>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass

            st.markdown("")
            if st.button("Load and view →", type="primary", use_container_width=False):
                _load_run_file(selected_run)
                st.toast("Loaded — opening Inspect")
                st.session_state._pending_nav = "Inspect"
                st.rerun()

            # Research runs — tucked away, not needed during the demo
            if _research_items:
                st.markdown("")
                with st.expander(f"Research & sweep runs ({len(_research_items)} scenarios)", expanded=False):
                    st.caption(
                        "Credibility sweeps, latency experiments, persona isolation runs, "
                        "and your saved 🧪 Sandbox runs (each kept separately). "
                        "These power the Findings charts but aren't needed for the live demo."
                    )
                    _res_paths = [p for _, p in _research_items]
                    _res_run = st.selectbox(
                        "Research runs",
                        _res_paths,
                        format_func=lambda p: _label_by_path.get(p) or _format_run_stem(p.stem),
                        label_visibility="collapsed",
                        key="research_run_select",
                    )
                    if st.button("Load research run →", use_container_width=False, key="load_research"):
                        _load_run_file(_res_run)
                        st.toast("Loaded — opening Inspect")
                        st.session_state._pending_nav = "Inspect"
                        st.rerun()

    # ── Run tab ──────────────────────────────────────────────────────────
    with run_tab:
        st.markdown(
            "Make real LLM calls and generate a new run. "
            "Takes 30–90 seconds. Use this to demonstrate live generation."
        )

        col_preset, col_speed = st.columns([3, 1])

        with col_preset:
            selected_idx = st.selectbox(
                "Scenario",
                range(len(preset_labels)),
                format_func=lambda i: preset_labels[i],
            )

        with col_speed:
            speed_label = st.selectbox(
                "Speed",
                ["AI Speed", "Human Speed"],
                help=(
                    "**AI Speed**: decisions fire instantly. "
                    "**Human Speed**: 90-second deliberation delay per decision."
                ),
            )

        scenario_template = preset_scenarios[selected_idx]
        if scenario_template.rumors:
            _rumor_content = scenario_template.rumors[0].content
            _rumor_credibility = float(scenario_template.rumors[0].credibility)
        else:
            first_signal = scenario_template.signals[0]
            _rumor_content = first_signal.content
            _rumor_credibility = float(first_signal.base_credibility)

        st.markdown(
            f'<div style="background:#EDE8DF;border-left:3px solid #8A7560;'
            f'border-radius:4px;padding:0.9rem 1.1rem;font-size:0.95rem;'
            f'line-height:1.6;margin:0.5rem 0">'
            f'{scenario_template.description}<br><br>'
            f'<span style="color:#5A4E3C;font-weight:600">Rumor agents will receive:</span><br>'
            f'<span style="font-style:italic">&#8220;{_rumor_content}&#8221;</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        pa, pb = st.columns(2)
        with pa:
            credibility = st.slider(
                "Rumor credibility",
                min_value=0.0, max_value=1.0,
                value=_rumor_credibility, step=0.05,
                help="0 = completely unbelievable  ·  1 = absolute certainty",
            )
        with pb:
            _default_vis = 1.0 if speed_label == "AI Speed" else 0.55
            social_visibility = st.slider(
                "Peer activity visible to agents",
                min_value=0.0, max_value=1.0,
                value=_default_vis, step=0.05,
                key=f"vis_{speed_label}",
                help=(
                    "Fraction of peer withdrawals visible on the social feed. "
                    "AI Speed: 1.0 (agents monitor feeds continuously). "
                    "Human Speed: 0.55 (humans see a filtered, delayed subset)."
                ),
            )

        # ── Central Bank toggle ───────────────────────────────────────────
        st.markdown("")
        with st.expander("🏛 Central Bank intervention (optional)", expanded=False):
            enable_cb = st.checkbox("Enable Central Bank", value=False)
            if enable_cb:
                cb_col1, cb_col2 = st.columns(2)
                with cb_col1:
                    cb_type_label = st.radio(
                        "Policy type",
                        ["🤖 AI-powered (LLM)", "📋 Rule-based (fixed threshold)"],
                        help=(
                            "**AI-powered**: the CB makes a real LLM call and chooses "
                            "the intervention in context. "
                            "**Rule-based**: fires a pre-configured guarantee announcement "
                            "when the threshold is crossed, without reasoning."
                        ),
                    )
                with cb_col2:
                    cb_threshold = st.slider(
                        "Trigger threshold",
                        min_value=0.10, max_value=0.60,
                        value=0.25, step=0.05,
                        help="Fraction of agents who must fully withdraw before the CB acts.",
                    )
                    st.caption(f"CB fires at {int(cb_threshold * 100)}% withdrawn")
            else:
                enable_cb = False

        st.markdown("")
        btn_col, note_col = st.columns([1, 3])
        with btn_col:
            run_pressed = st.button("▶ Run", type="primary", use_container_width=True)
        with note_col:
            cb_note = " · CB enabled" if enable_cb else ""
            st.caption(f"12 agents · {int(round(credibility * 100))}% credibility · {speed_label.lower()}{cb_note}")

        if run_pressed:
            import random as _random
            from src.core.scenario import CentralBankConfig, ScenarioSpeed

            s = copy.deepcopy(scenario_template)
            if s.rumors:
                s.rumors[0].credibility = credibility
            else:
                for sig in s.signals:
                    if sig.alarm_level > 0:
                        sig.base_credibility = credibility
            s.social_signal_visibility = social_visibility
            s.seed = _random.randint(0, 9999)
            s.speed = ScenarioSpeed.AI_SPEED if speed_label == "AI Speed" else ScenarioSpeed.HUMAN_SPEED

            if enable_cb:
                s.central_bank = CentralBankConfig(
                    policy_type="llm" if "AI" in cb_type_label else "rule_based",
                    trigger_threshold=cb_threshold,
                    model="anthropic/claude-sonnet-4.5",
                )
            else:
                s.central_bank = None

            _run_and_store(s)


# ---------------------------------------------------------------------------
# Simulation runner
# ---------------------------------------------------------------------------


def _run_and_store(scenario) -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv()

    if not os.environ.get("OPENROUTER_API_KEY"):
        st.warning(
            "⚠️ Live runs are disabled on this hosted demo — no `OPENROUTER_API_KEY` is "
            "configured. Explore the pre-saved simulations via **📂 Load saved run** above. "
            "(To launch new runs, clone the repo and run locally with your own key.)"
        )
        return

    from src.core.simulation import run_scenario
    from src.decisions.llm_client import LLMClient
    from src.personas.instances import make_all_agents

    agents = make_all_agents()
    client = LLMClient()
    runs_dir = Path(__file__).parent.parent.parent / "runs"

    status = st.empty()
    progress = st.progress(0, text="Initialising agents...")
    status.info("Running simulation — making real LLM calls. Takes 30–90 seconds at AI speed.")
    progress.progress(15, text="Agents observing rumor...")

    try:
        def _run():
            return asyncio.run(
                run_scenario(scenario, agents, llm_client=client, runs_dir=runs_dir, verbose=False)
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(_run).result(timeout=600)

        progress.progress(100, text="Complete!")
        st.session_state.run_result = result.to_dict()
        st.session_state.playback_slider = 0.0
        st.session_state.is_playing = False
        st.session_state.selected_agent_id = None

        m = result.metrics
        status.success(
            f"Done — **{m.attempted_exit_count}/{m.total_agents}** tried to exit · "
            f"**{m.paid_out_count}/{m.total_agents}** got cash · "
            f"Bank A paid out **{m.final_withdrawal_fraction:.1%}** · "
            f"Cascade: **{'YES 🔥' if m.cascade_triggered else 'no'}**"
        )

        st.markdown("")
        if st.button("→ Inspect agent reasoning", type="primary"):
            st.session_state._pending_nav = "Inspect"
            st.rerun()

    except Exception as exc:
        progress.empty()
        status.error(f"Simulation failed: {exc}")
        st.stop()
