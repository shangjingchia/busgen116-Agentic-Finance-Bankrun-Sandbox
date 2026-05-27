"""
Batch experiment runner for additional simulation runs.

Experiments (in priority order):
  1. Latency sweep        — 7 runs: rumor_high_false at 0s,10s,20s,30s,45s,60s,90s delay
  2. Persona extremes     — 4 runs: all-retiree and all-treasurer populations, AI+human speed
  3. Model isolation      — 2 runs: force all agents to Haiku (patch routing threshold)
  4. Low-cred extension   — 3 runs: credibility at 5%, 10%, 15% (extend existing sweep)
"""

from __future__ import annotations

import asyncio
import copy
import os
import sys
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core.scenario import (
    AgentPopulationGroup,
    BankConfig,
    RumorConfig,
    Scenario,
    ScenarioSpeed,
)
from src.core.simulation import run_scenario
from src.decisions.llm_client import LLMClient
from src.personas.instances import (
    make_margaret_chen,
    make_robert_petersen,
    make_linda_vo,
    make_james_okonkwo,
    make_sarah_kim,
    make_robert_achebe,
    make_all_agents,
)
from src.scenarios.presets import _BANKS, _POPULATION, _RUMOR_HIGH
import src.decisions.strategies as strategies

RUNS_DIR = Path(__file__).parent.parent / "runs"


# ---------------------------------------------------------------------------
# Shared rumor config (high-credibility, false alarm)
# ---------------------------------------------------------------------------

def _high_false_rumor(credibility: float = 0.85) -> RumorConfig:
    return RumorConfig(
        content=_RUMOR_HIGH,
        source="market_terminal_alert",
        credibility=credibility,
        target_bank_id="bank_a",
        publish_at_time=0.0,
        is_true=False,
        propagation_latency_seconds=3.0,
    )


# ===========================================================================
# Experiment 1: Latency sweep
# 7 runs: 0s (AI_SPEED), 10s, 20s, 30s, 45s, 60s, 90s (HUMAN_SPEED)
# Isolates the cascade threshold as a function of deliberation delay alone.
# ===========================================================================

LATENCY_DELAYS = [0, 10, 20, 30, 45, 60, 90]


def make_latency_sweep_scenario(delay_seconds: int) -> Scenario:
    if delay_seconds == 0:
        speed = ScenarioSpeed.AI_SPEED
        sid = "sweep_latency_000s"
    else:
        speed = ScenarioSpeed.HUMAN_SPEED
        sid = f"sweep_latency_{delay_seconds:03d}s"

    return Scenario(
        scenario_id=sid,
        name=f"Latency Sweep — {delay_seconds}s Decision Delay",
        description=(
            f"High-credibility false rumor, {delay_seconds}s per-agent decision delay. "
            "Part of latency sweep (0-90s) to find cascade threshold."
        ),
        rumors=[_high_false_rumor()],
        banks=_BANKS,
        population=_POPULATION,
        speed=speed,
        human_speed_decision_delay_seconds=float(delay_seconds),
        social_signal_visibility=1.0,
        seed=42,
        max_simulation_time=3600.0,
    )


# ===========================================================================
# Experiment 2: Persona extremes
# 4 runs: all-retiree and all-treasurer, AI and human speed.
# Tests whether cascade dynamics are archetype-universal or driven by the mix.
# ===========================================================================

def _clone_agents(base_builders, n: int, id_prefix: str):
    """Deepcopy n*len(base_builders) agents with unique IDs."""
    agents = []
    for i in range(n):
        for fn in base_builders:
            a = copy.deepcopy(fn())
            a.agent_id = f"{id_prefix}_{a.agent_id}_{i}"
            agents.append(a)
    return agents


def make_all_retirees():
    return _clone_agents(
        [make_margaret_chen, make_robert_petersen, make_linda_vo],
        n=4,
        id_prefix="xp",
    )


def make_all_treasurers():
    return _clone_agents(
        [make_james_okonkwo, make_sarah_kim, make_robert_achebe],
        n=4,
        id_prefix="xp",
    )


def make_persona_extreme_scenario(archetype: str, speed: ScenarioSpeed, delay: float) -> Scenario:
    speed_label = speed.value
    return Scenario(
        scenario_id=f"persona_all_{archetype}_{speed_label}",
        name=f"Persona Extreme — All {archetype.replace('_', ' ').title()} ({speed_label})",
        description=(
            f"12 agents, all {archetype} archetype. High-credibility false rumor. "
            "Tests whether cascade requires mixed population or any single archetype sustains it."
        ),
        rumors=[_high_false_rumor()],
        banks=_BANKS,
        population=_POPULATION,
        speed=speed,
        human_speed_decision_delay_seconds=delay,
        social_signal_visibility=1.0,
        seed=42,
        max_simulation_time=3600.0,
    )


# ===========================================================================
# Experiment 3: Model capability isolation
# 2 runs: full mixed population, all Haiku (patch routing threshold to ∞).
# Tests whether institutional first-mover advantage is model capability or persona.
# ===========================================================================

