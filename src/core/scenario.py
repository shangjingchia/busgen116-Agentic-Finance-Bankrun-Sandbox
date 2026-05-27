"""
Scenario: the configuration object that drives a simulation run.

Everything that defines a simulation lives here — banks, agent population mix,
rumors, speed setting, social signal visibility. The simulation engine takes a
Scenario and produces a run. This is the v2 anchor: the natural-language
scenario translator will produce Scenario objects of this same shape.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, List, Optional, Tuple

from src.information.environment import InformationSignal


class ScenarioSpeed(str, Enum):
    AI_SPEED = "ai"        # no artificial latency between observation and decision
    HUMAN_SPEED = "human"  # 90-second decision delay injected
    CUSTOM = "custom"


@dataclass
class RumorConfig:
    content: str
    source: str
    credibility: float                    # 0-1
    target_bank_id: str
    publish_at_time: float = 0.0
    is_true: bool = False                 # ground truth, revealed at simulation end
    propagation_latency_seconds: float = 5.0  # mean per-agent observation latency


@dataclass
class BankConfig:
    bank_id: str
    name: str
    initial_reserve_ratio: float          # ratio of reserves to total deposits at t=0
    early_withdrawal_fee_rate: float = 0.03
    withdrawal_processing_capacity: float = 1_000_000.0
    distress_threshold: float = 0.20
    suspension_threshold: float = 0.05


@dataclass
class AgentPopulationGroup:
    """One row of the population mix: N agents of this archetype with these deposits."""

    archetype: str
    count: int
    primary_bank_id: str
    primary_deposit_range: Tuple[float, float]
    secondary_bank_id: Optional[str] = None
    secondary_deposit_range: Optional[Tuple[float, float]] = None


@dataclass
class CentralBankConfig:
    """Configuration for the Central Bank intervention agent.

    policy_type="llm"        — makes a real LLM call to choose the intervention.
    policy_type="rule_based" — fires a pre-programmed action at the trigger threshold.
    """
    policy_type: str = "llm"                          # "llm" | "rule_based"
    trigger_threshold: float = 0.25                   # fraction of agents withdrawn before CB acts
    model: str = "anthropic/claude-sonnet-4.5"        # model for LLM CB
    rule_action: str = "announce_guarantee"           # fixed action for rule_based CB
    rule_liquidity_fraction: float = 0.5              # for rule_based inject_liquidity


@dataclass
class Scenario:
    scenario_id: str
    name: str
    description: str
    banks: List[BankConfig]
    population: List[AgentPopulationGroup]
    # Primary signal stream — heterogeneous alarm/reassurance signals per archetype
    signals: List[InformationSignal] = field(default_factory=list)
    # Legacy shim — old runs and presets can still provide rumors; they are converted
    # to InformationSignal objects with alarm_level=0.8 in the simulation engine.
    rumors: List[RumorConfig] = field(default_factory=list)
    speed: ScenarioSpeed = ScenarioSpeed.AI_SPEED
    human_speed_decision_delay_seconds: float = 90.0
    # Per-archetype deliberation multiplier applied on top of persona.deliberation_seconds
    human_speed_deliberation_multiplier: float = 1.0
    social_signal_visibility: float = 1.0   # fraction of withdrawals visible on social feed
    seed: int = 42
    max_simulation_time: float = 3600.0     # 1 simulated hour
    central_bank: Optional["CentralBankConfig"] = None  # None = no CB intervention

    # v2 hook: scenarios produced by the natural-language translator carry their source.
    source_natural_language: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["speed"] = self.speed.value
        # InformationSignal is not a plain dict in asdict output; convert manually
        d["signals"] = [
            {k: v for k, v in s.__dict__.items()} for s in self.signals
        ]
        return d
