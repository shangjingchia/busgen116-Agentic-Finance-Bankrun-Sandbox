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
import re
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

_ARCHETYPE_ORDER = [
    "cautious_retiree",
    "aggressive_trader",
    "gig_worker",
    "institutional_treasurer",
]

# Default Bank A deposit range per archetype (matches the standard population groups).
_DEFAULT_DEPOSIT_RANGES = {
    "cautious_retiree":        (25_000, 52_000),
    "aggressive_trader":       (11_000, 38_000),
    "gig_worker":              (1_800, 3_200),
    "institutional_treasurer": (310_000, 590_000),
}

_DEFAULT_DENIAL = (
    "Redwood Regional Bank has issued an official statement confirming that all "
    "deposits remain fully accessible and that the circulating rumours are false. "
    "The bank reports its liquidity and capital positions are well within normal ranges."
)

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


def _slugify(text: str) -> str:
    """Filesystem/id-safe slug from a free-text scenario name (empty -> '')."""
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:40]


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

    scenario_name = st.text_input(
        "Name this scenario (optional)",
        value="",
        placeholder="e.g. Healthy bank · charged rumour · all retirees",
        key="sb_scenario_name",
        help=(
            "Saved with the run so you can find and reload it later from "
            "Presets → Load saved run. Each run is kept separately."
        ),
    )

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

    # ════════════════════════════════════════════════════════════════════
    #  THE RUMOUR
    # ════════════════════════════════════════════════════════════════════
    st.markdown("##### 📰 The rumour")
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

    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        credibility = st.slider(
            "Credibility shown to agents",
            min_value=0.05, max_value=1.0,
            value=default_cred, step=0.05,
            key="sb_cred",
            help="0 = 'barely credible' · 1 = 'absolute certainty'",
        )
    with rc2:
        rumor_time = st.slider(
            "When the rumour hits (sec)",
            min_value=0.0, max_value=30.0, value=2.0, step=1.0,
            key="sb_rumor_time",
            help="Simulation time at which the rumour is published into the feed.",
        )
    with rc3:
        speed_label = st.radio(
            "Decision speed",
            ["AI Speed (instant)", "Human Speed (90-sec delay)"],
            key="sb_speed",
            help=(
                "**AI Speed**: agents decide in seconds. "
                "**Human Speed**: 90-second deliberation pause per decision."
            ),
        )
    ai_speed = "AI" in speed_label

    # ════════════════════════════════════════════════════════════════════
    #  THE BANKS
    # ════════════════════════════════════════════════════════════════════
    st.markdown("##### 🏦 The banks")
    bcol_a, bcol_b = st.columns(2)
    with bcol_a:
        st.markdown("**Bank A — Redwood Regional** · under rumour")
        bank_a_reserve = st.slider(
            "Reserve ratio (liquidity)", 0.02, 0.60, 0.40, 0.01, key="sb_res_a",
            help=(
                "Cash on hand vs deposits. Low = the bank can't meet a wave of withdrawals "
                "and suspends sooner. This is *liquidity* — separate from solvency below."
            ),
        )
        bank_a_capacity = st.slider(
            "Payout capacity ($)", 100_000, 5_000_000, 450_000, 50_000, key="sb_cap_a",
            help="How much the bank can pay out before it freezes. Raise it and more depositors get cash.",
        )
        bank_a_fee = st.slider(
            "Early-withdrawal fee", 0.0, 0.10, 0.03, 0.005, key="sb_fee_a",
            help="Penalty for pulling money early — gives cautious agents a reason to hold.",
        )
        bank_failing = st.toggle(
            "Bank A is actually insolvent (ground truth)", value=False, key="sb_insolvent",
            help=(
                "ON: the bank is genuinely broke — agents who hold through it lose principal, "
                "and the rumour is TRUE. OFF: solvent — withdrawers are panicking unnecessarily. "
                "Independent of the reserve slider (which is liquidity, not solvency)."
            ),
        )
    with bcol_b:
        st.markdown("**Bank B — Harbor National** · safe haven")
        bank_b_reserve = st.slider(
            "Reserve ratio (liquidity)", 0.02, 0.60, 0.30, 0.01, key="sb_res_b",
            help="Where agents flee. Drop its reserves to model 'nowhere is safe' / contagion.",
        )
        st.caption(
            "Bank B carries no rumour. Lower its reserves to make the safe haven shaky too — "
            "useful for contagion scenarios."
        )

    # ════════════════════════════════════════════════════════════════════
    #  THE POPULATION MIX
    # ════════════════════════════════════════════════════════════════════
    st.markdown("##### 👥 The population mix")
    st.caption(
        "How many standard agents of each archetype to include. Any custom agents you saved "
        "in Section 2 are added on top of this."
    )
    pop_counts: Dict[str, int] = {}
    pop_deposit_ranges: Dict[str, Any] = {}
    for arch in _ARCHETYPE_ORDER:
        label = _ARCHETYPE_LABELS[arch]
        pcol1, pcol2 = st.columns([1, 2.4])
        with pcol1:
            pop_counts[arch] = int(st.number_input(
                label, min_value=0, max_value=12, value=3, step=1, key=f"sb_count_{arch}",
            ))
        with pcol2:
            lo_def, hi_def = _DEFAULT_DEPOSIT_RANGES[arch]
            pop_deposit_ranges[arch] = st.slider(
                f"{label} — Bank A deposit range ($)",
                min_value=int(lo_def * 0.2), max_value=int(hi_def * 2.0),
                value=(int(lo_def), int(hi_def)),
                step=max(100, int(lo_def * 0.05)),
                key=f"sb_dep_{arch}",
            )
    total_std = sum(pop_counts.values())
    st.caption(f"**{total_std}** standard agents configured (custom agents add to this).")

    # ════════════════════════════════════════════════════════════════════
    #  INFORMATION ENVIRONMENT
    # ════════════════════════════════════════════════════════════════════
    st.markdown("##### 🌐 Information environment")
    icol1, icol2 = st.columns(2)
    with icol1:
        default_vis = 1.0 if ai_speed else 0.55
        social_visibility = st.slider(
            "Peer activity visible to agents", 0.0, 1.0, default_vis, 0.05,
            key=f"sb_vis_{ai_speed}",
            help=(
                "Fraction of peer withdrawals each agent sees on the social feed. "
                "High = strong herding; 0 = agents are blind to each other."
            ),
        )
    with icol2:
        enable_denial = st.checkbox(
            "Add a reassuring counter-signal (official denial)", value=False, key="sb_denial",
            help="Inject an opposing signal saying the bank is fine — to test whether agents can be talked back.",
        )

    denial_text = _DEFAULT_DENIAL
    denial_time, denial_strength, denial_cred = 5.0, 0.7, 0.6
    if enable_denial:
        denial_text = st.text_area(
            "Counter-signal text", value=_DEFAULT_DENIAL, height=80, key="sb_denial_text",
        )
        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            denial_time = st.slider("When the denial lands (sec)", 0.0, 30.0, 5.0, 1.0, key="sb_denial_time")
        with dcol2:
            denial_strength = st.slider(
                "How reassuring", 0.1, 1.0, 0.7, 0.1, key="sb_denial_str",
                help="Maps to a negative alarm level. 1.0 = maximally calming.",
            )
        with dcol3:
            denial_cred = st.slider("Denial credibility", 0.05, 1.0, 0.6, 0.05, key="sb_denial_cred")
        st.caption(
            "The denial travels on the same channel as the rumour, so it reaches whoever heard the rumour."
        )

    # ── Central Bank intervention ─────────────────────────────────────────
    st.markdown("##### 🏛 Central Bank intervention")
    with st.expander("Configure a regulator (optional)", expanded=False):
        enable_cb = st.checkbox("Enable Central Bank", value=False, key="sandbox_enable_cb")
        cb_policy_type = "llm"
        cb_threshold = 0.25
        if enable_cb:
            cb_col1, cb_col2 = st.columns(2)
            with cb_col1:
                cb_type_label = st.radio(
                    "Policy type",
                    ["🤖 AI-powered (LLM)", "📋 Rule-based (fixed threshold)"],
                    key="sandbox_cb_type",
                    help=(
                        "**AI-powered**: the CB makes a real LLM call and chooses the "
                        "intervention in context. "
                        "**Rule-based**: fires a pre-configured guarantee announcement "
                        "when the threshold is crossed, without reasoning."
                    ),
                )
                cb_policy_type = "llm" if "AI" in cb_type_label else "rule_based"
            with cb_col2:
                cb_threshold = st.slider(
                    "Trigger threshold",
                    min_value=0.10, max_value=0.60,
                    value=0.25, step=0.05,
                    key="sandbox_cb_threshold",
                    help="Fraction of agents who must fully withdraw before the CB acts.",
                )
                st.caption(f"CB fires at {int(cb_threshold * 100)}% withdrawn")

    return {
        "scenario_name": scenario_name,
        "rumor_text": rumor_text,
        "credibility": credibility,
        "rumor_time": rumor_time,
        "bank_failing": bank_failing,
        "bank_a_reserve": bank_a_reserve,
        "bank_a_capacity": float(bank_a_capacity),
        "bank_a_fee": bank_a_fee,
        "bank_b_reserve": bank_b_reserve,
        "ai_speed": ai_speed,
        "social_visibility": social_visibility,
        "pop_counts": pop_counts,
        "pop_deposit_ranges": pop_deposit_ranges,
        "country_profile": country_profile,
        "enable_cb": enable_cb,
        "cb_policy_type": cb_policy_type,
        "cb_threshold": cb_threshold,
        "enable_denial": enable_denial,
        "denial_text": denial_text,
        "denial_time": denial_time,
        "denial_strength": denial_strength,
        "denial_cred": denial_cred,
    }


