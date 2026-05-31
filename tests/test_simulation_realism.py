"""Focused checks for simulation realism invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.scenario import (
    AgentPopulationGroup,
    BankConfig,
    PaymentObligation,
    RumorConfig,
    Scenario,
)
from src.core.simulation import run_scenario
from src.decisions.llm_client import CallSummary, LLMCallResult
from src.personas.instances import make_margaret_chen, make_robert_petersen


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


class FakeHoldClient:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, **kwargs) -> LLMCallResult:
        self.calls += 1
        return LLMCallResult(
            tool_input={
                "reasoning": "The rumor seems overblown; I'll keep my deposit.",
                "action": "hold",
                "amount_fraction": None,
                "confidence": 0.7,
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
async def test_true_insolvency_crystallizes_real_loss_for_holders(tmp_path: Path):
    """An agent who holds through a genuinely insolvent bank (asset_recovery < 1
    + true rumor) must take a REAL principal loss, so the ledger and the
    IGNORED_REAL_WARNING tag agree."""
    agent = make_margaret_chen()
    scenario = Scenario(
        scenario_id="real_insolvency",
        name="Real insolvency",
        description="The bank really is insolvent and the holder eats the loss.",
        rumors=[
            RumorConfig(
                content="The bank is insolvent.",
                source="financial_news",
                credibility=0.9,
                target_bank_id="bank_a",
                is_true=True,
                propagation_latency_seconds=0.0,
            )
        ],
        banks=[
            BankConfig(
                bank_id="bank_a",
                name="Bank A",
                initial_reserve_ratio=0.35,
                asset_recovery_ratio=0.60,  # 60 cents on the dollar
            ),
            BankConfig(bank_id="bank_b", name="Bank B", initial_reserve_ratio=1.0),
        ],
        population=[
            AgentPopulationGroup("cautious_retiree", 1, "bank_a", (100_000, 100_000)),
        ],
        social_signal_visibility=0.0,
        max_simulation_time=10.0,
    )

    starting_deposit_a = agent.deposit_at_bank("bank_a")
    expected_loss = starting_deposit_a * (1 - 0.60)
    assert expected_loss > 0  # sanity: the agent actually holds at the failing bank

    result = await run_scenario(
        scenario, [agent], llm_client=FakeHoldClient(), runs_dir=None, verbose=False
    )

    final_agent = result.to_dict()["agent_final_states"][0]
    ledger = final_agent["outcome_ledger"]
    tags = ledger["outcome_tags"]

    assert "ignored_real_warning" in tags
    # Held through a 60%-recovery insolvency → 40% of the deposit is destroyed.
    assert ledger["total_realized_cost"] == pytest.approx(expected_loss, rel=1e-6)
    assert ledger["net_principal_change"] == pytest.approx(-expected_loss, rel=1e-6)
    # The agent HELD — no withdrawals. The insolvency haircut writes down deposits
    # but must NOT be counted as a withdrawal in the cascade metric.
    assert result.metrics.final_withdrawal_fraction == pytest.approx(0.0, abs=1e-6)
    assert result.metrics.cascade_triggered is False


@pytest.mark.asyncio
async def test_payment_contagion_executes_and_fails(tmp_path: Path):
    """A funded payment settles (payee's cash rises, payer's deposit falls);
    an underfunded payment fails and the payee is recorded as hit + re-triggered."""
    payer = make_margaret_chen()
    payer.agent_id = "payer"
    payer.portfolio = {"bank_a:deposit": 100_000.0}

    payee = make_robert_petersen()
    payee.agent_id = "payee"
    payee.portfolio = {"bank_b:deposit": 5_000.0}

    broke = make_margaret_chen()
    broke.agent_id = "broke"
    broke.portfolio = {"bank_a:deposit": 1_000.0}  # cannot cover a 5k obligation

    scenario = Scenario(
        scenario_id="payments",
        name="Payments",
        description="Payment contagion smoke test.",
        rumors=[],
        banks=[
            BankConfig(bank_id="bank_a", name="Bank A", initial_reserve_ratio=1.0),
            BankConfig(bank_id="bank_b", name="Bank B", initial_reserve_ratio=1.0),
        ],
        population=[],
        obligations=[
            PaymentObligation("ob1", "payer", "payee", 8_000.0, due_time=3.0,
                              kind="payroll", label="payroll"),
            PaymentObligation("ob2", "broke", "payee", 5_000.0, due_time=4.0,
                              kind="rent", label="rent"),
        ],
        social_signal_visibility=0.0,
        max_simulation_time=30.0,
    )

    result = await run_scenario(
        scenario, [payer, payee, broke], llm_client=FakeHoldClient(),
        runs_dir=None, verbose=False,
    )
    m = result.metrics

    assert m.obligations_total == 2
    assert m.payments_executed == 1
    assert m.payments_failed == 1
    assert m.agents_hit_by_failed_payment == 1
    assert m.payment_failure_triggered_runs >= 1
    assert m.time_to_first_payment_failure is not None

    states = {a["agent_id"]: a for a in result.to_dict()["agent_final_states"]}
    # Payer settled 8k from their deposit.
    assert states["payer"]["portfolio"].get("bank_a:deposit", 0) == pytest.approx(92_000.0)
    # Payee received the 8k payroll as cash (the 5k rent never arrived).
    assert states["payee"]["portfolio"].get("cash:available", 0) == pytest.approx(8_000.0)


class FakeFailingClient:
    """Simulates an LLM call that fails every time (e.g. malformed tool output
    surviving all retries, or a bad model id)."""

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, **kwargs) -> LLMCallResult:
        self.calls += 1
        raise RuntimeError("simulated LLM failure")

    def summary(self) -> CallSummary:
        return CallSummary(total_calls=self.calls, by_model={})


@pytest.mark.asyncio
async def test_failed_llm_call_degrades_to_hold_without_aborting_run(tmp_path: Path):
    """A single failed decision must not crash the whole simulation mid-demo."""
    agent = make_margaret_chen()
    scenario = Scenario(
        scenario_id="llm_failure",
        name="LLM failure",
        description="The decision call always raises.",
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
            BankConfig(bank_id="bank_a", name="Bank A", initial_reserve_ratio=1.0),
            BankConfig(bank_id="bank_b", name="Bank B", initial_reserve_ratio=1.0),
        ],
        population=[
            AgentPopulationGroup("cautious_retiree", 1, "bank_a", (50_000, 50_000)),
        ],
        social_signal_visibility=0.0,
        max_simulation_time=10.0,
    )

    # Must complete without raising despite every decision call failing.
    result = await run_scenario(
        scenario,
        [agent],
        llm_client=FakeFailingClient(),
        runs_dir=None,
        verbose=False,
    )

    final_agent = result.to_dict()["agent_final_states"][0]
    history = final_agent["decision_history"]
    assert history, "a fallback decision should still be recorded for the audit trail"
    assert history[-1]["action"] == "hold"
    assert history[-1]["model_used"] == "fallback"
    # The agent held, so its deposit is untouched.
    assert final_agent["portfolio"]["bank_a:deposit"] == 50_000.0


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
