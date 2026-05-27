"""
Preset scenario factory functions used by the dashboard configure page.

Five presets cover the 2×2 credibility/truth matrix plus a baseline:
  rumor_moderate_false  — moderate credibility, bank fine (unnecessary panic)
  rumor_high_true       — high credibility, bank insolvent (real crisis)
  rumor_high_false      — high credibility, bank fine (maximum false alarm)
  rumor_weak_true       — low credibility, bank insolvent (slow burn)
  rumor_weak_false      — low credibility, bank fine (noise test)

Each preset uses a structured InformationSignal stream rather than a single
uniform rumor. Different archetypes see different sources with different
credibilities — gig workers see social-media alarms while institutional
treasurers also receive official denials and FDIC statements.
"""

from __future__ import annotations

from typing import List, Tuple

from src.core.scenario import (
    AgentPopulationGroup,
    BankConfig,
    CentralBankConfig,
    RumorConfig,
    Scenario,
    ScenarioSpeed,
)
from src.information.environment import (
    SOURCE_FINANCIAL_NEWS,
    SOURCE_OFFICIAL_BANK,
    SOURCE_PEER_NETWORK,
    SOURCE_REGULATOR,
    SOURCE_SOCIAL_MEDIA,
    InformationSignal,
)

# ---------------------------------------------------------------------------
# Shared bank and population configs
# ---------------------------------------------------------------------------

