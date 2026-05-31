"""
SVB Vocabulary Grid Sweep.

Runs 12 scenarios — 4 vocabulary categories × 3 intensity levels — with all
controls locked identically to the language-sweep experiment (credibility=0.50,
alarm=0.45, bank solvent, seed=42).  Only the vocabulary kernel changes: one
key phrase per cell, drawn from documented SVB-era coverage.

Usage:
    python scripts/run_vocab_sweep.py

Cost estimate: ~12 runs × $0.01–0.015 per run ≈ $0.15–0.18 total.
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
from src.scenarios.presets import (
    VOCAB_CATEGORIES,
    VOCAB_LEVELS,
    VOCAB_CATEGORY_LABELS,
    VOCAB_LEVEL_LABELS,
    VOCAB_GRID_PHRASES,
    make_vocab_sweep_scenario,
)

RUNS_DIR = Path(__file__).parent.parent / "runs"


async def main() -> None:
    client = LLMClient()
    sep = "=" * 68
    total = len(VOCAB_CATEGORIES) * len(VOCAB_LEVELS)

    print(f"\n{sep}")
    print(f"  SVB VOCABULARY GRID SWEEP  —  {total} runs")
    print(f"  4 categories × 3 intensity levels")
    print(f"  Credibility: 0.50 (locked) · Alarm: 0.45 (locked) · Bank: solvent")
    print(f"  All controls identical to language-sweep experiment")
    print(sep)

    n = 0
    for category in VOCAB_CATEGORIES:
        for level in VOCAB_LEVELS:
            n += 1
            sid = f"vocab_{category}_{level}"
            cat_label = VOCAB_CATEGORY_LABELS[category]
            lev_label = VOCAB_LEVEL_LABELS[level]
            key_phrase = VOCAB_GRID_PHRASES[category][level]["key_phrase"]
            svb_anchor = VOCAB_GRID_PHRASES[category][level]["svb_anchor"]

            print(f"\n[{n}/{total}] {sid}")
            print(f"  Category  : {cat_label}")
            print(f"  Level     : {lev_label}")
            print(f"  Key phrase: '{key_phrase}'")
            print(f"  SVB anchor: {svb_anchor}", flush=True)

            scenario = make_vocab_sweep_scenario(category, level)
            agents = make_all_agents()
            await run_scenario(
                scenario, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True
            )

    print(f"\n{sep}")
    print("  VOCABULARY GRID SWEEP COMPLETE")
    print(sep)
    print(client.format_cost_summary())


if __name__ == "__main__":
    asyncio.run(main())
