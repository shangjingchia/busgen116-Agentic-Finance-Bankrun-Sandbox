"""
Day-3 manual inspection: render each archetype's system prompt for human review.

No LLM calls. Outputs:
  - Per-archetype system prompts under runs/inspections/<timestamp>/
  - A side-by-side summary table to stdout (archetype, prompt size, cost-function
    severity distribution, voice example count, threshold).

PLAN.md says: "Manually inspect prompts for all four personas. They should
sound like four different people." This script puts them in front of you.

Usage:
    .venv\\Scripts\\python scripts\\inspect_personas.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import Counter
from pathlib import Path

# Force UTF-8 stdout so em-dashes render on the Windows console.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.agent import Severity
from src.personas.instances import make_all_canonical_agents
from src.personas.prompts import render_persona_system_prompt


SEVERITY_ORDER = [
    Severity.CATASTROPHIC,
    Severity.SIGNIFICANT,
    Severity.MODERATE,
    Severity.MINOR,
    Severity.IRRELEVANT,
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render all canonical personas for inspection.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("runs/inspections"),
        help="Directory under which a timestamped folder is created.",
    )
    args = parser.parse_args(argv)

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out_dir / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    agents = make_all_canonical_agents()

    print()
    print("=" * 78)
    print(f"Day-3 persona inspection — {timestamp}")
    print(f"Output dir: {out_dir}")
    print("=" * 78)
    print()

    # --- per-archetype prompt files --------------------------------------
    for agent in agents:
        prompt = render_persona_system_prompt(agent.persona)
        path = out_dir / f"{agent.persona.archetype}__{agent.agent_id}.md"
        path.write_text(
            f"# {agent.persona.name} ({agent.persona.archetype})\n\n"
            f"agent_id: `{agent.agent_id}`  \n"
            f"age: {agent.persona.age}  \n"
            f"dependents: {agent.persona.dependents}  \n"
            f"income_annual: ${agent.persona.income_annual:,.0f}  \n"
            f"portfolio total: ${agent.total_wealth():,.0f}  \n"
            f"peer_action_reconsideration_threshold: "
            f"{agent.persona.peer_action_reconsideration_threshold}  \n\n"
            f"## Rendered system prompt\n\n"
            f"```\n{prompt}\n```\n",
            encoding="utf-8",
        )

    # --- side-by-side summary table to stdout ----------------------------
    rows: list[dict[str, str]] = []
    for agent in agents:
        sev_counts = Counter(item.severity for item in agent.persona.cost_function)
        sev_summary = " ".join(
            f"{s.value[:4]}={sev_counts.get(s, 0)}"
            for s in SEVERITY_ORDER
        )
        prompt = render_persona_system_prompt(agent.persona)
        rows.append({
            "archetype": agent.persona.archetype,
            "name": agent.persona.name,
            "age": str(agent.persona.age),
            "wealth": f"${agent.total_wealth():,.0f}",
            "voice_lines": str(len(agent.persona.voice_examples)),
            "peer_thresh": f"{agent.persona.peer_action_reconsideration_threshold:.2f}",
            "prompt_chars": f"{len(prompt):,}",
            "severities": sev_summary,
        })

    headers = ["archetype", "name", "age", "wealth", "voice_lines",
               "peer_thresh", "prompt_chars", "severities"]
    widths = {h: max(len(h), max(len(r[h]) for r in rows)) for h in headers}

    print("  ".join(h.ljust(widths[h]) for h in headers))
    print("  ".join("-" * widths[h] for h in headers))
    for r in rows:
        print("  ".join(r[h].ljust(widths[h]) for h in headers))

    print()
    print("Severity legend: cata=catastrophic, sign=significant, mode=moderate, "
          "mino=minor, irre=irrelevant")
    print()
    print(f"Per-archetype prompt files written to: {out_dir}")
    print()

    # --- voice & trust quick-look (so you can eyeball distinctness) -------
    print("=" * 78)
    print("Voice & trust quick-look (read these out loud — they should sound different)")
    print("=" * 78)
    for agent in agents:
        print()
        print(f"## {agent.persona.archetype} — {agent.persona.name}")
        print(f"  trust profile: {agent.persona.trust_profile[:200]}...")
        print(f"  voice examples:")
        for v in agent.persona.voice_examples:
            print(f"    - \"{v}\"")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
