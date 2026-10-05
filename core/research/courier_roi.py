"""Transparent, assumption-driven economics for a courier verification pilot."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class CourierPilotAssumptions:
    """Operator-supplied inputs; VeriSlip does not provide market estimates."""

    transactions: int
    fraud_attempt_rate: float
    average_fraudulent_order_value_lkr: float
    intervention_effectiveness: float

    def validate(self) -> None:
        values = (
            self.fraud_attempt_rate,
            self.average_fraudulent_order_value_lkr,
            self.intervention_effectiveness,
        )
        if self.transactions < 0 or any(not isfinite(value) for value in values):
            raise ValueError("Pilot assumptions must be finite and non-negative.")
        if not 0 <= self.fraud_attempt_rate <= 1:
            raise ValueError("Fraud attempt rate must be between 0 and 1.")
        if self.average_fraudulent_order_value_lkr < 0:
            raise ValueError("Average order value must be non-negative.")
        if not 0 <= self.intervention_effectiveness <= 1:
            raise ValueError("Intervention effectiveness must be between 0 and 1.")


def estimated_avoided_loss_lkr(assumptions: CourierPilotAssumptions) -> float:
    """Return a scenario estimate, never an observed or guaranteed saving."""
    assumptions.validate()
    return (
        assumptions.transactions
        * assumptions.fraud_attempt_rate
        * assumptions.average_fraudulent_order_value_lkr
        * assumptions.intervention_effectiveness
    )
