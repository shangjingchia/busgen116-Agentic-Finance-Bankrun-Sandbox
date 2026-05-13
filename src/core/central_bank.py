"""Central Bank intervention agent.

Two policy types share the same interface:
  "llm"        — makes a real LLM call (Sonnet) to choose intervention in context.
  "rule_based" — fires a pre-programmed action when the cascade threshold is crossed,
                 with no reasoning, representing a regulatory body that has not yet
                 adopted AI-speed decision-making.

The three available interventions are:
  do_nothing         — monitor only; no action taken.
  announce_guarantee — issue a public guarantee covering all deposits at the target
                       bank; injected into agent feeds, may stop further withdrawals.
  inject_liquidity   — transfer emergency reserves directly into the bank; improves
                       the reserve ratio immediately but does not send a public signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.core.scenario import CentralBankConfig
from src.decisions.llm_client import DEFAULT_SONNET_MODEL, LLMClient


# ---------------------------------------------------------------------------
# CB policy tool schema (OpenAI function-tool shape)
# ---------------------------------------------------------------------------

CB_POLICY_TOOL_NAME = "record_cb_policy_decision"

CB_POLICY_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": CB_POLICY_TOOL_NAME,
        "description": (
            "Record your central bank policy decision after reasoning through the "
            "cascade dynamics. Reason analytically — weigh the cost of intervention "
            "(moral hazard, credibility cost) against the cost of inaction (cascade "
            "continuation, bank suspension, depositor losses). Commit to one action."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": (
                        "Your institutional analysis (4-6 sentences). "
                        "Reference the cascade fraction, reserve ratio, and the "
                        "asymmetry between acting too early (moral hazard) and too "
                        "late (irreversible cascade). Institutional voice — measured, "
                        "analytical, citing systemic risk."
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["do_nothing", "announce_guarantee", "inject_liquidity"],
                    "description": (
                        "do_nothing: monitor only, no intervention. "
                        "announce_guarantee: issue a public guarantee covering ALL "
                        "deposits at the target bank — removes the incentive to run. "
                        "inject_liquidity: transfer emergency reserves to the bank — "
                        "improves the reserve ratio without a public announcement."
                    ),
                },
                "announcement_text": {
                    "type": "string",
                    "description": (
                        "For announce_guarantee: the exact text of the official "
                        "announcement depositors will see. 1-2 sentences, clear and "
                        "authoritative. For other actions: empty string."
                    ),
                },
                "liquidity_fraction": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": (
                        "For inject_liquidity: fraction of Bank A's initial reserves "
                        "to inject (e.g. 0.5 = inject 50% of initial reserves). "
                        "For other actions: 0.0."
                    ),
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Your confidence in this decision (0.0–1.0).",
                },
            },
            "required": [
                "reasoning", "action",
                "announcement_text", "liquidity_fraction", "confidence",
            ],
        },
    },
}


def _validate_cb_tool_input(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    required = {"reasoning", "action", "announcement_text", "liquidity_fraction", "confidence"}
    missing = required - set(tool_input.keys())
    if missing:
        raise ValueError(f"CB tool input missing fields: {missing}")
    action = tool_input["action"]
    if action not in {"do_nothing", "announce_guarantee", "inject_liquidity"}:
        raise ValueError(f"Unknown CB action: {action!r}")
    lf = float(tool_input.get("liquidity_fraction", 0.0))
    if not (0.0 <= lf <= 1.0):
        raise ValueError(f"liquidity_fraction out of range: {lf}")
    tool_input["liquidity_fraction"] = lf
    conf = float(tool_input.get("confidence", 0.5))
    if not (0.0 <= conf <= 1.0):
        raise ValueError(f"confidence out of range: {conf}")
    tool_input["confidence"] = conf
    return tool_input


# ---------------------------------------------------------------------------
# CB system and user prompts
# ---------------------------------------------------------------------------

_CB_SYSTEM_PROMPT = """\
You are the Central Bank Emergency Response System, monitoring real-time financial stability.

Your mandate: prevent unnecessary cascading bank failures. You do NOT intervene to protect \
individual depositors from rational losses — only to stop irrational or self-fulfilling panics \
from damaging solvent institutions.

Available interventions:
- do_nothing: appropriate when the cascade is small, self-limiting, or the bank is genuinely \
insolvent (intervention would only delay inevitable failure and create moral hazard).
- announce_guarantee: issue an official public guarantee that ALL deposits at the bank are fully \
covered. This is your most powerful stabilisation tool — it removes the incentive to run from a \
solvent bank. Use only when you believe the panic is irrational or disproportionate to actual risk.
- inject_liquidity: transfer emergency reserves directly into the bank to bolster its reserve \
ratio. Use when the bank is solvent but illiquid — a reserve boost prevents suspension without \
requiring a full public guarantee (lower moral hazard cost).

