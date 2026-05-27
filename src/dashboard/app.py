"""
Streamlit dashboard entry point for the AI Bank Run Sandbox.

Launch with:
    streamlit run src/dashboard/app.py

Three views:
  Presets    — pick a scenario, tweak parameters, run the simulation.
  Live View  — scrub through the pre-rendered run: graph + event timeline.
  Inspect    — click any agent, read their LLM reasoning.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(
    page_title="AI Bank Run Sandbox",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

_defaults = {
    "run_result": None,          # dict from RunResult.to_dict()
    "playback_slider": 0.0,      # current scrub position (sim seconds) — drives the slider widget
    "is_playing": False,         # auto-play flag
    "selected_agent_id": None,   # agent selected in Inspect view
    "nav_page": "Presets",     # active page — set programmatically to navigate
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🏦 AI Bank Run Sandbox")
    st.caption("Studying AI agent behavior under financial stress")
    st.divider()

    _pages = ["Presets", "Live View", "Inspect", "Findings", "Sandbox"]
    # Drain any programmatic nav request BEFORE the widget renders
    # (writing to a widget-bound key after instantiation raises StreamlitAPIException)
    _pending = st.session_state.pop("_pending_nav", None)
    if _pending in _pages:
        st.session_state.nav_page = _pending
    elif st.session_state.get("nav_page") not in _pages:
        st.session_state.nav_page = "Presets"
    page = st.radio(
        "nav",
        _pages,
        label_visibility="collapsed",
        key="nav_page",
    )

    st.divider()

    if st.session_state.run_result:
        m = st.session_state.run_result.get("metrics", {})
        n = m.get("total_agents", 0)
        pct = m.get("final_withdrawal_fraction", 0.0)
        cascade = m.get("cascade_triggered", False)
        t50 = m.get("time_to_50pct_deposits_paid") or m.get("time_to_50pct_withdrawn")

        # Count by decision intent from agent_final_states
        agents = st.session_state.run_result.get("agent_final_states", [])
        n_ran = m.get("attempted_exit_count")
        if n_ran is None:
            n_ran = sum(
                1 for a in agents
                if a.get("decision_history") and
                a["decision_history"][-1].get("action") in ("full_withdraw", "partial_withdraw")
            )
        # Count agents who actually received any money
        all_events = st.session_state.run_result.get("events", [])
        n_paid_out = m.get("paid_out_count")
        if n_paid_out is None:
            n_paid_out = len({
                e["agent_id"] for e in all_events
                if e.get("event_type") == "withdrawal_processed" and e.get("amount_paid_out", 0) > 0
            })
        st.caption(f"**Last run:** {st.session_state.run_result.get('scenario_name', '—')}")
        st.metric("Tried to exit", f"{n_ran} / {n}")
        st.metric("Got cash out", f"{n_paid_out} / {n}")
        st.metric("Bank A paid out", f"{pct:.1%}")
        st.metric("Cascade", "🔥 YES" if cascade else "✓ no")
        if t50 is not None:
            st.metric("Time to 50%", f"{t50:.0f}s")
    else:
        st.caption("No run yet — go to Presets.")

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

if page == "Presets":
    from src.dashboard.scenario_panel import render_configure
    render_configure()

elif page == "Live View":
    from src.dashboard.live_view import render_live_view
    render_live_view()

elif page == "Inspect":
    from src.dashboard.reasoning_view import render_inspect
    render_inspect()

elif page == "Findings":
    from src.dashboard.findings_view import render_findings
    render_findings()

elif page == "Sandbox":
    from src.dashboard.sandbox_view import render_sandbox
    render_sandbox()
