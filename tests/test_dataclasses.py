"""Smoke tests for the core dataclasses: JSON round-trip and basic invariants."""

from __future__ import annotations

import json

from src.core.agent import (
    Agent,
    AgentState,
    CostCategory,
    DecisionRecord,
    OutcomeLedger,
    Severity,
)
from src.core.bank import Bank, BankState
from src.core.event import EventType, RumorPublished
from src.core.scenario import (
    AgentPopulationGroup,
    BankConfig,
    RumorConfig,
    Scenario,
    ScenarioSpeed,
)
from src.personas.archetypes import (
    ARCHETYPE_CAUTIOUS_RETIREE,
    cautious_retiree_cost_function,
    make_cautious_retiree,
)
from src.personas.instances import make_margaret_chen


def test_persona_serializes_to_json():
    persona = make_cautious_retiree(
        name="Test Retiree",
        age=68,
        income_annual=30_000,
        dependents=0,
        background_narrative="A test character.",
    )
    payload = persona.to_dict()
    # Round-trip via JSON
    serialized = json.dumps(payload)
    loaded = json.loads(serialized)

    assert loaded["archetype"] == ARCHETYPE_CAUTIOUS_RETIREE
    assert loaded["name"] == "Test Retiree"
    assert isinstance(loaded["cost_function"], list)
    # All seven cost categories represented
    categories = {item["category"] for item in loaded["cost_function"]}
    assert categories == {c.value for c in CostCategory}


def test_cost_function_severities_are_valid():
    cf = cautious_retiree_cost_function()
    valid_sevs = {s.value for s in Severity}
    for item in cf:
        assert item.severity.value in valid_sevs


def test_agent_total_wealth_and_deposit_at_bank():
    agent = make_margaret_chen()
    assert agent.total_wealth() == 62_000.0
    assert agent.deposit_at_bank("bank_a") == 50_000.0
    assert agent.deposit_at_bank("bank_b") == 12_000.0


def test_agent_serializes_to_json_with_outcome_ledger():
    agent = make_margaret_chen()
    payload = agent.to_dict()
    serialized = json.dumps(payload)
    loaded = json.loads(serialized)
    assert loaded["state"] == AgentState.ACTIVE.value
    assert loaded["outcome_ledger"]["principal_starting_value"] == 62_000.0
    assert loaded["outcome_ledger"]["net_principal_change"] == 0.0


def test_bank_processes_withdrawal_with_fee():
    bank = Bank(
        bank_id="bank_a",
        name="First Bank",
        deposits={"a1": 50_000.0},
        reserves=20_000.0,
        reserve_ratio_target=0.30,
        withdrawal_processing_capacity=1_000_000.0,
    )
    result = bank.process_withdrawal("a1", 10_000.0)
    assert result.amount_paid_out == 9_700.0  # 10k - 3% fee
    assert result.fee_paid == 300.0
    assert bank.deposits["a1"] == 40_000.0
    assert not result.was_queued


def test_bank_suspends_when_reserves_exhausted():
    bank = Bank(
        bank_id="bank_a",
        name="First Bank",
        deposits={"a1": 100_000.0},
        reserves=1_000.0,
        reserve_ratio_target=0.30,
        withdrawal_processing_capacity=1_000_000.0,
        suspension_threshold=0.05,
    )
    bank._recompute_state()
    assert bank.state == BankState.SUSPENDED


def test_rumor_published_event_serializes():
    e = RumorPublished(
        event_type=EventType.RUMOR_PUBLISHED,
        timestamp=0.0,
        content="Something is wrong with Bank A.",
        source="twitter",
        credibility=0.4,
        bank_id="bank_a",
    )
    payload = e.to_dict()
    json.dumps(payload)  # must not raise
    assert payload["event_type"] == "rumor_published"


def test_scenario_serializes():
    scenario = Scenario(
        scenario_id="rumor_moderate",
        name="Moderate rumor against Bank A",
        description="One rumor of medium credibility.",
        rumors=[
            RumorConfig(
                content="...",
                source="financial_news_outlet",
                credibility=0.6,
                target_bank_id="bank_a",
            )
        ],
        banks=[
            BankConfig(bank_id="bank_a", name="Bank A", initial_reserve_ratio=0.30),
            BankConfig(bank_id="bank_b", name="Bank B", initial_reserve_ratio=0.40),
        ],
        population=[
            AgentPopulationGroup(
                archetype=ARCHETYPE_CAUTIOUS_RETIREE,
                count=3,
                primary_bank_id="bank_a",
                primary_deposit_range=(40_000.0, 60_000.0),
            ),
        ],
        speed=ScenarioSpeed.AI_SPEED,
    )
    payload = scenario.to_dict()
    json.dumps(payload)
    assert payload["speed"] == "ai"


def test_decision_record_round_trips():
    record = DecisionRecord(
        decision_id="d1",
        agent_id="a1",
        timestamp=5.0,
        trigger_reason="rumor_observed",
        action="partial_withdraw",
        bank_id="bank_a",
        amount_fraction=0.8,
        reasoning="I cannot afford to be wrong about my retirement principal.",
        confidence=0.7,
        model_used="claude-haiku-4-5-20251001",
        prompt_tokens=600,
        completion_tokens=200,
        cost_usd=0.0016,
        cache_hit=False,
        system_prompt="...",
        user_message="...",
        raw_tool_input={"action": "partial_withdraw"},
        portfolio_snapshot={"bank_a:deposit": 50_000.0},
        observation_summary=["Rumor observed."],
    )
    payload = record.to_dict()
    serialized = json.dumps(payload)
    loaded = json.loads(serialized)
    assert loaded["action"] == "partial_withdraw"
    assert loaded["amount_fraction"] == 0.8
