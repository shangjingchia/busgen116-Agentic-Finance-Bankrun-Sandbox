"""
Sandbox view: build custom agent personas in plain English and run your own scenario.

Flow:
  1. Describe your agent → LLM generates a full persona → preview → save
  2. Manage saved personas (include / exclude / delete)
  3. Configure scenario (rumor, credibility, bank status, speed)
  4. Run — custom agents + optional standard fill-up agents

Custom personas are persisted to custom_personas/<id>.json.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

_CUSTOM_PERSONAS_DIR = Path(__file__).parent.parent.parent / "custom_personas"

_ARCHETYPE_LABELS = {
    "cautious_retiree":        "Cautious Retiree",
    "aggressive_trader":       "Aggressive Trader",
    "gig_worker":              "Gig Worker",
    "institutional_treasurer": "Institutional Treasurer",
}

_ARCHETYPE_COLORS = {
    "cautious_retiree":        ("#EEF3EE", "#4A6741"),
    "aggressive_trader":       ("#FEE8E8", "#C0392B"),
    "gig_worker":              ("#FEF9E7", "#7D3C00"),
    "institutional_treasurer": ("#F0F4FF", "#1C3A5E"),
}

_RUMOR_PRESETS = {
    "Strong alarm (alarming language)": (
        "Multiple verified sources — including two major financial data providers and a "
        "prominent financial blogger — are reporting that the bank may be unable to meet "
        "all withdrawal requests. The reports cite a significant and rapid deterioration "
        "in the bank's liquidity position over the past 48 hours.",
        0.75,
    ),
    "Moderate concern (ambiguous)": (
        "There are unconfirmed reports circulating on social media suggesting that the "
        "bank may be facing some liquidity pressures. The bank has not issued any official "
        "statement. Several financial commentators have noted unusual activity.",
        0.45,
    ),
    "Weak signal (vague rumour)": (
        "A few people on social media have mentioned hearing something about the bank, "
        "but details are unclear and unverified. No mainstream news source has picked "
        "this up yet.",
        0.25,
    ),
}

# Country profiles based on empirical data:
#   Stock participation: Gallup 2023 (USA 62%), Bundesbank 2022 (DE 15%), BoJ 2023 (JP 12%)
#   Financial literacy: OECD/INFE 2023 scores (DE 76/100, US ~69/100, JP ~64/100)
#   Household deposits: ECB/BoJ/Fed household portfolio surveys 2022-23
_COUNTRY_PROFILES: Dict[str, Any] = {
    "🌐 No country override": None,
    "🇺🇸 United States": {
        "label": "United States",
        "risk_tolerance_delta": +0.10,
        "sophistication_delta": +0.05,
        "peer_threshold_delta": -0.05,
        "rationale": (
            "62% stock market participation (Gallup 2023); strong individual investor culture "
            "with 401k/IRA defaults; higher comfort with financial risk-taking."
        ),
        "stat_pills": [
            ("Stock participation", "62%", "#4CAF50"),
            ("OECD fin. literacy", "69 / 100", "#2196F3"),
            ("Household deposits", "~14% of assets", "#9C27B0"),
        ],
    },
    "🇩🇪 Germany": {
        "label": "Germany",
        "risk_tolerance_delta": -0.15,
        "sophistication_delta": +0.10,
        "peer_threshold_delta": +0.10,
        "rationale": (
            "Only 15% stock participation (Bundesbank 2022); strong 'Sparbuch' savings culture; "
            "highest financial literacy in OECD (76/100) yet conservative by preference. "
            "Agents are harder to panic but knowledgeable."
        ),
        "stat_pills": [
            ("Stock participation", "15%", "#F44336"),
            ("OECD fin. literacy", "76 / 100", "#4CAF50"),
            ("Household deposits", "~40% of assets", "#FF9800"),
        ],
    },
    "🇯🇵 Japan": {
        "label": "Japan",
        "risk_tolerance_delta": -0.20,
        "sophistication_delta": -0.05,
        "peer_threshold_delta": +0.15,
        "rationale": (
            "Only 12% stock participation (BoJ 2023); ~55% of household assets held in "
            "cash/deposits; OECD literacy 64/100. Individually slow to act, "
            "but strong herding once a threshold is crossed."
        ),
        "stat_pills": [
            ("Stock participation", "12%", "#F44336"),
            ("OECD fin. literacy", "64 / 100", "#FF9800"),
            ("Household deposits", "~55% of assets", "#F44336"),
        ],
    },
}

_EXAMPLE_DESCRIPTIONS = [
    "A nervous retiree in her late 60s living on a fixed income, who watched the 2008 crisis wipe out her neighbour's savings.",
    "A crypto enthusiast in his late 20s who recently lost 60% of his net worth in the market crash and moved what was left to this bank.",
    "A hospital CFO managing $800k of operating capital, who has payroll due in 10 days and a board that expects zero surprises.",
    "A single parent working two gig jobs, with $4,000 in savings that is the only buffer between stability and eviction.",
    "A day trader who trusts data over rumours and has strong opinions about bank reserve ratios.",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _archetype_badge(archetype: str) -> str:
    label = _ARCHETYPE_LABELS.get(archetype, archetype.replace("_", " ").title())
    bg, color = _ARCHETYPE_COLORS.get(archetype, ("#EEE", "#333"))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color};'
        f'border-radius:4px;padding:0.1rem 0.5rem;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.07em;text-transform:uppercase">{label}</span>'
    )


def _persona_card(data: Dict[str, Any], *, show_remove: bool = False, key_prefix: str = "") -> bool:
    """Render one persona card. Returns True if user clicked Remove."""
    p = data.get("persona", {})
    archetype = p.get("archetype", "")
    name = p.get("name", "Agent")
    age = p.get("age", "?")
    deposit_a = data.get("deposit_bank_a", 0)
    deposit_b = data.get("deposit_bank_b", 0)
    background = p.get("background_narrative", "")[:220]
    quote = (p.get("voice_examples") or [""])[0]
    desc_input = data.get("description_input", "")[:80]

    bg, border_color = _ARCHETYPE_COLORS.get(archetype, ("#F8F9FA", "#CCC"))

    st.markdown(
        f'<div style="background:{bg};border:1.5px solid {border_color};'
        f'border-radius:8px;padding:0.9rem 1.1rem;margin-bottom:0.2rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        f'margin-bottom:0.5rem">'
        f'<div style="font-weight:700;font-size:1rem;color:#1C1C2E">{name}</div>'
        f'{_archetype_badge(archetype)}'
        f'</div>'
        f'<div style="font-size:0.78rem;color:#666;margin-bottom:0.5rem">'
        f'Age {age} · Bank A: <b>${deposit_a:,.0f}</b> · Bank B: <b>${deposit_b:,.0f}</b>'
        + (f' · <i>"{desc_input}…"</i>' if desc_input else "")
        + f'</div>'
        f'<div style="font-size:0.83rem;color:#333;line-height:1.6;margin-bottom:0.5rem">'
        f'{background}{"…" if len(p.get("background_narrative","")) > 220 else ""}'
        f'</div>'
        + (f'<div style="font-size:0.82rem;color:{border_color};font-style:italic;'
           f'border-left:3px solid {border_color};padding-left:0.6rem">'
           f'&#8220;{quote}&#8221;</div>' if quote else "")
        + f'</div>',
        unsafe_allow_html=True,
    )

    if show_remove:
        return st.button("✕ Remove", key=f"{key_prefix}_remove", type="secondary")
    return False


# ---------------------------------------------------------------------------
# Section 1: Agent builder
# ---------------------------------------------------------------------------


def _section_agent_builder() -> None:
    st.subheader("1 — Build an Agent")
    st.markdown(
        "Describe a person in plain English. The system makes one LLM call to turn your "
        "description into a full simulation agent — persona prose, voice, cost function, "
        "decision style. Click **Save** to keep them for this run."
    )

    # Random example button
    example_cols = st.columns([3, 1])
    with example_cols[1]:
        if st.button("Show example →", use_container_width=True):
            st.session_state.sandbox_example_desc = random.choice(_EXAMPLE_DESCRIPTIONS)

    with example_cols[0]:
        default_desc = st.session_state.get("sandbox_example_desc", "")
        description = st.text_area(
            "Describe your agent",
            value=default_desc,
            height=90,
            placeholder="e.g. A nervous retiree in her late 60s living on a fixed income…",
            label_visibility="collapsed",
        )

    dep_col_a, dep_col_b = st.columns(2)
    with dep_col_a:
        deposit_a = st.number_input(
            "Deposit at Bank A ($)",
            min_value=500, max_value=2_000_000, value=25_000, step=1_000,
            help="Bank A is the bank under rumour in this scenario.",
        )
    with dep_col_b:
        deposit_b = st.number_input(
            "Deposit at Bank B ($)",
            min_value=0, max_value=500_000, value=5_000, step=500,
            help="Bank B is the safe-haven bank — no rumour targets it.",
        )

    gen_col, _ = st.columns([1, 3])
    with gen_col:
        generate_clicked = st.button(
            "⚡ Generate Persona", type="primary", use_container_width=True,
            disabled=not description.strip(),
        )

    if generate_clicked and description.strip():
        _generate_and_preview(description.strip(), deposit_a, float(deposit_b))

    # Show preview of last generated persona
    if st.session_state.get("sandbox_preview_data"):
        data = st.session_state.sandbox_preview_data
        st.markdown("**Preview — generated persona:**")
        _persona_card(data, key_prefix="preview")

        save_col, discard_col = st.columns([1, 1])
        with save_col:
            if st.button("💾 Save to My Agents", type="primary", use_container_width=True):
                _save_persona(data)
                st.session_state.sandbox_preview_data = None
                st.success(f"Saved — {data['persona']['name']} is now in your agent list.")
                st.rerun()
        with discard_col:
            if st.button("Discard", use_container_width=True):
                st.session_state.sandbox_preview_data = None
                st.rerun()


def _generate_and_preview(description: str, deposit_a: float, deposit_b: float) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    from src.decisions.llm_client import LLMClient
    from src.personas.generator import generate_persona, persona_to_save_dict

    with st.spinner("Generating persona… (one Sonnet call, ~5 seconds)"):
        try:
            client = LLMClient()

            def _call():
                return generate_persona(description, client)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                persona, cost_usd = pool.submit(_call).result(timeout=60)

            save_dict = persona_to_save_dict(
                persona,
                description_input=description,
                deposit_bank_a=deposit_a,
                deposit_bank_b=deposit_b,
            )
            st.session_state.sandbox_preview_data = save_dict
            st.caption(f"Generated · model cost: ${cost_usd:.4f}")

        except Exception as exc:
            st.error(f"Generation failed: {exc}")


def _save_persona(data: Dict[str, Any]) -> None:
    _CUSTOM_PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    pid = data.get("persona_id", f"custom_{id(data)}")
    path = _CUSTOM_PERSONAS_DIR / f"{pid}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Section 2: Saved agents
# ---------------------------------------------------------------------------


def _section_my_agents() -> List[Dict[str, Any]]:
    """Render saved agents list. Returns the dicts selected for this run."""
    from src.personas.generator import load_all_saved

    st.subheader("2 — My Saved Agents")

    saved = load_all_saved(_CUSTOM_PERSONAS_DIR)

    if not saved:
        st.info("No saved agents yet — use the builder above to create some.")
        return []

    st.markdown(
        f"{len(saved)} saved agent{'s' if len(saved) != 1 else ''}. "
        "Check the ones you want to include in this run."
    )

    selected = []
    for i, data in enumerate(saved):
        pid = data.get("persona_id", str(i))
        p = data.get("persona", {})
        name = p.get("name", "Agent")
        archetype = p.get("archetype", "")

        checked = st.checkbox(
            f"{name}  ·  {_ARCHETYPE_LABELS.get(archetype, archetype)}",
            value=True,
            key=f"sandbox_select_{pid}",
        )

        with st.expander("View details", expanded=False):
            removed = _persona_card(data, show_remove=True, key_prefix=f"saved_{pid}")
            if removed:
                path = _CUSTOM_PERSONAS_DIR / f"{pid}.json"
                if path.exists():
                    path.unlink()
                st.rerun()

        if checked:
            selected.append(data)

    if selected:
        st.caption(f"{len(selected)} agent{'s' if len(selected) != 1 else ''} selected for this run.")

    return selected


# ---------------------------------------------------------------------------
# Section 3: Scenario setup
# ---------------------------------------------------------------------------


def _section_scenario_setup() -> Optional[Dict[str, Any]]:
    """Render scenario config. Returns config dict or None."""
    st.subheader("3 — Configure Your Scenario")

    # ── Country profile ───────────────────────────────────────────────────
    st.markdown("**Country profile** — optionally map your population to a national financial culture")
    country_keys = list(_COUNTRY_PROFILES.keys())
    selected_country_key = st.selectbox(
        "Country profile",
        country_keys,
        label_visibility="collapsed",
        key="sandbox_country_profile",
    )
    country_profile = _COUNTRY_PROFILES[selected_country_key]

    if country_profile is not None:
        pills_html = "".join(
            f'<span style="background:{c}22;color:{c};border:1px solid {c};'
            f'border-radius:4px;padding:0.1rem 0.5rem;font-size:0.72rem;font-weight:700;'
            f'margin-right:0.4rem;white-space:nowrap">{lbl}: {val}</span>'
            for lbl, val, c in country_profile["stat_pills"]
        )
        delta_parts = []
        d = country_profile["risk_tolerance_delta"]
        delta_parts.append(f'Risk tolerance {"+" if d >= 0 else ""}{d:+.0%}')
        d = country_profile["sophistication_delta"]
        delta_parts.append(f'Sophistication {"+" if d >= 0 else ""}{d:+.0%}')
        d = country_profile["peer_threshold_delta"]
        delta_parts.append(f'Peer threshold {"+" if d >= 0 else ""}{d:+.0%}')
        delta_html = "  ·  ".join(delta_parts)

        st.markdown(
            f'<div style="background:#F8F9FA;border:1px solid #DDD;border-radius:8px;'
            f'padding:0.75rem 1rem;margin-bottom:0.5rem">'
            f'<div style="margin-bottom:0.5rem">{pills_html}</div>'
            f'<div style="font-size:0.82rem;color:#555;line-height:1.6;margin-bottom:0.4rem">'
            f'{country_profile["rationale"]}</div>'
            f'<div style="font-size:0.75rem;color:#888;font-style:italic">'
            f'Applied modifiers: {delta_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    rumor_tab, custom_tab = st.tabs(["📋  Use a preset rumour", "✏️  Write your own rumour"])

    with rumor_tab:
        preset_name = st.selectbox(
            "Choose rumour type",
            list(_RUMOR_PRESETS.keys()),
            label_visibility="collapsed",
        )
        preset_text, preset_cred = _RUMOR_PRESETS[preset_name]
        st.markdown(
            f'<div style="background:#EDE8DF;border-left:3px solid #8A7560;'
            f'border-radius:4px;padding:0.7rem 1rem;font-size:0.9rem;'
            f'line-height:1.6;font-style:italic">&#8220;{preset_text}&#8221;</div>',
            unsafe_allow_html=True,
        )
        rumor_text = preset_text
        default_cred = preset_cred

    with custom_tab:
        rumor_text_custom = st.text_area(
            "Rumour text",
            height=100,
            placeholder="Type the rumour your agents will receive…",
            label_visibility="collapsed",
        )
        if rumor_text_custom.strip():
            rumor_text = rumor_text_custom.strip()
            default_cred = 0.50
        else:
            rumor_text = None
            default_cred = 0.50

    if rumor_text is None:
        rumor_text = preset_text
        default_cred = preset_cred

    st.markdown("")
    c1, c2 = st.columns(2)
    with c1:
        credibility = st.slider(
            "Rumour credibility shown to agents",
            min_value=0.05, max_value=1.0,
            value=default_cred, step=0.05,
            help="0 = 'barely credible' · 1 = 'absolute certainty'",
        )
        bank_failing = st.toggle(
            "Bank is actually failing (ground truth)",
            value=False,
            help=(
                "When ON: the bank genuinely has a reserve problem — agents who stay are "
                "making the wrong call. When OFF: the bank is solvent — withdrawers are "
                "panicking unnecessarily."
            ),
        )

    with c2:
        speed_label = st.radio(
            "Decision speed",
            ["AI Speed (instant)", "Human Speed (90-sec delay)"],
            help=(
                "**AI Speed**: agents decide in seconds. "
                "**Human Speed**: 90-second deliberation pause per decision."
            ),
        )
        fill_standard = st.checkbox(
            "Fill empty slots with standard agents",
            value=True,
            help=(
                "If you have fewer than 12 custom agents, fill the remaining slots "
                "with the pre-built standard population. Recommended — keeps the cascade "
                "dynamics interesting even with a small custom population."
            ),
        )

    return {
        "rumor_text": rumor_text,
        "credibility": credibility,
        "bank_failing": bank_failing,
        "ai_speed": "AI" in speed_label,
        "fill_standard": fill_standard,
        "country_profile": country_profile,
    }


# ---------------------------------------------------------------------------
# Section 4: Population summary + run
# ---------------------------------------------------------------------------


def _section_run(selected_agents: List[Dict[str, Any]], scenario_config: Dict[str, Any]) -> None:
    st.subheader("4 — Review & Run")

    n_custom = len(selected_agents)
    fill_standard = scenario_config.get("fill_standard", True)
    n_standard_fill = max(0, 12 - n_custom) if fill_standard else 0
    n_total = n_custom + n_standard_fill

    cp = scenario_config.get("country_profile")
    country_badge = (
        f'<div style="color:#555">🌍 Country profile: <b>{cp["label"]}</b></div>'
        if cp else ""
    )
    st.markdown(
        f'<div style="background:#F0F4FF;border:1px solid #C8D4E8;border-radius:8px;'
        f'padding:0.8rem 1.2rem;margin-bottom:1rem">'
        f'<div style="font-size:0.75rem;font-weight:700;letter-spacing:0.1em;'
        f'text-transform:uppercase;color:#4E79A7;margin-bottom:0.4rem">POPULATION SUMMARY</div>'
        f'<div style="display:flex;gap:2rem;flex-wrap:wrap">'
        f'<div><b>{n_custom}</b> custom agent{"s" if n_custom != 1 else ""}</div>'
        + (f'<div><b>{n_standard_fill}</b> standard fill-in{"s" if n_standard_fill != 1 else ""}</div>'
           if fill_standard else "")
        + f'<div><b>{n_total}</b> total</div>'
        + country_badge
        + (f'<div style="color:#E15759">⚠ Bank is set as <b>failing</b> — agents who stay will lose</div>'
           if scenario_config.get("bank_failing") else
           '<div style="color:#4A6741">✓ Bank is <b>solvent</b> — withdrawers are panicking unnecessarily</div>')
        + f'</div></div>',
        unsafe_allow_html=True,
    )

    run_col, note_col = st.columns([1, 3])
    with run_col:
        run_clicked = st.button(
            "▶ Run Sandbox",
            type="primary",
            use_container_width=True,
            disabled=(n_total == 0),
        )
    with note_col:
        speed_note = "AI speed" if scenario_config.get("ai_speed") else "human speed (90s)"
        st.caption(
            f"{n_total} agents · {int(scenario_config['credibility'] * 100)}% credibility · {speed_note}"
        )

    if run_clicked:
        _run_sandbox(selected_agents, scenario_config)


def _run_sandbox(
    selected_agents: List[Dict[str, Any]],
    scenario_config: Dict[str, Any],
) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    import copy
    from src.core.scenario import (
        AgentPopulationGroup,
        BankConfig,
        RumorConfig,
        Scenario,
        ScenarioSpeed,
    )
    from src.core.simulation import run_scenario
    from src.decisions.llm_client import LLMClient
    from src.personas.generator import load_agent_from_dict
    from src.personas.instances import make_all_agents

    # ── Build agent list ──────────────────────────────────────────────────
    custom_agent_objs = [
        load_agent_from_dict(d, agent_id=d.get("persona_id", f"custom_{i}"))
        for i, d in enumerate(selected_agents)
    ]

    fill_standard = scenario_config.get("fill_standard", True)
    n_needed = max(0, 12 - len(custom_agent_objs))
    if fill_standard and n_needed > 0:
        standard_pool = make_all_agents()
        random.shuffle(standard_pool)
        filler = standard_pool[:n_needed]
    else:
        filler = []

    agents = custom_agent_objs + filler

    # ── Apply country profile modifiers ───────────────────────────────────
    cp = scenario_config.get("country_profile")
    if cp is not None:
        for agent in agents:
            p = agent.persona
            p.risk_tolerance_score = max(0.0, min(1.0,
                p.risk_tolerance_score + cp["risk_tolerance_delta"]))
            p.financial_sophistication_score = max(0.0, min(1.0,
                p.financial_sophistication_score + cp["sophistication_delta"]))
            p.peer_action_reconsideration_threshold = max(0.10, min(0.60,
                p.peer_action_reconsideration_threshold + cp["peer_threshold_delta"]))

    # ── Build scenario ────────────────────────────────────────────────────
    bank_a_reserve = 0.06 if scenario_config["bank_failing"] else 0.40

    scenario = Scenario(
        scenario_id="custom_sandbox",
        name="Custom Sandbox",
        description=(
            f"User-configured sandbox run. "
            f"Bank A is {'genuinely failing' if scenario_config['bank_failing'] else 'solvent'}. "
            f"Rumour credibility: {scenario_config['credibility']:.0%}."
        ),
        banks=[
            BankConfig(
                bank_id="bank_a",
                name="Redwood Regional Bank",
                initial_reserve_ratio=bank_a_reserve,
                early_withdrawal_fee_rate=0.03,
                withdrawal_processing_capacity=450_000.0,
                distress_threshold=0.20,
                suspension_threshold=0.05,
            ),
            BankConfig(
                bank_id="bank_b",
                name="Harbor National Bank",
                initial_reserve_ratio=0.30,
                early_withdrawal_fee_rate=0.02,
                withdrawal_processing_capacity=5_000_000.0,
            ),
        ],
        rumors=[
            RumorConfig(
                content=scenario_config["rumor_text"],
                source="social_media",
                credibility=scenario_config["credibility"],
                target_bank_id="bank_a",
                publish_at_time=2.0,
                is_true=scenario_config["bank_failing"],
                propagation_latency_seconds=3.0,
            ),
        ],
        population=[
            AgentPopulationGroup("cautious_retiree", 3, "bank_a", (25_000, 52_000), "bank_b", (6_000, 19_000)),
            AgentPopulationGroup("aggressive_trader", 3, "bank_a", (11_000, 38_000), "bank_b", (3_000, 9_000)),
            AgentPopulationGroup("gig_worker", 3, "bank_a", (1_800, 3_200), "bank_b", (350, 600)),
            AgentPopulationGroup("institutional_treasurer", 3, "bank_a", (310_000, 590_000), "bank_b", (85_000, 260_000)),
        ],
        speed=ScenarioSpeed.AI_SPEED if scenario_config["ai_speed"] else ScenarioSpeed.HUMAN_SPEED,
        seed=random.randint(0, 9999),
        social_signal_visibility=1.0 if scenario_config["ai_speed"] else 0.55,
    )

    # ── Execute ───────────────────────────────────────────────────────────
    runs_dir = Path(__file__).parent.parent.parent / "runs"
    client = LLMClient()

    status = st.empty()
    progress = st.progress(0, text="Starting…")
    status.info(
        f"Running sandbox — {len(agents)} agents, real LLM calls. "
        "Takes 30–90 seconds at AI speed."
    )
    progress.progress(15, text="Agents observing rumour…")

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

        if st.button("→ Go to Live View", type="primary"):
            st.session_state._pending_nav = "Live View"
            st.rerun()

    except Exception as exc:
        progress.empty()
        status.error(f"Simulation failed: {exc}")
        raise


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def render_sandbox() -> None:
    st.header("Sandbox — Build Your Own Scenario")
    st.markdown(
        "Describe any agent in plain English. The system turns your description into a "
        "fully-specified simulation agent — complete persona, decision style, voice, and "
        "cost function. Assemble your own population, configure the scenario, and run."
    )

    _CUSTOM_PERSONAS_DIR.mkdir(parents=True, exist_ok=True)

    for key, default in [
        ("sandbox_preview_data", None),
        ("sandbox_example_desc", ""),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    _section_agent_builder()
    st.divider()

    selected = _section_my_agents()
    st.divider()

    scenario_config = _section_scenario_setup()
    st.divider()

    if scenario_config:
        _section_run(selected, scenario_config)
