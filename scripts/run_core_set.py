"""Re-run the core demo set with the bulletproofed engine + real economics.

Runs the 5 rumor presets at AI and human speed, plus the 4 CB presets (AI speed),
saving each to runs/. A fresh LLMClient per run keeps per-run cost/metrics isolated.

Usage:  python -m scripts.run_core_set
"""

from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=str(ROOT / ".env"))

from src.core.scenario import ScenarioSpeed  # noqa: E402
from src.core.simulation import run_scenario  # noqa: E402
from src.decisions.llm_client import LLMClient  # noqa: E402
from src.personas.instances import make_all_agents  # noqa: E402
from src.scenarios.presets import CB_PRESETS, PRESETS  # noqa: E402

RUNS_DIR = ROOT / "runs"

# Rumor presets to re-run at BOTH speeds (skip payment_contagion — already run).
RUMOR_IDS = [
    "rumor_moderate_false",
    "rumor_high_true",
    "rumor_high_false",
    "rumor_weak_true",
    "rumor_weak_false",
]

PRESET_BY_ID = {pid: s for pid, _, s in PRESETS}


def _jobs():
    for pid in RUMOR_IDS:
        scen = PRESET_BY_ID[pid]
        yield f"{pid} [AI]", scen
        yield f"{pid} [HUMAN]", dataclasses.replace(scen, speed=ScenarioSpeed.HUMAN_SPEED)
    for pid, _, scen in CB_PRESETS:
        yield f"{pid} [AI+CB]", scen


def main() -> None:
    jobs = list(_jobs())
    total_cost = 0.0
    print(f"Running {len(jobs)} core-set simulations → {RUNS_DIR}\n")
    for i, (label, scen) in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] {label} …", flush=True)
        try:
            agents = make_all_agents()
            client = LLMClient()  # fresh per run → isolated cost/metrics
            res = asyncio.run(
                run_scenario(scen, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=False)
            )
            m = res.metrics
            total_cost += m.total_cost_usd
            print(
                f"      done · withdrew {m.withdrawn_count}+{m.partially_withdrawn_count}p "
                f"· susp {m.bank_suspension_time} · cascade {m.cascade_triggered} "
                f"· cb {m.cb_action} · ${m.total_cost_usd:.3f} (cum ${total_cost:.2f})",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 — keep the batch going
            print(f"      FAILED: {exc}", flush=True)
    print(f"\nCore set complete. Total cost ≈ ${total_cost:.2f}")


if __name__ == "__main__":
    main()
