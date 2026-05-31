"""
Visibility Sweep.

Holds vocabulary fixed at the charged variant and varies social_signal_visibility
across 0%, 25%, 50%, 75%.  The 100% data point already exists from lang_charged.

This directly tests: is the cascade driven by agents herding off each other, or
by the underlying signal alone?

  - 0%  → agents see no peer withdrawals; react only to the signal
  - 25% → sparse social proof
  - 50% → half the peer activity visible
  - 75% → most peer activity visible
  - 100%→ full transparency (use lang_charged run already in runs/)

Usage:
    python scripts/run_visibility_sweep.py

Cost estimate: ~4 runs × $0.25 ≈ $1.00
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core.simulation import run_scenario
from src.decisions.llm_client import LLMClient
from src.personas.instances import make_all_agents
from src.scenarios.presets import VISIBILITY_LEVELS, make_visibility_sweep_scenario

RUNS_DIR = Path(__file__).parent.parent / "runs"


async def main() -> None:
    client = LLMClient()
    sep = "=" * 68
    total = len(VISIBILITY_LEVELS)

    print(f"\n{sep}")
    print(f"  VISIBILITY SWEEP  —  {total} runs  (+1 existing: lang_charged at 100%)")
    print(f"  Vocabulary: charged (SVB-level crisis language — fixed)")
    print(f"  Variable: social_signal_visibility (0% → 75%)")
    print(f"  Question: herding vs. signal-driven cascade?")
    print(f"  Credibility: 0.50 (locked) · Alarm: 0.45 (locked) · Bank: solvent")
    print(sep)

    for i, vis in enumerate(VISIBILITY_LEVELS, 1):
        vis_pct = round(vis * 100)
        sid = f"vis_charged_{vis_pct:03d}"
        print(f"\n[{i}/{total}] {sid}  (peer visibility = {vis_pct}%)", flush=True)
        scenario = make_visibility_sweep_scenario(vis)
        agents = make_all_agents()
        await run_scenario(
            scenario, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True
        )

    print(f"\n{sep}")
    print("  VISIBILITY SWEEP COMPLETE")
    print(f"  (Combine with lang_charged run for the full 0%–100% picture)")
    print(sep)
    print(client.format_cost_summary())


if __name__ == "__main__":
    asyncio.run(main())