Weigh carefully:
1. Moral hazard: guarantees and injections signal that the CB will always bail out banks, \
encouraging future risk-taking.
2. Credibility: an announcement only works if credible — acting too early on weak evidence \
undermines future guarantees.
3. Cascade irreversibility: each additional withdrawal makes the next more likely. There is a \
window; after it closes, even perfect intervention arrives too late.
4. Actual insolvency: if the bank is genuinely insolvent, intervention prolongs damage. \
Letting the cascade proceed may be the correct call.

Your voice: institutional, measured, analytical. You are the lender of last resort making a \
consequential real-time judgment call.\
"""


def _build_cb_user_message(
    *,
    bank_id: str,
    bank_state: str,
    bank_reserve_ratio: float,
    cascade_fraction: float,
    withdrawn_count: int,
    total_agents: int,
    sim_time: float,
    trigger_threshold: float,
) -> str:
    return (
        f"EMERGENCY MONITORING ALERT — T+{sim_time:.0f}s\n\n"
        f"Bank under stress: {bank_id}\n"
        f"  State:           {bank_state}\n"
        f"  Reserve ratio:   {bank_reserve_ratio:.1%}\n\n"
        f"Cascade dynamics:\n"
        f"  Fully withdrawn: {withdrawn_count}/{total_agents} agents "
        f"({cascade_fraction:.0%} of depositors)\n"
        f"  Trigger threshold: {trigger_threshold:.0%} just crossed\n\n"
        f"Your decision: intervene, and if so, how?"
    )


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class CBDecisionResult:
    action: str           # "do_nothing" | "announce_guarantee" | "inject_liquidity"
    reasoning: str
    announcement_text: str
    liquidity_fraction: float
    confidence: float
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


# ---------------------------------------------------------------------------
# Central Bank agent
# ---------------------------------------------------------------------------


class CentralBankAgent:
    """Decision-maker for the central bank. Stateless across interventions."""

    def __init__(self, config: CentralBankConfig, llm_client: LLMClient) -> None:
        self._config = config
        self._llm_client = llm_client

    def decide(
        self,
        *,
        bank_id: str,
        bank_state: str,
        bank_reserve_ratio: float,
        cascade_fraction: float,
        withdrawn_count: int,
        total_agents: int,
        sim_time: float,
    ) -> CBDecisionResult:
        if self._config.policy_type == "rule_based":
            return self._decide_rule_based(cascade_fraction, bank_state, bank_reserve_ratio)
        return self._decide_llm(
            bank_id=bank_id,
            bank_state=bank_state,
            bank_reserve_ratio=bank_reserve_ratio,
            cascade_fraction=cascade_fraction,
            withdrawn_count=withdrawn_count,
            total_agents=total_agents,
            sim_time=sim_time,
        )

    # ------------------------------------------------------------------

    def _decide_rule_based(
        self,
        cascade_fraction: float,
        bank_state: str,
        bank_reserve_ratio: float,
    ) -> CBDecisionResult:
        action = self._config.rule_action
        announcement_text = ""
        liquidity_fraction = self._config.rule_liquidity_fraction

        if action == "announce_guarantee":
            announcement_text = (
                "The Central Bank hereby guarantees full coverage of all deposits at this bank. "
                "Your funds are fully protected. There is no need to withdraw."
            )

        reasoning = (
            f"Automatic rule-based trigger: cascade reached {cascade_fraction:.0%}, "
            f"bank state is {bank_state} (reserve ratio {bank_reserve_ratio:.1%}). "
            f"Applying pre-configured policy: {action}. "
            "This intervention fires at a fixed threshold without contextual analysis — "
            "it represents a regulatory body that has not yet adopted AI-speed judgment."
        )

        return CBDecisionResult(
            action=action,
            reasoning=reasoning,
            announcement_text=announcement_text,
            liquidity_fraction=liquidity_fraction,
            confidence=1.0,  # rule-based is deterministic
            model_used="rule_based",
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
        )

    def _decide_llm(
        self,
        *,
        bank_id: str,
        bank_state: str,
        bank_reserve_ratio: float,
        cascade_fraction: float,
        withdrawn_count: int,
        total_agents: int,
        sim_time: float,
    ) -> CBDecisionResult:
        user_message = _build_cb_user_message(
            bank_id=bank_id,
            bank_state=bank_state,
            bank_reserve_ratio=bank_reserve_ratio,
            cascade_fraction=cascade_fraction,
            withdrawn_count=withdrawn_count,
            total_agents=total_agents,
            sim_time=sim_time,
            trigger_threshold=self._config.trigger_threshold,
        )

        model = self._config.model or DEFAULT_SONNET_MODEL

        result = self._llm_client.decide(
            system_prompt=_CB_SYSTEM_PROMPT,
            user_message=user_message,
            model=model,
            max_tokens=1024,
            tool_schema=CB_POLICY_TOOL_SCHEMA,
            tool_validator=_validate_cb_tool_input,
        )

        ti = result.tool_input
        return CBDecisionResult(
            action=ti["action"],
            reasoning=ti["reasoning"],
            announcement_text=ti.get("announcement_text", ""),
            liquidity_fraction=float(ti.get("liquidity_fraction", 0.0)),
            confidence=float(ti["confidence"]),
            model_used=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd,
        )
