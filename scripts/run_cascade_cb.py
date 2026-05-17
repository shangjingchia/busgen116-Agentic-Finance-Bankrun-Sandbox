"""
Run Central Bank intervention on the 45%-credibility cascade scenario.

This is the meaningful CB comparison: at 45% credibility the false-alarm
cascade actually fires (10/12 agents withdraw in ~7 seconds at AI speed).
The three runs show what happens with no CB, rule-based CB, and AI CB.

  sweep_false_045          — baseline cascade, no intervention
  sweep_false_045_llm_cb   — AI Central Bank intervenes
  sweep_false_045_rule_cb  — Rule-based CB fires same threshold

Usage:
    python scripts/run_cascade_cb.py
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

from src.core.scenario import CentralBankConfig, ScenarioSpeed
from src.core.simulation import run_scenario
from src.decisions.llm_client import LLMClient
from src.personas.instances import make_all_agents
from src.scenarios.presets import PRESET_BY_ID

RUNS_DIR = Path(__file__).parent.parent / "runs"
CREDIBILITY = 0.45
SEED = 42

_CB_LLM = CentralBankConfig(
    policy_type="llm",
    trigger_threshold=0.25,
    model="anthropic/claude-sonnet-4.5",
)

_CB_RULE = CentralBankConfig(
    policy_type="rule_based",
    trigger_threshold=0.25,
    rule_action="announce_guarantee",
    rule_liquidity_fraction=0.5,
)


def _already_run(scenario_id: str) -> bool:
    for p in RUNS_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("scenario_id") == scenario_id and d.get("speed") == "ai":
                return True
        except Exception:
            continue
    return False


async def run_one(scenario_id: str, label: str, cb: CentralBankConfig | None) -> None:
    if _already_run(scenario_id):
        print(f"  skip  {scenario_id} — already exists")
        return

    _, base = PRESET_BY_ID["rumor_moderate_false"]
    s = copy.deepcopy(base)
    s.scenario_id = scenario_id
    s.name = label
    s.description = (
        f"Credibility sweep at {CREDIBILITY:.0%} — false bank, AI speed. "
        + (
            "No Central Bank intervention."
            if cb is None
            else f"Central Bank ({cb.policy_type}) triggers at {cb.trigger_threshold:.0%} deposit-fraction withdrawn."
        )
    )
    s.rumors[0].credibility = CREDIBILITY
    s.speed = ScenarioSpeed.AI_SPEED
    s.social_signal_visibility = 1.0
    s.seed = SEED
    s.central_bank = cb

    agents = make_all_agents()
    client = LLMClient()

    cb_tag = f"  [CB: {cb.policy_type}  threshold={cb.trigger_threshold:.0%}]" if cb else "  [no CB]"
    print(f"  run   {scenario_id}{cb_tag}", flush=True)

    result = await run_scenario(s, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True)
    m = result.metrics
    cb_fired = m.cb_triggered_at is not None
    print(f"         CB fired: {'YES at T+{:.1f}s'.format(m.cb_triggered_at) if cb_fired else 'no'}")


def main() -> None:
    RUNS_DIR.mkdir(exist_ok=True)

    runs = [
        ("sweep_false_045",         f"Credibility Sweep — {CREDIBILITY:.0%} false bank (no CB)", None),
        ("sweep_false_045_llm_cb",  f"Credibility Sweep — {CREDIBILITY:.0%} false bank + AI CB", _CB_LLM),
        ("sweep_false_045_rule_cb", f"Credibility Sweep — {CREDIBILITY:.0%} false bank + Rule CB", _CB_RULE),
    ]

    print(f"\nCascade CB comparison — {len(runs)} runs at {CREDIBILITY:.0%} credibility\n")
    for sid, label, cb in runs:
        asyncio.run(run_one(sid, label, cb))

    print("\nDone. Load runs from Configure -> Load, or view CB comparison in Findings.")


if __name__ == "__main__":
    main()
