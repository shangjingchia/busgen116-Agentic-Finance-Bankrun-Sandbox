"""
Streamlit dashboard entry point for the AI Bank Run Sandbox.

Launch with:
    streamlit run src/dashboard/app.py

Views:
  Presets   — pick a scenario, tweak parameters, run the simulation.
  Inspect   — click any agent, read their full LLM reasoning and outcome.
  Findings  — the cross-scenario results, incl. the payment-contagion story.
  Sandbox   — build custom personas and run your own scenario.
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

# ── Global CSS polish ────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* Hide Streamlit toolbar so it doesn't clip top content */
header[data-testid="stHeader"] { display: none !important; }
#MainMenu { visibility: hidden !important; }

/* Tighten default top padding (no toolbar to clear) */
.block-container { padding-top: 0.75rem !important; padding-bottom: 1rem !important; }

/* Stronger headers */
h1 { font-weight: 800 !important; letter-spacing: -0.02em !important; }
h2 { font-weight: 800 !important; letter-spacing: -0.01em !important; color: #1A1A2E !important; }
h3 { font-weight: 700 !important; }

/* Metric cards in sidebar */
[data-testid="stMetricValue"]  { font-weight: 800 !important; }
[data-testid="stMetricLabel"]  { font-weight: 600 !important; font-size: 0.82rem !important; color: #555 !important; }

/* Primary buttons — red glow */
.stButton > button[kind="primary"] {
    box-shadow: 0 3px 12px rgba(225,87,89,0.30) !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 5px 18px rgba(225,87,89,0.45) !important;
    transform: translateY(-1px);
}

/* Dividers */
hr { border-top: 1px solid #EAEAEA !important; margin: 1.3rem 0 !important; }

/* Tabs bold */
button[data-baseweb="tab"] { font-weight: 600 !important; }

/* Sidebar */
[data-testid="stSidebar"] { border-right: 1px solid #EAEAEA; }

/* Go-to-top button */
#go-top-btn {
    position: fixed;
    bottom: 2rem;
    right: 1.5rem;
    z-index: 9999;
    width: 42px;
    height: 42px;
    border-radius: 50%;
    background: #1A1A2E;
    color: white;
    font-size: 1.1rem;
    border: none;
    cursor: pointer;
    box-shadow: 0 2px 12px rgba(0,0,0,0.28);
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    transition: background 0.15s, transform 0.15s;
}
#go-top-btn:hover {
    background: #E15759;
    color: white;
    transform: translateY(-2px);
}

/* Cascade-suspended pulsing glow — triggered by class on the banner div */
@keyframes suspend-pulse {
    0%,100% { box-shadow: 0 0  0  0 rgba(225,87,89,0.00); }
    50%      { box-shadow: 0 0 28px 8px rgba(225,87,89,0.18); }
}
.cascade-suspended { animation: suspend-pulse 1.8s ease-in-out infinite; }
</style>
""",
    unsafe_allow_html=True,
)

# Top anchor + floating "back to top" link. Streamlit strips inline JS event
# handlers (onclick) from injected HTML, so a <button onclick> never fires —
# an anchor to a top-of-page <div id> works (same mechanism as the Findings nav).
st.markdown(
    '<div id="app-top" style="position:relative;scroll-margin-top:0"></div>'
    '<a href="#app-top" id="go-top-btn" title="Back to top">↑</a>',
    unsafe_allow_html=True,
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

    _pages = ["Presets", "Inspect", "Findings", "Sandbox"]
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
        st.caption(
            f"**Loaded:** {st.session_state.run_result.get('scenario_name', '—')}  \n"
            f"Run summary and per-agent reasoning are on the **Inspect** page."
        )
    else:
        st.caption("No run yet — go to Presets.")

    st.divider()
    st.caption(
        "Built by **Shang Jing Chia** · Stanford GSB · BUSGEN 116  \n"
        "[View source on GitHub]"
        "(https://github.com/shangjingchia/busgen116-Agentic-Finance-Bankrun-Sandbox)"
    )

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

if page == "Presets":
    from src.dashboard.scenario_panel import render_configure
    render_configure()

elif page == "Inspect":
    from src.dashboard.reasoning_view import render_inspect
    render_inspect()

elif page == "Findings":
    from src.dashboard.findings_view import render_findings
    render_findings()

elif page == "Sandbox":
    from src.dashboard.sandbox_view import render_sandbox
    render_sandbox()
