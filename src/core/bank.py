"""
Bank: deposit ledger + reserves + withdrawal processing.

The bank is generic. Adding a third or fourth bank is configuration, not code —
this is one of the v2 hooks we preserve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class BankState(str, Enum):
    HEALTHY = "healthy"
    DISTRESSED = "distressed"
    SUSPENDED = "suspended"


@dataclass
class WithdrawalResult:
    """What happened when a withdrawal request was processed."""

    amount_requested: float
    amount_paid_out: float       # net to agent after fee
    amount_debited: float        # gross debited from deposit (paid_out + fee)
    fee_paid: float
    was_queued: bool             # if processing capacity exceeded, the request was queued
    new_bank_state: BankState

    def to_dict(self) -> dict[str, Any]:
        return {
            "amount_requested": self.amount_requested,
            "amount_paid_out": self.amount_paid_out,
            "amount_debited": self.amount_debited,
            "fee_paid": self.fee_paid,
            "was_queued": self.was_queued,
            "new_bank_state": self.new_bank_state.value,
        }


@dataclass
class Bank:
    bank_id: str
    name: str
    deposits: Dict[str, float]                 # agent_id -> deposited amount
    reserves: float
    reserve_ratio_target: float
    withdrawal_processing_capacity: float       # max USD per simulation second
    state: BankState = BankState.HEALTHY
    early_withdrawal_fee_rate: float = 0.03

    # State stamps populated by the engine
    distress_threshold: float = field(default=0.20)   # ratio below which bank is distressed
    suspension_threshold: float = field(default=0.05) # ratio below which bank suspends
    _capacity_window_second: Optional[int] = field(default=None, init=False, repr=False)
    _capacity_used_in_window: float = field(default=0.0, init=False, repr=False)

    def total_deposits(self) -> float:
        return sum(self.deposits.values())

    def reserve_ratio(self) -> float:
        total = self.total_deposits()
        if total <= 0:
            return 1.0
        return self.reserves / total

    def _recompute_state(self) -> BankState:
        ratio = self.reserve_ratio()
        if ratio < self.suspension_threshold or self.reserves <= 0:
            self.state = BankState.SUSPENDED
        elif ratio < self.distress_threshold:
            self.state = BankState.DISTRESSED
        else:
            self.state = BankState.HEALTHY
        return self.state

    def process_withdrawal(
        self,
        agent_id: str,
        amount_requested: float,
        *,
        timestamp: Optional[float] = None,
    ) -> WithdrawalResult:
        """Process a withdrawal. Mutates self.deposits and self.reserves.

        For v1, fees are deducted from the gross debited amount. The agent receives
        (amount - fee). The bank loses (amount - fee) of reserves; the fee remains
        as bank capital (it does not leave the bank).

        If a timestamp is supplied, withdrawal_processing_capacity is enforced as
        a per-second gross-debit cap. Requests beyond that capacity remain queued.
        """
        if agent_id not in self.deposits:
            raise ValueError(f"Agent {agent_id} has no deposit at {self.bank_id}")

        if self.state == BankState.SUSPENDED:
            return WithdrawalResult(
                amount_requested=amount_requested,
                amount_paid_out=0.0,
                amount_debited=0.0,
                fee_paid=0.0,
                was_queued=True,
                new_bank_state=self.state,
            )

        requested_gross = min(amount_requested, self.deposits[agent_id])
        capacity_remaining = requested_gross
        if timestamp is not None and self.withdrawal_processing_capacity >= 0:
            window_second = int(timestamp)
            if self._capacity_window_second != window_second:
                self._capacity_window_second = window_second
                self._capacity_used_in_window = 0.0
            capacity_remaining = max(
                0.0,
                self.withdrawal_processing_capacity - self._capacity_used_in_window,
            )

        gross = min(requested_gross, capacity_remaining)
        capacity_limited = gross < requested_gross
        if gross <= 0.0:
            return WithdrawalResult(
                amount_requested=amount_requested,
                amount_paid_out=0.0,
                amount_debited=0.0,
                fee_paid=0.0,
                was_queued=True,
                new_bank_state=self.state,
            )

        fee = gross * self.early_withdrawal_fee_rate
        net_to_agent = gross - fee

        # Reserves can only pay what they have
        cash_available = max(0.0, self.reserves)
        actually_paid = min(net_to_agent, cash_available)

        # If we cannot pay the full net, the deposit is debited only by what was paid + the fee
        # (the rest of the request was queued)
        if actually_paid < net_to_agent:
            was_queued = True
            actual_gross = actually_paid / (1 - self.early_withdrawal_fee_rate) if self.early_withdrawal_fee_rate < 1 else actually_paid
            actual_fee = actual_gross - actually_paid
            self.deposits[agent_id] -= actual_gross
            self.reserves -= actually_paid
            result = WithdrawalResult(
                amount_requested=amount_requested,
                amount_paid_out=actually_paid,
                amount_debited=actual_gross,
                fee_paid=actual_fee,
                was_queued=was_queued,
                new_bank_state=self._recompute_state(),
            )
        else:
            self.deposits[agent_id] -= gross
            self.reserves -= net_to_agent
            result = WithdrawalResult(
                amount_requested=amount_requested,
                amount_paid_out=net_to_agent,
                amount_debited=gross,
                fee_paid=fee,
                was_queued=capacity_limited,
                new_bank_state=self._recompute_state(),
            )

        if timestamp is not None:
            self._capacity_used_in_window += result.amount_debited
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "bank_id": self.bank_id,
            "name": self.name,
            "deposits": dict(self.deposits),
            "reserves": self.reserves,
            "reserve_ratio_target": self.reserve_ratio_target,
            "withdrawal_processing_capacity": self.withdrawal_processing_capacity,
            "state": self.state.value,
            "reserve_ratio": self.reserve_ratio(),
            "total_deposits": self.total_deposits(),
            "early_withdrawal_fee_rate": self.early_withdrawal_fee_rate,
            "distress_threshold": self.distress_threshold,
            "suspension_threshold": self.suspension_threshold,
        }