# ---------------------------------------------------------------------------
# Section 4: Population summary + run
# ---------------------------------------------------------------------------


def _section_run(selected_agents: List[Dict[str, Any]], scenario_config: Dict[str, Any]) -> None:
    st.subheader("4 — Review & Run")

    n_custom = len(selected_agents)
    n_standard = sum(scenario_config.get("pop_counts", {}).values())
    n_total = n_custom + n_standard

    cp = scenario_config.get("country_profile")
    country_badge = (
        f'<div style="color:#555">🌍 Country profile: <b>{cp["label"]}</b></div>'
        if cp else ""
    )
    denial_badge = (
        '<div style="color:#4A6741">🟢 Counter-signal (denial) active</div>'
        if scenario_config.get("enable_denial") else ""
    )
    st.markdown(
        f'<div style="background:#F0F4FF;border:1px solid #C8D4E8;border-radius:8px;'
        f'padding:0.8rem 1.2rem;margin-bottom:1rem">'
        f'<div style="font-size:0.75rem;font-weight:700;letter-spacing:0.1em;'
        f'text-transform:uppercase;color:#4E79A7;margin-bottom:0.4rem">POPULATION SUMMARY</div>'
        f'<div style="display:flex;gap:2rem;flex-wrap:wrap">'
        f'<div><b>{n_custom}</b> custom agent{"s" if n_custom != 1 else ""}</div>'
        f'<div><b>{n_standard}</b> standard agent{"s" if n_standard != 1 else ""}</div>'
        f'<div><b>{n_total}</b> total</div>'
        + country_badge
        + denial_badge
        + (f'<div style="color:#E15759">⚠ Bank A set <b>insolvent</b> — agents who hold lose principal</div>'
           if scenario_config.get("bank_failing") else
           '<div style="color:#4A6741">✓ Bank A <b>solvent</b> — withdrawers are panicking unnecessarily</div>')
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
        cb_note = ""
        if scenario_config.get("enable_cb"):
            cb_note = " · 🏛 " + ("AI CB" if scenario_config.get("cb_policy_type") == "llm" else "Rule CB")
        st.caption(
            f"{n_total} agents · {int(scenario_config['credibility'] * 100)}% credibility · {speed_note}{cb_note}"
        )

    if run_clicked:
        _run_sandbox(selected_agents, scenario_config)


def _run_sandbox(
    selected_agents: List[Dict[str, Any]],
    scenario_config: Dict[str, Any],
) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    from src.core.scenario import (
        AgentPopulationGroup,
        BankConfig,
        CentralBankConfig,
        RumorConfig,
        Scenario,
        ScenarioSpeed,
    )
    from src.core.simulation import run_scenario
    from src.decisions.llm_client import LLMClient
    from src.information.environment import SOURCE_SOCIAL_MEDIA, InformationSignal
    from src.personas.generator import load_agent_from_dict
    from src.personas.instances import make_agents_for_archetype

    ai_speed = scenario_config.get("ai_speed", True)
    insolvent = scenario_config.get("bank_failing", False)

    # Unique id + friendly name per run so each sandbox run is saved and
    # reloadable on its own (rather than every run sharing "custom_sandbox").
    raw_name = (scenario_config.get("scenario_name") or "").strip()
    display_name = raw_name or "Custom Sandbox"
    slug = _slugify(raw_name) or "sandbox"
    scenario_uid = f"custom_{slug}_{random.randint(1000, 9999)}"

    # ── Build agent list: custom agents + the configured standard mix ──────
    custom_agent_objs = [
        load_agent_from_dict(d, agent_id=d.get("persona_id", f"custom_{i}"))
        for i, d in enumerate(selected_agents)
    ]

    mix_agents = []
    pop_counts = scenario_config.get("pop_counts", {})
    pop_ranges = scenario_config.get("pop_deposit_ranges", {})
    for arch, cnt in pop_counts.items():
        if cnt <= 0:
            continue
        built = make_agents_for_archetype(arch, int(cnt))
        rng = pop_ranges.get(arch)
        default_rng = _DEFAULT_DEPOSIT_RANGES.get(arch)
        # Only override deposits if the user moved the range off its default.
        if rng and default_rng and tuple(rng) != tuple(default_rng):
            lo, hi = float(rng[0]), float(rng[1])
            for a in built:
                a.portfolio["bank_a:deposit"] = round(random.uniform(lo, hi), 2)
        mix_agents.extend(built)

    agents = custom_agent_objs + mix_agents

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

    # ── Build the population metadata groups (records the configured mix) ──
    _SECONDARY_RANGES = {
        "cautious_retiree": (6_000, 19_000),
        "aggressive_trader": (3_000, 9_000),
        "gig_worker": (350, 600),
        "institutional_treasurer": (85_000, 260_000),
    }
    pop_groups = []
    for arch, cnt in pop_counts.items():
        if cnt <= 0:
            continue
        rng = pop_ranges.get(arch) or _DEFAULT_DEPOSIT_RANGES[arch]
        pop_groups.append(AgentPopulationGroup(
            arch, int(cnt), "bank_a", (float(rng[0]), float(rng[1])),
            "bank_b", _SECONDARY_RANGES.get(arch),
        ))

    # ── Reassuring counter-signal (optional) ───────────────────────────────
    signals = []
    if scenario_config.get("enable_denial"):
        signals.append(InformationSignal(
            content=scenario_config.get("denial_text", _DEFAULT_DENIAL),
            source_type=SOURCE_SOCIAL_MEDIA,   # same channel as the rumour → mirrors its reach
            alarm_level=-float(scenario_config.get("denial_strength", 0.7)),
            base_credibility=float(scenario_config.get("denial_cred", 0.6)),
            publish_at=float(scenario_config.get("denial_time", 5.0)),
            target_bank_id="bank_a",
            propagation_latency_seconds=3.0,
            is_true=not insolvent,
        ))

    # ── Build scenario ────────────────────────────────────────────────────
    scenario = Scenario(
        scenario_id=scenario_uid,
        name=display_name,
        description=(
            f"User-configured sandbox run. Bank A reserve "
            f"{scenario_config.get('bank_a_reserve', 0.40):.0%}, "
            f"{'genuinely insolvent' if insolvent else 'solvent'}. "
            f"Rumour credibility: {scenario_config['credibility']:.0%}"
            + (" · counter-signal active" if scenario_config.get("enable_denial") else "")
            + "."
        ),
        banks=[
            BankConfig(
                bank_id="bank_a",
                name="Redwood Regional Bank",
                initial_reserve_ratio=float(scenario_config.get("bank_a_reserve", 0.40)),
                early_withdrawal_fee_rate=float(scenario_config.get("bank_a_fee", 0.03)),
                withdrawal_processing_capacity=float(scenario_config.get("bank_a_capacity", 450_000.0)),
                distress_threshold=0.20,
                suspension_threshold=0.05,
                asset_recovery_ratio=0.5 if insolvent else 1.0,
            ),
            BankConfig(
                bank_id="bank_b",
                name="Harbor National Bank",
                initial_reserve_ratio=float(scenario_config.get("bank_b_reserve", 0.30)),
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
                publish_at_time=float(scenario_config.get("rumor_time", 2.0)),
                is_true=insolvent,
                propagation_latency_seconds=3.0,
            ),
        ],
        signals=signals,
        population=pop_groups,
        speed=ScenarioSpeed.AI_SPEED if ai_speed else ScenarioSpeed.HUMAN_SPEED,
        seed=random.randint(0, 9999),
        social_signal_visibility=float(
            scenario_config.get("social_visibility", 1.0 if ai_speed else 0.55)
        ),
        central_bank=(
            CentralBankConfig(
                policy_type=scenario_config.get("cb_policy_type", "llm"),
                trigger_threshold=scenario_config.get("cb_threshold", 0.25),
                model="anthropic/claude-sonnet-4.5",
            )
            if scenario_config.get("enable_cb")
            else None
        ),
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

        if st.button("→ Inspect agent reasoning", type="primary"):
            st.session_state._pending_nav = "Inspect"
            st.rerun()

    except Exception as exc:
        progress.empty()
        status.error(f"Simulation failed: {exc}")
        st.stop()


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
