"""
Cross-model replication analysis: is "which LLM you delegate to" a stable driver
of bank-run propensity, or just sampling noise?

For each model, loads every modelcmp_<slug>_<scen>_*.json rep and reports:
  - final-action withdrawal fraction per rep (the metric analyze_runs.py uses)
  - mean / min / max across reps  (the variance band)
  - fallback-decision count per rep (a run with many fallbacks is contaminated:
    the model failed to emit structured decisions and silently held)
  - "ever-attempted" fraction (agents who decided to run at any point, even if
    they later reversed to hold) — the gap vs final-action exposes walk-back behavior

Usage:  python -m scripts.analyze_model_comparison [false|true]
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"

MODELS = [
    ("claude",   "Claude Haiku 4.5"),
    ("gpt",      "GPT-5.4 Mini"),
    ("gemini",   "Gemini 3.5 Flash"),
    ("grok",     "Grok 4.3"),
    ("mistral",  "Mistral Medium 3.5"),
    ("deepseek", "DeepSeek V4 Flash"),
]

WITHDRAW = {"full_withdraw", "partial_withdraw"}


def rep_metrics(path: str) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    agents = d["agent_final_states"]
    n = len(agents) or 12
    final_withdrew = 0
    ever_withdrew = 0
    fallback_decisions = 0
    total_decisions = 0
    for a in agents:
        dh = a.get("decision_history", [])
        for x in dh:
            total_decisions += 1
            if x.get("model_used") == "fallback":
                fallback_decisions += 1
        final = dh[-1]["action"] if dh else "hold"
        if final in WITHDRAW:
            final_withdrew += 1
        if any(x.get("action") in WITHDRAW for x in dh):
            ever_withdrew += 1
    return {
        "file": Path(path).name,
        "n": n,
        "final_frac": final_withdrew / n,
        "ever_frac": ever_withdrew / n,
        "fallback_decisions": fallback_decisions,
        "total_decisions": total_decisions,
    }


def main() -> None:
    scen = sys.argv[1] if len(sys.argv) > 1 else "false"
    print(f"CROSS-MODEL REPLICATION — scenario tag: '{scen}' "
          f"({'false alarm: withdrawing = the ERROR' if scen == 'false' else 'true alarm: withdrawing = correct'})")
    print("=" * 88)
    print(f"{'Model':<20} {'reps':>4}  {'final-withdraw frac (mean [min-max])':<34} {'ever-attempted':>15}  flags")
    print("-" * 88)

    rows = []
    for slug, disp in MODELS:
        files = sorted(glob.glob(str(RUNS / f"modelcmp_{slug}_{scen}_*.json")))
        reps = [rep_metrics(f) for f in files]
        # split clean vs contaminated (>=6 fallback decisions ≈ a model that couldn't participate)
        clean = [r for r in reps if r["fallback_decisions"] < 6]
        contaminated = len(reps) - len(clean)
        if not clean:
            print(f"{disp:<20} {len(reps):>4}  {'— all reps high-fallback —':<34} {'':>15}  EXCLUDED")
            continue
        fr = [r["final_frac"] for r in clean]
        ev = [r["ever_frac"] for r in clean]
        mean = sum(fr) / len(fr)
        ever_mean = sum(ev) / len(ev)
        flags = []
        if contaminated:
            flags.append(f"{contaminated} contaminated rep(s) dropped")
        band = f"{mean:.0%}  [{min(fr):.0%}-{max(fr):.0%}]"
        print(f"{disp:<20} {len(clean):>4}  {band:<34} {ever_mean:>14.0%}  {'; '.join(flags)}")
        rows.append((disp, mean, min(fr), max(fr), ever_mean, len(clean)))

    print("-" * 88)
    if len(rows) >= 2:
        rows_sorted = sorted(rows, key=lambda r: -r[1])
        top, bot = rows_sorted[0], rows_sorted[-1]
        print(f"\nSpread: {top[0]} ({top[1]:.0%}) vs {bot[0]} ({bot[1]:.0%}) "
              f"= {top[1] - bot[1]:.0%} pts attributable to model identity alone.")
        # ranking stability: do the extreme bands overlap?
        overlap = top[2] <= bot[3]
        print(f"Band overlap between extremes: {'YES — ranking NOT robust at this n' if overlap else 'NO — ranking is stable across reps'}")
        print("\nReversal/walk-back (ever-attempted minus final): a large gap = the model's "
              "agents panic then reconsider; a ~0 gap = they lock in.")
        for disp, mean, lo, hi, ever, nrep in rows_sorted:
            print(f"  {disp:<20} attempted {ever:.0%} -> stayed-out {mean:.0%}  (walk-back {ever - mean:+.0%})")


if __name__ == "__main__":
    main()
