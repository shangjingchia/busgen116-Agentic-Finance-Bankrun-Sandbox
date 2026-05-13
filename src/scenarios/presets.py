"""
Preset scenario factory functions used by the dashboard configure page.

Five presets cover the 2×2 credibility/truth matrix plus a baseline:
  rumor_moderate_false  — moderate credibility, bank fine (unnecessary panic)
  rumor_high_true       — high credibility, bank insolvent (real crisis)
  rumor_high_false      — high credibility, bank fine (maximum false alarm)
  rumor_weak_true       — low credibility, bank insolvent (slow burn)
  rumor_weak_false      — low credibility, bank fine (noise test)
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

# ---------------------------------------------------------------------------
# Shared bank and population configs
# ---------------------------------------------------------------------------

_BANKS: List[BankConfig] = [
    BankConfig(
        bank_id="bank_a",
        name="Bank A",
        initial_reserve_ratio=0.40,   # 40% — Basel III LCR-aligned, starts well above distress
        early_withdrawal_fee_rate=0.03,
        withdrawal_processing_capacity=5_000_000.0,
        distress_threshold=0.20,      # enters distress after ~50% of reserves withdrawn
        suspension_threshold=0.05,    # suspends when nearly depleted
    ),
    BankConfig(
        bank_id="bank_b",
        name="Bank B",
        initial_reserve_ratio=0.30,   # 30% — healthy safe-haven bank, starts above distress
        early_withdrawal_fee_rate=0.02,
        withdrawal_processing_capacity=5_000_000.0,
    ),
]

_POPULATION: List[AgentPopulationGroup] = [
    AgentPopulationGroup("cautious_retiree", 3, "bank_a", (25_000, 52_000), "bank_b", (6_000, 19_000)),
    AgentPopulationGroup("aggressive_trader", 3, "bank_a", (11_000, 38_000), "bank_b", (3_000, 9_000)),
    AgentPopulationGroup("gig_worker", 3, "bank_a", (1_800, 3_200), "bank_b", (350, 600)),
    AgentPopulationGroup("institutional_treasurer", 3, "bank_a", (310_000, 590_000), "bank_b", (85_000, 260_000)),
]

# ---------------------------------------------------------------------------
# Rumor content strings
# ---------------------------------------------------------------------------

_RUMOR_HIGH = (
    "Multiple verified sources — including two major financial data providers and a "
    "regulatory filing — indicate that Bank A has failed a stress test and cannot "
    "meet its liquidity coverage ratio. The bank's CEO has cancelled a scheduled "
    "earnings call without explanation. Trading in the bank's stock has been halted."
)

_RUMOR_MODERATE = (
    "Bank A is facing a severe liquidity crisis and may not be able to meet all "
    "withdrawal requests. Several large corporate depositors are rumored to have "
    "already begun moving funds. A regional financial news outlet flagged concerns "
    "based on the bank's most recent call report."
)

_RUMOR_LOW = (
    "An anonymous post on a financial message board claims Bank A is in serious "
    "trouble. No official sources have confirmed the claim. The identity of the "
    "poster is unknown and the post has not been picked up by any major outlet."
)

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
            rumors=[
                RumorConfig(
                    content=_RUMOR_MODERATE,
                    source="financial_news_outlet",
                    credibility=0.55,
                    target_bank_id="bank_a",
                    publish_at_time=0.0,
                    is_true=False,
                    propagation_latency_seconds=5.0,
                )
            ],
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
                "A high-credibility rumor about Bank A from official sources. "
                "The bank really is insolvent. Tests cascade speed when the "
                "signal is both credible and true — the worst case."
            ),
            rumors=[
                RumorConfig(
                    content=_RUMOR_HIGH,
                    source="financial_regulator",
                    credibility=0.85,
                    target_bank_id="bank_a",
                    publish_at_time=0.0,
                    is_true=True,
                    propagation_latency_seconds=3.0,
                )
            ],
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
                "A high-credibility rumor from what appear to be official sources, "
                "but the bank is actually solvent. Tests the maximum false-alarm cascade: "
                "how badly do AI agents run on a false but credible signal?"
            ),
            rumors=[
                RumorConfig(
                    content=_RUMOR_HIGH,
                    source="financial_regulator",
                    credibility=0.85,
                    target_bank_id="bank_a",
                    publish_at_time=0.0,
                    is_true=False,
                    propagation_latency_seconds=3.0,
                )
            ],
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
            rumors=[
                RumorConfig(
                    content=_RUMOR_LOW,
                    source="social_media",
                    credibility=0.25,
                    target_bank_id="bank_a",
                    publish_at_time=0.0,
                    is_true=True,
                    propagation_latency_seconds=10.0,
                )
            ],
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
            rumors=[
                RumorConfig(
                    content=_RUMOR_LOW,
                    source="social_media",
                    credibility=0.25,
                    target_bank_id="bank_a",
                    publish_at_time=0.0,
                    is_true=False,
                    propagation_latency_seconds=10.0,
                )
            ],
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
            rumors=[
                RumorConfig(
                    content=_RUMOR_HIGH,
                    source="financial_regulator",
                    credibility=0.85,
                    target_bank_id="bank_a",
                    publish_at_time=0.0,
                    is_true=False,
                    propagation_latency_seconds=3.0,
                )
            ],
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
            rumors=[
                RumorConfig(
                    content=_RUMOR_HIGH,
                    source="financial_regulator",
                    credibility=0.85,
                    target_bank_id="bank_a",
                    publish_at_time=0.0,
                    is_true=False,
                    propagation_latency_seconds=3.0,
                )
            ],
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
