"""
Credibility threshold sweep.

Runs the same false-bank scenario (bank is solvent) at 7 credibility levels
× 2 speeds (AI and Human) to find where each speed triggers a cascade.

Saves results to runs/ — the Compare view picks them up automatically.
Skips any (scenario_id, speed) pair that already exists.

Usage:
    python scripts/run_credibility_sweep.py
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv()

CREDIBILITIES = [0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85]
RUNS_DIR = Path(__file__).parent.parent / "runs"
BASE_PRESET_ID = "rumor_moderate_false"
SEED = 42


def _already_run(scenario_id: str, speed: str) -> bool:
    for p in RUNS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("scenario_id") == scenario_id and data.get("speed") == speed:
                return True
        except Exception:
            continue
    return False


async def run_one(credibility: float, speed_enum, speed_str: str) -> None:
    from src.core.simulation import run_scenario
    from src.decisions.llm_client import LLMClient
    from src.personas.instances import make_all_agents
    from src.scenarios.presets import PRESET_BY_ID

    cred_int = int(round(credibility * 100))
    scenario_id = f"sweep_false_{cred_int:03d}"

    if _already_run(scenario_id, speed_str):
        print(f"  skip  {scenario_id}/{speed_str} — already exists")
        return

    _, base_scenario = PRESET_BY_ID[BASE_PRESET_ID]
    s = copy.deepcopy(base_scenario)
    s.rumors[0].credibility = credibility
    s.speed = speed_enum
    # AI agents monitor feeds continuously; human depositors see a filtered subset.
    s.social_signal_visibility = 1.0 if speed_str == "ai" else 0.55
    s.seed = SEED
    s.scenario_id = scenario_id
    s.name = f"Credibility Sweep — {credibility:.0%} false bank"

    agents = make_all_agents()
    client = LLMClient()

    print(f"  run   {scenario_id}/{speed_str} (credibility={credibility:.0%}) ...", flush=True)
    result = await run_scenario(s, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=False)
    m = result.metrics
    n_ran = sum(
        1 for a in result.agent_final_states
        if a.get("decision_history")
        and a["decision_history"][-1].get("action") in ("full_withdraw", "partial_withdraw")
    )
    tag = "CASCADE" if n_ran / m.total_agents >= 0.25 else "held"
    print(f"         → [{tag}] {n_ran}/{m.total_agents} agents withdrew")


def main() -> None:
    from src.core.scenario import ScenarioSpeed

    RUNS_DIR.mkdir(exist_ok=True)

    combos = (
        [(c, ScenarioSpeed.AI_SPEED, "ai") for c in CREDIBILITIES]
        + [(c, ScenarioSpeed.HUMAN_SPEED, "human") for c in CREDIBILITIES]
    )

    print(f"Credibility sweep — {len(combos)} runs ({BASE_PRESET_ID}, seed={SEED})")
    for i, (cred, speed_enum, speed_str) in enumerate(combos, 1):
        print(f"[{i:02d}/{len(combos)}]", end=" ")
        asyncio.run(run_one(cred, speed_enum, speed_str))

    print("\nDone. Refresh the Compare page in the dashboard.")


if __name__ == "__main__":
    main()
