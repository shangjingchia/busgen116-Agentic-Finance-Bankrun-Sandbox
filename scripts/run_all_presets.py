"""
Batch runner: runs all 5 preset scenarios at both AI speed and Human speed.
Saves each run to runs/ directory for use by the comparison view.

Usage:
    python scripts/run_all_presets.py
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
from src.scenarios.presets import PRESETS

RUNS_DIR = Path(__file__).parent.parent / "runs"


async def run_all() -> None:
    total = len(PRESETS) * 2
    done = 0

    for pid, label, scenario_template in PRESETS:
        for speed in [ScenarioSpeed.AI_SPEED, ScenarioSpeed.HUMAN_SPEED]:
            done += 1
            speed_label = "AI Speed" if speed == ScenarioSpeed.AI_SPEED else "Human Speed"
            print(f"\n[{done}/{total}] {label}  [{speed_label}]")
            print("─" * 62)

            s = copy.deepcopy(scenario_template)
            s.speed = speed
            # AI agents monitor feeds continuously; human depositors see a filtered subset.
            s.social_signal_visibility = 1.0 if speed == ScenarioSpeed.AI_SPEED else 0.55
            # Keep preset seed for reproducibility — same agents, same RNG,
            # only the speed differs. This makes AI vs human comparison clean.

            agents = make_all_agents()
            client = LLMClient()

            try:
                await run_scenario(
                    s,
                    agents,
                    llm_client=client,
                    runs_dir=RUNS_DIR,
                    verbose=True,
                )
            except Exception as exc:
                print(f"  ERROR: {exc}")
                continue

    print(f"\n✓ All {total} runs complete. Saved to {RUNS_DIR}/")


if __name__ == "__main__":
    asyncio.run(run_all())
