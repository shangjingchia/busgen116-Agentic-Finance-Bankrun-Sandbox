"""
Day-3 live comparison: run all four canonical personas through the same rumor
and print their decisions side by side.

This is the "they should sound like four different people" check, executed
against real LLM calls. Costs ~$0.04-0.05 (four Sonnet calls — each persona's
first decision, so the strategy router picks Sonnet).

Usage:
    .venv\\Scripts\\python scripts\\four_personas_one_rumor.py
    .venv\\Scripts\\python scripts\\four_personas_one_rumor.py --rumor-credibility 0.4
    .venv\\Scripts\\python scripts\\four_personas_one_rumor.py --model anthropic/claude-haiku-4.5
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

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
from src.personas.instances import make_all_canonical_agents


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    load_dotenv()


def _new_run_id() -> str:
    return "run_day3_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _wrap(text: str, *, width: int, indent: str) -> list[str]:
    import textwrap
    out: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph.strip():
            out.append("")
            continue
        out.extend(textwrap.wrap(paragraph, width=width,
                                 initial_indent=indent, subsequent_indent=indent))
    return out


async def _decide_one(agent, context, *, llm_client, force_strategic):
    """Run a single agent's decision in a thread so the LLM client (sync) doesn't block the loop."""
    return await asyncio.to_thread(
        make_decision,
        agent,
        context,
        llm_client=llm_client,
        force_strategic=force_strategic,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all four canonical personas through one rumor.")
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path(os.environ.get("AGENT_BANKRUN_RUNS_DIR", "runs")),
    )
    parser.add_argument("--rumor-credibility", type=float, default=0.7)
    parser.add_argument("--rumor-source", default="financial_news_outlet")
    parser.add_argument(
        "--model",
        default=None,
        help="Override and force a specific model for all four calls.",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run one at a time instead of fanning out in parallel.",
    )
    parser.add_argument("--log-level", default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    _load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set.", file=sys.stderr)
        return 2

    agents = make_all_canonical_agents()

    # Same rumor for all — this is the comparison point.
    sim_t0 = 0.0
    observation_latency = 5.0
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
        target_agent_ids=[],
    )
    observation_text = (
        f"Rumor on {rumor.source} (credibility {rumor.credibility:.2f}): {rumor.content}"
    )

    llm = LLMClient()

    # Build per-agent contexts
    contexts = []
    for agent in agents:
        contexts.append((
            agent,
            DecisionContext(
                bank_id_in_focus="bank_a",
                observations=[observation_text],
                sim_time_seconds=decision_time,
                trigger_reason="rumor_observed",
            ),
        ))

    # Run all four. With --sequential we keep timing/cost predictable; otherwise
    # we fan out via asyncio (real parallelism since each call goes to a thread).
    print(f"Running {len(agents)} agents through the same rumor "
          f"({'sequentially' if args.sequential else 'in parallel'})...")

    if args.sequential:
        records = []
        for agent, context in contexts:
            print(f"  [{agent.persona.archetype}] {agent.persona.name}...")
            r = make_decision(
                agent, context, llm_client=llm,
                force_strategic=True,  # Sonnet for all, parity across agents
            )
            records.append((agent, r))
    else:
        async def runner():
            tasks = [
                _decide_one(agent, context, llm_client=llm, force_strategic=True)
                for agent, context in contexts
            ]
            results = await asyncio.gather(*tasks)
            return list(zip([a for a, _ in contexts], results))
        records = asyncio.run(runner())

    # ------------------------------------------------------------------
    # Persist audit trail
    # ------------------------------------------------------------------
    run_id = _new_run_id()
    run_dir = args.runs_dir / run_id
    (run_dir / "decisions").mkdir(parents=True, exist_ok=True)

    metadata = {
        "run_id": run_id,
        "kind": "day3_four_personas_one_rumor",
        "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "agent_count": len(agents),
        "agent_ids": [a.agent_id for a in agents],
        "rumor": {
            "content": rumor.content,
            "source": rumor.source,
            "credibility": rumor.credibility,
            "bank_id": rumor.bank_id,
        },
        "model_override": args.model,
        "execution_mode": "sequential" if args.sequential else "parallel",
    }
    _write_json(run_dir / "run_metadata.json", metadata)

    events: list[dict] = [rumor.to_dict()]
    for agent, record in records:
        events.append(AgentObserved(
            event_type=EventType.AGENT_OBSERVED,
            timestamp=decision_time,
            agent_id=agent.agent_id,
            observed_event_id=rumor.event_id,
            observation_latency=observation_latency,
        ).to_dict())
        events.append(AgentDecisionTriggered(
            event_type=EventType.AGENT_DECISION_TRIGGERED,
            timestamp=decision_time,
            agent_id=agent.agent_id,
            trigger_reason="rumor_observed",
            triggering_event_id=rumor.event_id,
        ).to_dict())
        events.append(AgentActed(
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
        ).to_dict())
        _write_json(
            run_dir / "decisions" / agent.agent_id / f"{record.decision_id}.json",
            record.to_dict(),
        )

    _write_json(run_dir / "events.json", events)
    (run_dir / "cost_summary.txt").write_text(llm.format_cost_summary(), encoding="utf-8")

    # ------------------------------------------------------------------
    # Print side-by-side summary
    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(f"Run: {run_id}")
    print(f"Rumor (credibility {rumor.credibility:.2f}, source {rumor.source}):")
    for line in _wrap(rumor.content, width=72, indent="  "):
        print(line)
    print("=" * 78)

    for agent, record in records:
        amt = (f" (fraction: {record.amount_fraction:.2f})"
               if record.action in ("partial_withdraw", "increase_deposit")
               else "")
        print()
        print(f"### {agent.persona.archetype} — {agent.persona.name}, "
              f"age {agent.persona.age}, ${agent.total_wealth():,.0f} total")
        print(f"   action: {record.action}{amt}")
        print(f"   confidence: {record.confidence:.2f}   model: {record.model_used}   "
              f"cost: ${record.cost_usd:.4f}")
        print()
        print("   reasoning:")
        for line in _wrap(record.reasoning, width=72, indent="     "):
            print(line)

    print()
    print("-" * 78)
    print(llm.format_cost_summary())
    print("-" * 78)
    print(f"Audit written to: {run_dir}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
