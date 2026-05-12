"""
Day 1-2 vertical slice.

Runs one agent (Margaret Chen, cautious retiree) through one decision in
response to one rumor event. Writes a full audit trail to runs/<run_id>/ and
prints the model's reasoning + a cost summary.

Usage:
    # 1) Copy .env.example to .env and set ANTHROPIC_API_KEY
    # 2) From the repo root:
    python scripts/vertical_slice.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path

# Force UTF-8 on Windows stdout so persona em-dashes render correctly.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        pass

# Make `src.*` importable when running this script directly from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core.event import (
    AgentActed,
    AgentDecisionTriggered,
    AgentObserved,
    EventType,
    RumorPublished,
)
from src.decisions.decision import DecisionContext, make_decision
from src.decisions.llm_client import LLMClient
from src.personas.instances import make_margaret_chen


def _load_dotenv() -> None:
    """Load .env if python-dotenv is available; otherwise rely on the OS env."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    load_dotenv()


def _new_run_id() -> str:
    return "run_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_run_dir(runs_root: Path, run_id: str) -> Path:
    run_dir = runs_root / run_id
    (run_dir / "decisions").mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Day 1-2 vertical slice")
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path(os.environ.get("AGENT_BANKRUN_RUNS_DIR", "runs")),
        help="Directory to write the run audit trail under.",
    )
    parser.add_argument(
        "--rumor-credibility",
        type=float,
        default=0.7,
        help="Credibility of the rumor (0-1). Default: 0.7",
    )
    parser.add_argument(
        "--rumor-source",
        default="financial_news_outlet",
        help="Source of the rumor (e.g. 'twitter', 'financial_news_outlet').",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    _load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "ERROR: OPENROUTER_API_KEY not set. Copy .env.example to .env and fill it in,\n"
            "       or export the key in your shell.",
            file=sys.stderr,
        )
        return 2

    # ------------------------------------------------------------------
    # 1. Build the agent
    # ------------------------------------------------------------------
    agent = make_margaret_chen()

    # ------------------------------------------------------------------
    # 2. Construct the rumor + observation events
    # ------------------------------------------------------------------
    sim_t0 = 0.0
    observation_latency = 5.0  # she sees the rumor 5 seconds after it's published
    decision_time = sim_t0 + observation_latency

    rumor = RumorPublished(
        event_type=EventType.RUMOR_PUBLISHED,
        timestamp=sim_t0,
        content=(
            "Reports from a regional financial news outlet indicate that Bank A's "
            "third-quarter call report shows reserves dropping below regulatory "
            "minimums. The bank has not yet commented. Two analysts have flagged "
            "concerns about Bank A's solvency."
        ),
        source=args.rumor_source,
        credibility=args.rumor_credibility,
        bank_id="bank_a",
        target_agent_ids=[],  # broadcast
    )

    observation = AgentObserved(
        event_type=EventType.AGENT_OBSERVED,
        timestamp=decision_time,
        agent_id=agent.agent_id,
        observed_event_id=rumor.event_id,
        observation_latency=observation_latency,
    )

    decision_triggered = AgentDecisionTriggered(
        event_type=EventType.AGENT_DECISION_TRIGGERED,
        timestamp=decision_time,
        agent_id=agent.agent_id,
        trigger_reason="rumor_observed",
        triggering_event_id=rumor.event_id,
    )

    observation_text = (
        f"Rumor on {rumor.source} (credibility {rumor.credibility:.2f}): {rumor.content}"
    )
    context = DecisionContext(
        bank_id_in_focus="bank_a",
        observations=[observation_text],
        sim_time_seconds=decision_time,
        trigger_reason="rumor_observed",
    )

    # ------------------------------------------------------------------
    # 3. Make the decision
    # ------------------------------------------------------------------
    llm = LLMClient()
    record = make_decision(agent, context, llm_client=llm)

    acted = AgentActed(
        event_type=EventType.AGENT_ACTED,
        timestamp=decision_time,
        agent_id=agent.agent_id,
        action=record.action,
        bank_id=record.bank_id,
        amount_fraction=record.amount_fraction,
        reasoning=record.reasoning,
        confidence=record.confidence,
        decision_record_id=record.decision_id,
        model_used=record.model_used,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        cost_usd=record.cost_usd,
    )

    # ------------------------------------------------------------------
    # 4. Persist the audit trail
    # ------------------------------------------------------------------
    run_id = _new_run_id()
    run_dir = _ensure_run_dir(args.runs_dir, run_id)

    metadata = {
        "run_id": run_id,
        "kind": "vertical_slice_day1",
        "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "agent_count": 1,
        "agent_ids": [agent.agent_id],
        "rumor": {
            "content": rumor.content,
            "source": rumor.source,
            "credibility": rumor.credibility,
            "bank_id": rumor.bank_id,
        },
    }
    _write_json(run_dir / "run_metadata.json", metadata)

    events = [
        rumor.to_dict(),
        observation.to_dict(),
        decision_triggered.to_dict(),
        acted.to_dict(),
    ]
    _write_json(run_dir / "events.json", events)

    decision_path = run_dir / "decisions" / agent.agent_id / f"{record.decision_id}.json"
    _write_json(decision_path, record.to_dict())

    _write_json(run_dir / "agent_state.json", agent.to_dict())

    cost_summary_text = llm.format_cost_summary()
    (run_dir / "cost_summary.txt").write_text(cost_summary_text, encoding="utf-8")

    # ------------------------------------------------------------------
    # 5. Print the human-readable view
    # ------------------------------------------------------------------
    print()
    print("=" * 72)
    print(f"Run: {run_id}")
    print(f"Agent: {agent.persona.name} ({agent.persona.archetype}, age {agent.persona.age})")
    print(f"Portfolio at decision time: ${agent.total_wealth():,.0f}")
    print("=" * 72)
    print()
    print(f"Rumor (credibility {rumor.credibility:.2f}, source: {rumor.source}):")
    print(f"  {rumor.content}")
    print()
    print(f"Decision (model: {record.model_used}, confidence: {record.confidence:.2f}):")
    print(f"  Action: {record.action}", end="")
    if record.action in ("partial_withdraw", "increase_deposit"):
        print(f"  (fraction: {record.amount_fraction:.2f})")
    else:
        print()
    print()
    print(f"Reasoning:")
    print()
    for line in _wrap(record.reasoning, width=70, indent="  "):
        print(line)
    print()
    print("-" * 72)
    print(cost_summary_text)
    print("-" * 72)
    print(f"Audit written to: {run_dir}")
    print()

    return 0


def _wrap(text: str, *, width: int, indent: str) -> list[str]:
    import textwrap

    out: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph.strip():
            out.append("")
            continue
        out.extend(textwrap.wrap(paragraph, width=width, initial_indent=indent, subsequent_indent=indent))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