def make_model_isolation_scenario(speed: ScenarioSpeed, delay: float) -> Scenario:
    return Scenario(
        scenario_id=f"model_isolation_all_haiku_{speed.value}",
        name=f"Model Isolation — All Haiku ({speed.value} speed)",
        description=(
            "Same as rumor_high_false but LARGE_PORTFOLIO_USD patched to ∞ "
            "so all agents use Haiku. Tests if institutional exit-order advantage "
            "is model-capability-driven or persona-driven."
        ),
        rumors=[_high_false_rumor()],
        banks=_BANKS,
        population=_POPULATION,
        speed=speed,
        human_speed_decision_delay_seconds=delay,
        social_signal_visibility=1.0,
        seed=42,
        max_simulation_time=3600.0,
    )


# ===========================================================================
# Experiment 4: Low-credibility extension
# 3 runs: 5%, 10%, 15% credibility at AI speed (extends existing 25-85% sweep).
# Completes the lower tail — at what label does the cascade finally break down?
# ===========================================================================

LOW_CRED_LEVELS = [0.05, 0.10, 0.15]


def make_low_cred_scenario(credibility: float) -> Scenario:
    pct = int(credibility * 100)
    return Scenario(
        scenario_id=f"sweep_false_{pct:03d}_ai",
        name=f"Low-Credibility Extension — {pct}% (AI speed)",
        description=(
            f"Same alarming rumor content as rumor_high_false, labeled {pct}% credible. "
            "Extends credibility sweep into the very low range."
        ),
        rumors=[_high_false_rumor(credibility=credibility)],
        banks=_BANKS,
        population=_POPULATION,
        speed=ScenarioSpeed.AI_SPEED,
        social_signal_visibility=1.0,
        seed=42,
        max_simulation_time=3600.0,
    )


# ===========================================================================
# Runner
# ===========================================================================

async def run_all() -> None:
    client = LLMClient()
    sep = "=" * 68

    print(f"\n{sep}")
    print("  BATCH EXPERIMENT RUNNER  —  16 runs total")
    print(sep)

    completed = 0
    total = 16

    # ── 1. Latency sweep ────────────────────────────────────────────────────
    print(f"\n[Experiment 1/4] LATENCY SWEEP  (7 runs)")
    for delay in LATENCY_DELAYS:
        scenario = make_latency_sweep_scenario(delay)
        agents = make_all_agents()
        print(f"  [{completed+1}/{total}] {scenario.scenario_id} ...", flush=True)
        await run_scenario(scenario, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True)
        completed += 1

    # ── 2. Persona extremes ─────────────────────────────────────────────────
    print(f"\n[Experiment 2/4] PERSONA EXTREMES  (4 runs)")
    persona_configs = [
        ("cautious_retiree",        make_all_retirees,   ScenarioSpeed.AI_SPEED,    0.0),
        ("cautious_retiree",        make_all_retirees,   ScenarioSpeed.HUMAN_SPEED, 90.0),
        ("institutional_treasurer", make_all_treasurers, ScenarioSpeed.AI_SPEED,    0.0),
        ("institutional_treasurer", make_all_treasurers, ScenarioSpeed.HUMAN_SPEED, 90.0),
    ]
    for archetype, make_fn, speed, delay in persona_configs:
        scenario = make_persona_extreme_scenario(archetype, speed, delay)
        agents = make_fn()
        print(f"  [{completed+1}/{total}] {scenario.scenario_id} ...", flush=True)
        await run_scenario(scenario, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True)
        completed += 1

    # ── 3. Model capability isolation ───────────────────────────────────────
    print(f"\n[Experiment 3/4] MODEL ISOLATION — ALL HAIKU  (2 runs)")
    original_threshold = strategies.LARGE_PORTFOLIO_USD
    strategies.LARGE_PORTFOLIO_USD = 999_999_999.0
    try:
        for speed, delay in [
            (ScenarioSpeed.AI_SPEED,    0.0),
            (ScenarioSpeed.HUMAN_SPEED, 90.0),
        ]:
            scenario = make_model_isolation_scenario(speed, delay)
            agents = make_all_agents()
            print(f"  [{completed+1}/{total}] {scenario.scenario_id} ...", flush=True)
            await run_scenario(scenario, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True)
            completed += 1
    finally:
        strategies.LARGE_PORTFOLIO_USD = original_threshold

    # ── 4. Low-credibility extension ────────────────────────────────────────
    print(f"\n[Experiment 4/4] LOW-CREDIBILITY EXTENSION  (3 runs)")
    for cred in LOW_CRED_LEVELS:
        scenario = make_low_cred_scenario(cred)
        agents = make_all_agents()
        print(f"  [{completed+1}/{total}] {scenario.scenario_id} ...", flush=True)
        await run_scenario(scenario, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True)
        completed += 1

    print(f"\n{sep}")
    print(f"  ALL {total} EXPERIMENTS COMPLETE")
    print(sep)
    print(client.format_cost_summary())


if __name__ == "__main__":
    asyncio.run(run_all())
