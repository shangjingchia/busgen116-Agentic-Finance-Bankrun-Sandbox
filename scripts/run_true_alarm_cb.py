"""
Run Central Bank intervention on the true-alarm scenario (bank actually insolvent).

Completes the 2x2 needed for the CB finding:

  False alarm (bank fine):    AI CB chose do_nothing (correct)  | Rule CB fired guarantee (wrong)
  True alarm  (bank failing): AI CB chose ???                   | Rule CB fired guarantee (???)

Three runs:
  rumor_high_true          — baseline, no CB
  rumor_high_true_llm_cb   — AI Central Bank intervenes
  rumor_high_true_rule_cb  — Rule-based CB fires same threshold

Usage:
    python scripts/run_true_alarm_cb.py
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

    _, base = PRESET_BY_ID["rumor_high_true"]
    s = copy.deepcopy(base)
    s.scenario_id = scenario_id
    s.name = label
    s.central_bank = cb

    agents = make_all_agents()
    client = LLMClient()

    cb_tag = f"  [CB: {cb.policy_type}  threshold={cb.trigger_threshold:.0%}]" if cb else "  [no CB]"
    print(f"  run   {scenario_id}{cb_tag}", flush=True)

    result = await run_scenario(s, agents, llm_client=client, runs_dir=RUNS_DIR, verbose=True)
    m = result.metrics
    cb_fired = m.cb_triggered_at is not None
    print(
        f"         exits={m.withdrawn_count}/12  "
        f"deposits_withdrawn={m.final_withdrawal_fraction:.1%}  "
        f"CB fired: {'YES at T+{:.1f}s  action={}'.format(m.cb_triggered_at, m.cb_action) if cb_fired else 'no'}"
    )


def main() -> None:
    RUNS_DIR.mkdir(exist_ok=True)

    runs = [
        ("rumor_high_true",         "High-Credibility Rumor — Bank Insolvent (no CB)",          None),
        ("rumor_high_true_llm_cb",  "High-Credibility Rumor — Bank Insolvent + AI CB",          _CB_LLM),
        ("rumor_high_true_rule_cb", "High-Credibility Rumor — Bank Insolvent + Rule-Based CB",  _CB_RULE),
    ]

    print(f"\nTrue-alarm CB comparison — {len(runs)} runs (bank actually insolvent)\n")
    for sid, label, cb in runs:
        asyncio.run(run_one(sid, label, cb))

    print(
        "\nDone.\n"
        "Key question: did the AI CB correctly intervene on the insolvent bank?\n"
        "Compare cb_action in rumor_high_true_llm_cb vs. rumor_high_true_rule_cb.\n"
        "Then update findings_view.py CB finding with the 2x2 narrative."
    )


if __name__ == "__main__":
    main()
