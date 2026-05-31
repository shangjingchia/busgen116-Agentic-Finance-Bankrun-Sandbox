"""
Batch experiment runner.

Experiments:
  1. Latency sweep  — 5 runs: rumor_high_false at AI speed, 0.5×, 1.0×, 2.0×, 4.0×
                      human_speed_deliberation_multiplier. Uses new signal-based
                      architecture; per-archetype deliberation replaces flat delays.
"""

from __future__ import annotations

import asyncio
import copy
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core.scenario import Scenario, ScenarioSpeed
from src.core.simulation import run_scenario
from src.decisions.llm_client import LLMClient
from src.personas.instances import make_all_agents
from src.scenarios.presets import (
    _BANKS,
    _POPULATION,
    _signals_high_false,
    _signals_language_soft,
    _signals_language_neutral,
    _signals_language_charged,
)

RUNS_DIR = Path(__file__).parent.parent / "runs"


# ---------------------------------------------------------------------------
# Latency sweep
#
# Sweeps human_speed_deliberation_multiplier across 5 points.
# At multiplier=1.0 the per-archetype base times are:
#   aggressive_trader  ~4s  (+ 0.8-1.3 jitter, - anxiety scaling)
#   gig_worker         ~8s
#   cautious_retiree   ~25s
#   institutional_treasurer ~55s
#
# Counter-signals arrive at T=11s (bank denial) and T=17s (FDIC).
# At 2.0× traders decide ~T=11 — right as the denial lands.
# At 4.0× most agents see both counter-signals before deciding.
# ---------------------------------------------------------------------------

SWEEP_POINTS = [
    # (label_suffix, speed,               multiplier)
    ("000_ai",  ScenarioSpeed.AI_SPEED,    1.0),   # AI speed: 0.5-3s jitter
    ("050_hum", ScenarioSpeed.HUMAN_SPEED, 0.5),   # compressed human
    ("100_hum", ScenarioSpeed.HUMAN_SPEED, 1.0),   # natural human
    ("200_hum", ScenarioSpeed.HUMAN_SPEED, 2.0),   # slow — counter-signals start landing
    ("400_hum", ScenarioSpeed.HUMAN_SPEED, 4.0),   # very slow — full signal picture
]


def make_latency_sweep_scenario(label: str, speed: ScenarioSpeed, multiplier: float) -> Scenario:
    return Scenario(
        scenario_id=f"sweep_latency_{label}",
        name=f"Latency Sweep — {label.replace('_', ' ')}",
        description=(
            f"High-credibility false rumor. Speed={speed.value}, "
            f"deliberation_multiplier={multiplier}×. "
            "Part of latency sweep to characterise cascade vs deliberation speed."
        ),
        signals=_signals_high_false(is_true=False),
        banks=_BANKS,
        population=_POPULATION,
        speed=speed,
        human_speed_deliberation_multiplier=multiplier,
        social_signal_visibility=1.0,
        seed=42,
        max_simulation_time=3600.0,
    )


async def run_latency_sweep(client: LLMClient) -> None:
    sep = "=" * 68
    total = len(SWEEP_POINTS)
    print(f"\n{sep}")
    print(f"  LATENCY SWEEP  —  {total} runs")
    print(f"  Signal stream: high-credibility false alarm")
    print(f"  Multipliers: AI, 0.5×, 1.0×, 2.0×, 4.0×")
    print(sep)

    for i, (label, speed, multiplier) in enumerate(SWEEP_POINTS, 1):
        scenario = make_latency_sweep_scenario(label, speed, multiplier)
        agents = make_all_agents()
        print(f"\n[{i}/{total}] {scenario.scenario_id}", flush=True)
        await run_scenario(scenario, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True)

    print(f"\n{sep}")
    print("  LATENCY SWEEP COMPLETE")
    print(sep)
    print(client.format_cost_summary())


# ---------------------------------------------------------------------------
# Language sweep
#
# Three runs with IDENTICAL credibility (0.50) and alarm (0.45) numbers.
# Only the signal wording changes: soft → neutral → charged.
# Bank is solvent in all three runs (is_true=False).
#
# Hypothesis: if withdrawal fraction or speed differs across these three,
# agents are reacting to semantic surface rather than the stated credibility.
# ---------------------------------------------------------------------------

LANGUAGE_SWEEP_POINTS = [
    # (scenario_id,   display_label,      signal_fn)
    ("lang_soft",    "Soft language",     _signals_language_soft),
    ("lang_neutral", "Neutral language",  _signals_language_neutral),
    ("lang_charged", "Charged language",  _signals_language_charged),
]


def make_language_sweep_scenario(scenario_id: str, label: str, signal_fn) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        name=f"Language Sweep — {label}",
        description=(
            f"Credibility fixed at 0.50, alarm at 0.45 for all language-sweep runs. "
            f"Wording: {label.lower()}. Bank is solvent. "
            "Part of language-sensitivity experiment."
        ),
        signals=signal_fn(is_true=False),
        banks=_BANKS,
        population=_POPULATION,
        speed=ScenarioSpeed.AI_SPEED,
        social_signal_visibility=1.0,
        seed=42,
        max_simulation_time=3600.0,
    )


async def run_language_sweep(client: LLMClient) -> None:
    sep = "=" * 68
    total = len(LANGUAGE_SWEEP_POINTS)
    print(f"\n{sep}")
    print(f"  LANGUAGE SWEEP  —  {total} runs")
    print(f"  Credibility: 0.50 (locked) · Alarm: 0.45 (locked)")
    print(f"  Variable: signal wording only (soft / neutral / charged)")
    print(f"  Bank: solvent in all three")
    print(sep)

    for i, (sid, label, signal_fn) in enumerate(LANGUAGE_SWEEP_POINTS, 1):
        scenario = make_language_sweep_scenario(sid, label, signal_fn)
        agents = make_all_agents()
        print(f"\n[{i}/{total}] {sid}  ({label})", flush=True)
        await run_scenario(scenario, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True)

    print(f"\n{sep}")
    print("  LANGUAGE SWEEP COMPLETE")
    print(sep)
    print(client.format_cost_summary())


async def _run_all(client: LLMClient) -> None:
    await run_latency_sweep(client)
    await run_language_sweep(client)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run bank-run experiments")
    parser.add_argument(
        "experiment",
        nargs="?",
        default="latency",
        choices=["latency", "language", "all"],
        help="Which sweep to run (default: latency)",
    )
    args = parser.parse_args()

    client = LLMClient()
    if args.experiment == "latency":
        asyncio.run(run_latency_sweep(client))
    elif args.experiment == "language":
        asyncio.run(run_language_sweep(client))
    else:
        asyncio.run(_run_all(client))
