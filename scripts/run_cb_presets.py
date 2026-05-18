"""
Run the Central Bank preset scenarios (AI speed only — CB is most interesting at AI speed).

Generates three comparable runs:
  rumor_high_false           — baseline, no CB intervention
  rumor_high_false_llm_cb    — AI-powered CB intervenes at 25% withdrawal threshold
  rumor_high_false_rule_cb   — Rule-based CB fires same action at 25% threshold

Usage:
    python scripts/run_cb_presets.py
"""

from __future__ import annotations

import asyncio
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.core.scenario import ScenarioSpeed
from src.core.simulation import run_scenario
from src.decisions.llm_client import LLMClient
from src.personas.instances import make_all_agents
from src.scenarios.presets import CB_PRESETS, PRESET_BY_ID

RUNS_DIR = Path(__file__).parent.parent / "runs"

# Baseline scenario IDs to include for comparison
_BASELINE_IDS = ("rumor_high_false",)


async def run_cb_comparison() -> None:
    runs_to_execute = []

    # Include the baseline (no CB) at AI speed
    for bid in _BASELINE_IDS:
        if bid in PRESET_BY_ID:
            label, scenario = PRESET_BY_ID[bid]
            s = copy.deepcopy(scenario)
            s.speed = ScenarioSpeed.AI_SPEED
            s.social_signal_visibility = 1.0
            runs_to_execute.append((bid, f"{label}  [AI Speed, no CB]", s))

    # Include both CB variants
    for pid, label, scenario_template in CB_PRESETS:
        s = copy.deepcopy(scenario_template)
        s.speed = ScenarioSpeed.AI_SPEED
        s.social_signal_visibility = 1.0
        runs_to_execute.append((pid, label, s))

    total = len(runs_to_execute)
    print(f"\nRunning {total} Central Bank comparison scenarios...\n")

    for i, (pid, label, scenario) in enumerate(runs_to_execute, 1):
        cb_label = ""
        if scenario.central_bank:
            cb_label = f"  [CB: {scenario.central_bank.policy_type}  threshold={scenario.central_bank.trigger_threshold:.0%}]"
        print(f"[{i}/{total}] {label}{cb_label}")
        print("─" * 68)

        agents = make_all_agents()
        client = LLMClient()

        try:
            await run_scenario(
                scenario,
                agents,
                llm_client=client,
                runs_dir=RUNS_DIR,
                verbose=True,
            )
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue

    print(f"\nDone. CB comparison runs saved to {RUNS_DIR}/")
    print(
        "  Compare using the Findings page in the dashboard, "
        "or load each run individually from the Configure -> Load tab."
    )


if __name__ == "__main__":
    asyncio.run(run_cb_comparison())