_BANKS: List[BankConfig] = [
    BankConfig(
        bank_id="bank_a",
        name="Redwood Regional Bank",
        initial_reserve_ratio=0.40,          # 40% — Basel III LCR-aligned
        early_withdrawal_fee_rate=0.03,
        withdrawal_processing_capacity=5_000_000.0,   # restored from Codex-broken 450K
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
]

# Population: 3 cautious_retirees, 2 aggressive_traders, 3 gig_workers,
# 3 institutional_treasurers, 1 contrarian = 12 total
_POPULATION: List[AgentPopulationGroup] = [
    AgentPopulationGroup("cautious_retiree", 3, "bank_a", (25_000, 52_000), "bank_b", (6_000, 19_000)),
    AgentPopulationGroup("aggressive_trader", 2, "bank_a", (11_000, 38_000), "bank_b", (3_000, 9_000)),
    AgentPopulationGroup("gig_worker", 3, "bank_a", (1_800, 3_200), "bank_b", (350, 600)),
    AgentPopulationGroup("institutional_treasurer", 3, "bank_a", (310_000, 590_000), "bank_b", (85_000, 260_000)),
    AgentPopulationGroup("contrarian", 1, "bank_a", (80_000, 120_000), "bank_b", (100_000, 160_000)),
]

# ---------------------------------------------------------------------------
# Signal stream builders
# ---------------------------------------------------------------------------

def _signals_high_false(is_true: bool = False) -> List[InformationSignal]:
    """High-credibility alarm signal stream.

    Gig workers and aggressive traders see social-media alarm early.
    Institutional treasurers see Bloomberg terminal alert.
    Everyone sees the official bank response (alarm_level varies by is_true).
    Cautious retirees and institutionals see the FDIC notice.
    """
    signals = [
        # T=0: Social media alarm — everyone sees it; professionals discount it
        InformationSignal(
            content=(
                "Multiple posts across financial social media claim Redwood Regional Bank "
                "cannot meet withdrawal requests. Anonymous accounts cite 'insider' sources. "
                "The posts are spreading rapidly but have not been verified by any news outlet."
            ),
            source_type=SOURCE_SOCIAL_MEDIA,
            alarm_level=0.65,
            base_credibility=0.40,
            archetype_credibility_multipliers={
                "gig_worker": 1.4,
                "cautious_retiree": 0.7,
                "aggressive_trader": 0.9,
                "institutional_treasurer": 0.3,
                "contrarian": 0.2,
            },
            visible_to_archetypes=[],   # broadcast
            publish_at=0.0,
            target_bank_id="bank_a",
            propagation_latency_seconds=3.0,
            is_true=is_true,
        ),
        # T=2: Bloomberg terminal — high alarm, professionals only
        InformationSignal(
            content=(
                "A market-terminal alert cites two bank analysts and screenshots of a "
                "purported supervisory letter saying Redwood Regional Bank may miss its "
                "liquidity coverage requirement. The bank has delayed its investor call "
                "by two hours, and trading in its parent company's stock is unusually volatile."
            ),
            source_type=SOURCE_FINANCIAL_NEWS,
            alarm_level=0.75,
            base_credibility=0.70,
            archetype_credibility_multipliers={
                "institutional_treasurer": 1.2,
                "aggressive_trader": 1.1,
                "contrarian": 0.8,
            },
            visible_to_archetypes=["institutional_treasurer", "aggressive_trader", "contrarian"],
            publish_at=2.0,
            target_bank_id="bank_a",
            propagation_latency_seconds=2.0,
            is_true=is_true,
        ),
        # T=5: Peer network signal for gig workers — "my friend just moved their money"
        InformationSignal(
            content=(
                "Multiple people in local community group chats are reporting that their "
                "friends and neighbors have started pulling money from Redwood Regional. "
                "One message reads: 'My coworker said she tried to withdraw yesterday and "
                "it took hours — something is wrong.'"
            ),
            source_type=SOURCE_PEER_NETWORK,
            alarm_level=0.55,
            base_credibility=0.35,
            archetype_credibility_multipliers={
                "gig_worker": 1.5,
                "cautious_retiree": 0.8,
            },
            visible_to_archetypes=["gig_worker", "cautious_retiree"],
            publish_at=5.0,
            target_bank_id="bank_a",
            propagation_latency_seconds=4.0,
            is_true=is_true,
        ),
    ]

    if not is_true:
        # Bank is actually fine — issue a denial and FDIC reassurance
        signals += [
            # T=8: Official bank denial — reassuring for cautious + institutional
            InformationSignal(
                content=(
                    "Redwood Regional Bank official statement: 'We are aware of rumors "
                    "circulating on social media. We wish to assure our depositors that "
                    "our liquidity position remains strong. We meet all capital requirements "
                    "and all deposits remain fully accessible. These reports are false.'"
                ),
                source_type=SOURCE_OFFICIAL_BANK,
                alarm_level=-0.35,
                base_credibility=0.55,
                archetype_credibility_multipliers={
                    "cautious_retiree": 1.2,
                    "institutional_treasurer": 1.4,
                    "contrarian": 1.6,
                    "aggressive_trader": 0.4,
                    "gig_worker": 0.6,
                },
                visible_to_archetypes=[],
                publish_at=8.0,
                target_bank_id="bank_a",
                propagation_latency_seconds=3.0,
                is_true=False,
            ),
            # T=15: FDIC monitoring notice — reassuring for cautious + institutional
            InformationSignal(
                content=(
                    "FDIC statement: 'We are aware of reports regarding Redwood Regional Bank "
                    "and are actively monitoring the situation. All deposits at FDIC-insured "
                    "institutions are insured up to $250,000 per depositor. We have no current "
                    "plans for regulatory action.'"
                ),
                source_type=SOURCE_REGULATOR,
                alarm_level=0.05,   # slightly ominous that they're watching, but mostly reassuring
                base_credibility=0.85,
                archetype_credibility_multipliers={
                    "cautious_retiree": 1.5,
                    "institutional_treasurer": 1.3,
                    "contrarian": 1.4,
                },
                visible_to_archetypes=["cautious_retiree", "institutional_treasurer", "contrarian"],
                publish_at=15.0,
                target_bank_id="bank_a",
                propagation_latency_seconds=2.0,
                is_true=False,
            ),
        ]
    else:
        # Bank is actually insolvent — no reassuring denial, FDIC notice is more ominous
        signals += [
            # T=8: FDIC opens investigation — alarming
            InformationSignal(
                content=(
                    "FDIC statement: 'We are aware of reports regarding Redwood Regional Bank "
                    "and are conducting an expedited review of its financial position. Deposits "
                    "at FDIC-insured institutions remain protected up to $250,000. We will "
                    "provide updates as the situation develops.'"
                ),
                source_type=SOURCE_REGULATOR,
                alarm_level=0.45,   # expedited review is actually alarming
                base_credibility=0.90,
                archetype_credibility_multipliers={
                    "cautious_retiree": 1.4,
                    "institutional_treasurer": 1.5,
                    "contrarian": 1.3,
                },
                visible_to_archetypes=["cautious_retiree", "institutional_treasurer", "contrarian"],
                publish_at=8.0,
                target_bank_id="bank_a",
                propagation_latency_seconds=2.0,
                is_true=True,
            ),
        ]

    return signals


def _signals_moderate_false(is_true: bool = False) -> List[InformationSignal]:
    """Moderate-credibility signal stream from regional financial outlet."""
    signals = [
        # T=0: Regional financial news — moderate alarm
        InformationSignal(
            content=(
                "A regional financial outlet reports that Redwood Regional Bank is facing "
                "unusual deposit outflows after a weak quarterly call report. Several "
                "corporate depositors are rumored to be moving funds, but the bank says "
                "liquidity remains adequate."
            ),
            source_type=SOURCE_FINANCIAL_NEWS,
            alarm_level=0.40,
            base_credibility=0.55,
            archetype_credibility_multipliers={
                "institutional_treasurer": 1.1,
                "cautious_retiree": 0.9,
                "aggressive_trader": 1.0,
                "gig_worker": 0.5,
                "contrarian": 0.7,
            },
            visible_to_archetypes=[],
            publish_at=0.0,
            target_bank_id="bank_a",
            propagation_latency_seconds=5.0,
            is_true=is_true,
        ),
        # T=3: Social media pickup
        InformationSignal(
            content=(
                "The regional financial news story about Redwood Regional Bank has been "
                "picked up on social media. Comments range from 'this is nothing' to "
                "'get your money out now.' The volume of social discussion is growing."
            ),
            source_type=SOURCE_SOCIAL_MEDIA,
            alarm_level=0.30,
            base_credibility=0.30,
            archetype_credibility_multipliers={
                "gig_worker": 1.3,
                "cautious_retiree": 0.7,
                "institutional_treasurer": 0.2,
            },
            visible_to_archetypes=[],
            publish_at=3.0,
            target_bank_id="bank_a",
            propagation_latency_seconds=4.0,
            is_true=is_true,
        ),
    ]

    if not is_true:
        signals.append(
            # T=10: Bank issues clarifying statement
            InformationSignal(
                content=(
                    "Redwood Regional Bank: 'Reports of unusual outflows are exaggerated. "
                    "Our liquidity coverage ratio remains well above regulatory minimums. "
                    "We are in regular communication with our regulators and there are no "
                    "outstanding supervisory concerns.'"
                ),
                source_type=SOURCE_OFFICIAL_BANK,
                alarm_level=-0.25,
                base_credibility=0.50,
                archetype_credibility_multipliers={
                    "cautious_retiree": 1.2,
                    "institutional_treasurer": 1.3,
                    "contrarian": 1.5,
                    "aggressive_trader": 0.5,
                },
                visible_to_archetypes=[],
                publish_at=10.0,
                target_bank_id="bank_a",
                propagation_latency_seconds=3.0,
                is_true=False,
            )
        )

    return signals


def _signals_low(is_true: bool = False) -> List[InformationSignal]:
    """Low-credibility anonymous social media rumor — no official follow-up."""
    return [
        InformationSignal(
            content=(
                "An anonymous post on a financial message board claims Redwood Regional Bank "
                "is in serious trouble and that insiders are moving money. No official sources "
                "have confirmed the claim. The identity of the poster is unknown and the post "
                "has not been picked up by any major outlet."
            ),
            source_type=SOURCE_SOCIAL_MEDIA,
            alarm_level=0.30,
            base_credibility=0.20,
            archetype_credibility_multipliers={
                "gig_worker": 1.4,
                "cautious_retiree": 0.8,
                "aggressive_trader": 0.7,
                "institutional_treasurer": 0.2,
                "contrarian": 0.1,
            },
            visible_to_archetypes=[],
            publish_at=0.0,
            target_bank_id="bank_a",
            propagation_latency_seconds=10.0,
            is_true=is_true,
        )
    ]


# ---------------------------------------------------------------------------
# Preset list: (id, display_label, Scenario)
# ---------------------------------------------------------------------------

PRESETS: List[Tuple[str, str, Scenario]] = [
    (
        "rumor_moderate_false",
        "Moderate Rumor — Bank Solvent (unnecessary panic baseline)",
        Scenario(
            scenario_id="rumor_moderate_false",
            name="Moderate Rumor — Bank Solvent",
            description=(
                "A moderate-credibility rumor about Bank A enters at t=0. "
                "The bank is actually solvent. Tests unnecessary panic dynamics — "
                "do AI agents over-react to ambiguous news?"
            ),
            signals=_signals_moderate_false(is_true=False),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
        ),
    ),
    (
        "rumor_high_true",
        "High-Credibility Rumor — Bank Insolvent (real crisis)",
        Scenario(
            scenario_id="rumor_high_true",
            name="High-Credibility Rumor — Bank Insolvent",
            description=(
                "A high-credibility alert about Redwood Regional Bank from official sources. "
                "The bank really is insolvent. Tests cascade speed when the "
                "signal is both credible and true — the worst case."
            ),
            signals=_signals_high_false(is_true=True),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
        ),
    ),
    (
        "rumor_high_false",
        "High-Credibility Rumor — Bank Solvent (maximum false alarm)",
        Scenario(
            scenario_id="rumor_high_false",
            name="High-Credibility Rumor — Bank Solvent",
            description=(
                "A high-credibility alert from market terminals and purported leaked documents, "
                "but the bank is actually solvent. Tests the maximum false-alarm cascade: "
                "how badly do AI agents run on a false but credible signal?"
            ),
            signals=_signals_high_false(is_true=False),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
        ),
    ),
    (
        "rumor_weak_true",
        "Weak Rumor — Bank Insolvent (slow burn)",
        Scenario(
            scenario_id="rumor_weak_true",
            name="Weak Rumor — Bank Insolvent",
            description=(
                "A low-credibility anonymous rumor, but the bank really is insolvent. "
                "Tests whether AI agents eventually discover the truth through social "
                "signals, or whether the weak signal causes them to ignore a real warning."
            ),
            signals=_signals_low(is_true=True),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
        ),
    ),
    (
        "rumor_weak_false",
        "Weak Rumor — Bank Solvent (noise test)",
        Scenario(
            scenario_id="rumor_weak_false",
            name="Weak Rumor — Bank Solvent",
            description=(
                "A low-credibility anonymous rumor and the bank is fine. "
                "The ideal outcome is that agents correctly dismiss the noise. "
                "Tests agent discrimination between signal and noise."
            ),
            signals=_signals_low(is_true=False),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
        ),
    ),
]

# ---------------------------------------------------------------------------
# Central Bank configs (shared across CB preset pairs)
# ---------------------------------------------------------------------------

_CB_LLM = CentralBankConfig(
    policy_type="llm",
    trigger_threshold=0.25,
    model="anthropic/claude-sonnet-4.5",
)

_CB_RULE = CentralBankConfig(
    policy_type="rule_based",
    trigger_threshold=0.25,
    rule_action="announce_guarantee",
    rule_liquidity_fraction=0.5,
)

# ---------------------------------------------------------------------------
# CB preset list: two scenarios × two CB types (vs. baseline rumor_high_false)
# ---------------------------------------------------------------------------

CB_PRESETS: List[Tuple[str, str, Scenario]] = [
    # ── True alarm: bank actually insolvent ──────────────────────────────────
    (
        "rumor_high_true_llm_cb",
        "High Rumor — Bank Insolvent + AI Central Bank",
        Scenario(
            scenario_id="rumor_high_true_llm_cb",
            name="High-Credibility Rumor — Bank Insolvent + AI Central Bank",
            description=(
                "A high-credibility rumor and the bank really is insolvent. "
                "An AI-powered CB monitors in real time — does it correctly choose "
                "to intervene when the threat is genuine?"
            ),
            signals=_signals_high_false(is_true=True),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
            central_bank=_CB_LLM,
        ),
    ),
    (
        "rumor_high_true_rule_cb",
        "High Rumor — Bank Insolvent + Rule-Based Central Bank",
        Scenario(
            scenario_id="rumor_high_true_rule_cb",
            name="High-Credibility Rumor — Bank Insolvent + Rule-Based Central Bank",
            description=(
                "Same genuine crisis — bank insolvent — but CB uses a fixed rule. "
                "It fires correctly here (bank is actually failing), but for the "
                "wrong reason: it can't distinguish this from a false alarm."
            ),
            signals=_signals_high_false(is_true=True),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
            central_bank=_CB_RULE,
        ),
    ),
    # ── False alarm: bank actually solvent ───────────────────────────────────
    (
        "rumor_high_false_llm_cb",
        "High Rumor — Bank Solvent + AI Central Bank",
        Scenario(
            scenario_id="rumor_high_false_llm_cb",
            name="High-Credibility Rumor — Bank Solvent + AI Central Bank",
            description=(
                "A high-credibility false rumor — the bank is actually solvent. "
                "An AI-powered Central Bank agent monitors in real time and chooses "
                "whether to intervene via guarantee or liquidity injection once "
                "25% of agents have withdrawn. Shows whether LLM judgment stops the cascade."
            ),
            signals=_signals_high_false(is_true=False),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
            central_bank=_CB_LLM,
        ),
    ),
    (
        "rumor_high_false_rule_cb",
        "High Rumor — Bank Solvent + Rule-Based Central Bank",
        Scenario(
            scenario_id="rumor_high_false_rule_cb",
            name="High-Credibility Rumor — Bank Solvent + Rule-Based Central Bank",
            description=(
                "Same high-credibility false rumor, but the Central Bank uses a "
                "pre-programmed rule: fire a guarantee announcement once 25% of "
                "agents have withdrawn, regardless of context. "
                "Represents a regulatory body that has not yet adopted AI-speed judgment. "
                "Compare to the AI CB and no-CB baseline to see the three-way difference."
            ),
            signals=_signals_high_false(is_true=False),
            banks=_BANKS,
            population=_POPULATION,
            speed=ScenarioSpeed.AI_SPEED,
            social_signal_visibility=1.0,
            seed=42,
            max_simulation_time=3600.0,
            central_bank=_CB_RULE,
        ),
    ),
]

CB_PRESET_BY_ID = {pid: (label, s) for pid, label, s in CB_PRESETS}

# ---------------------------------------------------------------------------
# Combined list used by the dashboard and run scripts
# ---------------------------------------------------------------------------

ALL_PRESETS: List[Tuple[str, str, Scenario]] = PRESETS + CB_PRESETS

PRESET_BY_ID = {pid: (label, s) for pid, label, s in PRESETS}
