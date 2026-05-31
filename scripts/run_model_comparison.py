"""Cross-model experiment: same 12 personas, different "brains".

Runs the SAME scenario(s) with every agent forced onto a single base model, so we
can compare how risk-averse vs panic-prone each frontier LLM is as a financial
delegate. Saves each run as scenario_id `modelcmp_<modelslug>_<scenslug>` so the
Findings → "Different brains" panel can load and rank them.

Requires a funded OpenRouter key (OPENROUTER_API_KEY). Usage:
    python -m scripts.run_model_comparison
    python -m scripts.run_model_comparison --models haiku,gpt4o,gemini --runs 1

IMPORTANT: verify the OpenRouter model IDs below at https://openrouter.ai/models —
ids drift. Models that can't do structured tool-calling will degrade to "hold"
(handled gracefully) and show a high fallback rate — the script flags that so a
non-participating model isn't mistaken for a calm one.
"""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=str(ROOT / ".env"))

from src.core.simulation import run_scenario  # noqa: E402
from src.decisions.llm_client import LLMClient  # noqa: E402
from src.personas.instances import make_all_agents  # noqa: E402
from src.scenarios.presets import PRESETS  # noqa: E402

RUNS_DIR = ROOT / "runs"
PRESET_BY_ID = {pid: s for pid, _, s in PRESETS}

# (slug, OpenRouter model id, display name) — EDIT to the CURRENT flagship per
# provider. These are 2025-era ids and almost certainly NOT the latest by the time
# you run this — discover current ids with:  python -m scripts.run_model_comparison --list
# (filter e.g. --list gemini). The --list endpoint is public and works even with an
# exhausted key. Replace the ids below with whatever --list shows as newest.
MODELS = [
    # ── US labs ──
    ("claude",   "anthropic/claude-haiku-4.5",     "Claude Haiku 4.5"),
    ("gpt",      "openai/gpt-5.4-mini",            "GPT-5.4 Mini"),
    ("gemini",   "google/gemini-3.5-flash",        "Gemini 3.5 Flash"),
    ("grok",     "x-ai/grok-4.3",                  "Grok 4.3"),
    ("mistral",  "mistralai/mistral-medium-3-5",   "Mistral Medium 3.5"),
    # ── Chinese labs ──
    ("deepseek", "deepseek/deepseek-v4-flash",     "DeepSeek V4 Flash"),
    # NOTE (2026-05-30): Qwen3.6/3.7 and ByteDance Seed-2.0 verified on OpenRouter to
    # return 404/400 "no endpoints support 'tools'" for forced tool-calling — they
    # cannot emit our structured decision and degrade to all-hold (false 0% = artifact,
    # NOT calm behavior). Excluded from the quantitative comparison; the inability to
    # emit structured decisions is itself a reportable deployment constraint.
]
# ^ cheap/flash tier per provider as of 2026-05, concrete dated ids (not "*-latest"
#   aliases) so runs stay reproducible. 3 US + 3 Chinese labs. Verify/swap with
#   --list before running (e.g. `--list bytedance`, `--list gpt-5`).


def _fetch_openrouter_models(filter_substr: str | None = None):
    """List models available on OpenRouter (public endpoint), newest first, so we
    can read off the exact current ids for the latest flagship of each provider."""
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"User-Agent": "agent-bankrun"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = _json.loads(resp.read().decode("utf-8")).get("data", [])
    rows = []
    for m in data:
        mid = m.get("id", "")
        if filter_substr and filter_substr.lower() not in mid.lower():
            continue
        rows.append((m.get("created", 0), mid, m.get("name", "")))
    rows.sort(reverse=True)  # newest first
    print(f"{'created':>12}  {'id':<48} name")
    import datetime as _dt
    for created, mid, name in rows[:60]:
        ds = (_dt.datetime.fromtimestamp(created, _dt.timezone.utc).strftime("%Y-%m-%d")
              if created else "—")
        print(f"{ds:>12}  {mid:<48} {name}")
    print(f"\n{len(rows)} models"
          + (f" matching '{filter_substr}'" if filter_substr else "")
          + ". Copy the newest id you want into the MODELS list at the top of this script.")

# Scenarios to characterize each model on. A false alarm probes panic-proneness
# (ideal = hold); a true alarm probes appropriate caution (ideal = exit). Both
# together give each model a 2-D risk profile.
SCENARIOS = [
    ("false", "rumor_high_false"),   # bank healthy — withdrawing = over-reaction
    ("true",  "rumor_high_true"),    # bank insolvent — withdrawing = correct
]


def _slug_models(arg: str | None):
    if not arg:
        return MODELS
    want = {s.strip() for s in arg.split(",")}
    return [m for m in MODELS if m[0] in want]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma-separated slugs (default: all)")
    ap.add_argument("--scenarios", help="comma-separated tags: false,true (default: both)")
    ap.add_argument("--runs", type=int, default=1, help="repeats per (model, scenario)")
    ap.add_argument("--list", nargs="?", const="", metavar="FILTER",
                    help="list current OpenRouter model ids (optionally filtered, e.g. --list gemini) and exit")
    args = ap.parse_args()

    if args.list is not None:
        _fetch_openrouter_models(args.list or None)
        return

    models = _slug_models(args.models)
    scen_tags = set(args.scenarios.split(",")) if args.scenarios else {"false", "true"}
    scenarios = [s for s in SCENARIOS if s[0] in scen_tags]

    import asyncio

    total_cost = 0.0
    print(f"Model comparison: {len(models)} models × {len(scenarios)} scenarios × {args.runs} run(s)\n")
    for slug, model_id, display in models:
        for scen_tag, base_id in scenarios:
            base = PRESET_BY_ID[base_id]
            for r in range(args.runs):
                scen = dataclasses.replace(base, scenario_id=f"modelcmp_{slug}_{scen_tag}")
                agents = make_all_agents()
                client = LLMClient()
                print(f"[{display} · {scen_tag}] run {r+1}/{args.runs} …", flush=True)
                try:
                    res = asyncio.run(run_scenario(
                        scen, agents, llm_client=client, runs_dir=RUNS_DIR,
                        verbose=False, model_override=model_id,
                    ))
                    m = res.metrics
                    fb = sum(
                        1 for a in res.to_dict()["agent_final_states"]
                        for d in a.get("decision_history", [])
                        if d.get("model_used") == "fallback"
                    )
                    total_cost += m.total_cost_usd
                    flag = "  [!] HIGH FALLBACK — model may not support tool-calling" if fb >= 6 else ""
                    print(
                        f"      withdrew(full+part)={m.attempted_exit_count}/{m.total_agents} "
                        f"· fully={m.withdrawn_count} · cascade={m.cascade_triggered} "
                        f"· fallback_decisions={fb} · ${m.total_cost_usd:.3f}{flag}",
                        flush=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"      FAILED: {exc}", flush=True)
    print(f"\nDone. Total cost ≈ ${total_cost:.2f}")
    print("Open the dashboard → Findings → 'Same personas, different brains' to see the ranking.")


if __name__ == "__main__":
    main()
