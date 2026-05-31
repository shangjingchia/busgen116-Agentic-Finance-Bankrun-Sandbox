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

    # Cents-on-the-dollar that depositors recover if the bank is wound up. A
    # solvent bank is 1.0 (deposits fully backed by assets, even if not all are
    # liquid right now). A genuinely INSOLVENT bank is < 1.0 — its assets are
    # worth less than its liabilities, so depositors who hold through the failure
    # take a real principal loss. This is separate from reserve_ratio, which only
    # measures how much can be paid out *immediately* (and drives suspension).
    asset_recovery_ratio: float = 1.0

    # State stamps populated by the engine
    distress_threshold: float = field(default=0.20)   # ratio below which bank is distressed
    suspension_threshold: float = field(default=0.05) # ratio below which bank suspends

    # Fees collected from early withdrawals. Tracked explicitly so the fee does
    # not silently distort the reserve/deposit accounting (it is bank income, not
    # a depositor liability and not part of payable reserves).
    fees_collected: float = 0.0

    # Continuous token-bucket capacity meter. The old integer-second window reset
    # the budget on every whole second, so at AI speed (withdrawals clustered at
    # dense fractional timestamps) the cap almost never bound. The bucket refills
    # continuously at withdrawal_processing_capacity per simulation second and is
    # capped at one second's worth of burst.
    _capacity_bucket: Optional[float] = field(default=None, init=False, repr=False)
    _last_refill_time: float = field(default=0.0, init=False, repr=False)

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
            cap = self.withdrawal_processing_capacity
            if self._capacity_bucket is None:
                # Start with one second's worth of burst available.
                self._capacity_bucket = cap
                self._last_refill_time = timestamp
            else:
                elapsed = max(0.0, timestamp - self._last_refill_time)
                self._capacity_bucket = min(cap, self._capacity_bucket + elapsed * cap)
                self._last_refill_time = timestamp
            capacity_remaining = max(0.0, self._capacity_bucket)

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
            self.fees_collected += actual_fee
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
            self.fees_collected += fee
            result = WithdrawalResult(
                amount_requested=amount_requested,
                amount_paid_out=net_to_agent,
                amount_debited=gross,
                fee_paid=fee,
                was_queued=capacity_limited,
                new_bank_state=self._recompute_state(),
            )

        if timestamp is not None and self._capacity_bucket is not None:
            self._capacity_bucket = max(0.0, self._capacity_bucket - result.amount_debited)
        return result

    def available_for_payment(self, agent_id: str) -> float:
        """Cash the agent could pull right now to settle a routine payment.
        Zero if the bank is suspended — which is exactly how a bank run breaks the
        payment chain. Bounded by both the agent's deposit and the bank's reserves."""
        if self.state == BankState.SUSPENDED:
            return 0.0
        return max(0.0, min(self.deposits.get(agent_id, 0.0), self.reserves))

    def debit_for_payment(self, agent_id: str, amount: float) -> float:
        """Move `amount` out of the agent's deposit to settle a routine scheduled
        payment. No early-withdrawal fee (this is a bill payment, not a panic
        exit). Returns the amount actually debited."""
        if self.state == BankState.SUSPENDED or amount <= 0:
            return 0.0
        debit = max(0.0, min(amount, self.deposits.get(agent_id, 0.0), self.reserves))
        if debit <= 0:
            return 0.0
        self.deposits[agent_id] -= debit
        self.reserves -= debit
        self._recompute_state()
        return debit

    def apply_insolvency_haircut(self) -> Dict[str, float]:
        """Crystallize losses for remaining depositors when the bank is genuinely
        insolvent (asset_recovery_ratio < 1.0). Used at finalize when a *true*
        rumor's bank is wound up. Each remaining deposit is written down to its
        recovery value; returns {agent_id: loss_amount} so the engine can post the
        loss to ledgers.

        This is what makes a 'real crisis' mechanically real rather than a label:
        an agent who held through a true insolvency actually loses principal,
        while an agent who got out earlier kept theirs.
        """
        recovery = max(0.0, min(1.0, self.asset_recovery_ratio))
        if recovery >= 1.0:
            return {}
        losses: Dict[str, float] = {}
        for agent_id, deposit in list(self.deposits.items()):
            if deposit <= 0:
                continue
            recovered = deposit * recovery
            loss = deposit - recovered
            if loss > 0:
                losses[agent_id] = loss
                self.deposits[agent_id] = recovered
        return losses

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
            "fees_collected": self.fees_collected,
            "asset_recovery_ratio": self.asset_recovery_ratio,
            "early_withdrawal_fee_rate": self.early_withdrawal_fee_rate,
            "distress_threshold": self.distress_threshold,
            "suspension_threshold": self.suspension_threshold,
        }
