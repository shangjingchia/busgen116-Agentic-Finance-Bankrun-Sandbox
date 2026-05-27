"""Focused checks for simulation realism invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.scenario import AgentPopulationGroup, BankConfig, RumorConfig, Scenario
from src.core.simulation import run_scenario
from src.decisions.llm_client import CallSummary, LLMCallResult
from src.personas.instances import make_margaret_chen


class FakeFullWithdrawClient:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, **kwargs) -> LLMCallResult:
        self.calls += 1
        return LLMCallResult(
            tool_input={
                "reasoning": "The downside of waiting is worse than the withdrawal fee.",
                "action": "full_withdraw",
                "amount_fraction": 1.0,
                "confidence": 0.8,
            },
            model="fake-model",
            prompt_tokens=0,
            completion_tokens=0,
            cached_prompt_tokens=0,
            cost_usd=0.0,
            cost_source="test",
            cache_hit=False,
            raw_response={},
        )

    def summary(self) -> CallSummary:
        return CallSummary(total_calls=self.calls, by_model={"fake-model": self.calls})


@pytest.mark.asyncio
async def test_withdrawal_credits_cash_and_preserves_fee_accounting(tmp_path: Path):
    agent = make_margaret_chen()
    scenario = Scenario(
        scenario_id="cash_accounting",
        name="Cash accounting",
        description="One agent exits a fully liquid bank.",
        rumors=[
            RumorConfig(
                content="A credible alert says the bank may suspend withdrawals.",
                source="financial_news",
                credibility=0.8,
                target_bank_id="bank_a",
                propagation_latency_seconds=0.0,
            )
        ],
        banks=[
            BankConfig(
                bank_id="bank_a",
                name="Bank A",
                initial_reserve_ratio=1.0,
                early_withdrawal_fee_rate=0.03,
            ),
            BankConfig(bank_id="bank_b", name="Bank B", initial_reserve_ratio=1.0),
        ],
        population=[
            AgentPopulationGroup("cautious_retiree", 1, "bank_a", (50_000, 50_000)),
        ],
        social_signal_visibility=0.0,
        max_simulation_time=10.0,
    )

    result = await run_scenario(
        scenario,
        [agent],
        llm_client=FakeFullWithdrawClient(),
        runs_dir=None,
        verbose=False,
    )

    final_agent = result.to_dict()["agent_final_states"][0]
    portfolio = final_agent["portfolio"]
    ledger = final_agent["outcome_ledger"]

    assert portfolio["bank_a:deposit"] == 0.0
    assert portfolio["cash:available"] == 48_500.0
    assert ledger["principal_current_value"] == 60_500.0
    assert ledger["total_realized_cost"] == 1_500.0
    assert result.metrics.final_withdrawal_fraction == 1.0
    assert result.metrics.attempted_exit_count == 1
    assert result.metrics.paid_out_count == 1
    # AI speed now adds a small jitter (0.5–3s) so time is non-zero but well within max
    assert result.metrics.time_to_50pct_deposits_paid is not None
    assert result.metrics.time_to_50pct_deposits_paid < 10.0
