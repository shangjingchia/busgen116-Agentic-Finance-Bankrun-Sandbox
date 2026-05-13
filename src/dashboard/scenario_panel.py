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
        speed = "AI speed" if "_ai_" in stem else "Human speed" if "_human_" in stem else ""
        return f"{cred_label}  ·  {speed}" if speed else cred_label

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
    st.header("Configure")

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
            selected_run = st.selectbox(
                "Saved runs",
                saved,
                format_func=lambda p: _format_run_stem(p.stem),
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

                if _cb_type:
                    cols = st.columns(4)
                    cols[0].metric("Speed", _speed or "—")
                    cols[1].metric("CB", "🤖 AI" if _cb_type == "llm" else "📋 Rule")
                    cols[2].metric("Withdrew", f"{_withdrew} / {_total}")
                    cols[3].metric("Cascade", "🔥 yes" if _cascade else "✓ no")
                else:
                    cols = st.columns(3)
                    cols[0].metric("Speed", _speed or "—")
                    cols[1].metric("Withdrew", f"{_withdrew} / {_total}")
                    cols[2].metric("Cascade", "🔥 yes" if _cascade else "✓ no")

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
                st.toast(f"Loaded — navigating to Live View")
                st.session_state.nav_page = "Live View"
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
            speed_label = st.radio(
                "Speed",
                ["AI Speed", "Human Speed"],
                help=(
                    "**AI Speed**: decisions fire instantly. "
                    "**Human Speed**: 90-second deliberation delay per decision."
                ),
            )

        scenario_template = preset_scenarios[selected_idx]
        rumor = scenario_template.rumors[0]

        st.markdown(
            f'<div style="background:#EDE8DF;border-left:3px solid #8A7560;'
            f'border-radius:4px;padding:0.9rem 1.1rem;font-size:0.95rem;'
            f'line-height:1.6;margin:0.5rem 0">'
            f'{scenario_template.description}<br><br>'
            f'<span style="color:#5A4E3C;font-weight:600">Rumor agents will receive:</span><br>'
            f'<span style="font-style:italic">&#8220;{rumor.content}&#8221;</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        pa, pb = st.columns(2)
        with pa:
            credibility = st.slider(
                "Rumor credibility",
                min_value=0.0, max_value=1.0,
                value=float(rumor.credibility), step=0.05,
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
            s.rumors[0].credibility = credibility
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
    from dotenv import load_dotenv
    load_dotenv()

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
            f"Done — **{m.withdrawn_count}/{m.total_agents}** withdrew · "
            f"Bank A paid out **{m.final_withdrawal_fraction:.1%}** · "
            f"Cascade: **{'YES 🔥' if m.cascade_triggered else 'no'}**"
        )

        st.markdown("")
        if st.button("→ Go to Live View", type="primary"):
            st.session_state.nav_page = "Live View"
            st.rerun()

    except Exception as exc:
        progress.empty()
        status.error(f"Simulation failed: {exc}")
        raise
