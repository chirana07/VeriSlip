from pathlib import Path

import pytest

from core.research.courier_roi import (
    CourierPilotAssumptions,
    estimated_avoided_loss_lkr,
)


def test_roi_uses_only_explicit_assumptions():
    assumptions = CourierPilotAssumptions(1000, 0.02, 5000, 0.5)
    assert estimated_avoided_loss_lkr(assumptions) == 50_000


@pytest.mark.parametrize(
    "assumptions",
    [
        CourierPilotAssumptions(-1, 0.1, 100, 0.5),
        CourierPilotAssumptions(1, 1.1, 100, 0.5),
        CourierPilotAssumptions(1, 0.1, -100, 0.5),
        CourierPilotAssumptions(1, 0.1, 100, float("nan")),
    ],
)
def test_roi_rejects_invalid_or_misleading_inputs(assumptions):
    with pytest.raises(ValueError):
        estimated_avoided_loss_lkr(assumptions)


def test_proposal_and_editable_deck_source_are_present():
    proposal = Path("docs/courier_pilot/COURIER_PILOT_PROPOSAL.md").read_text(encoding="utf-8")
    builder = Path("docs/courier_pilot/build_deck.mjs").read_text(encoding="utf-8")
    assert "does not claim endorsement" in proposal
    assert "transactions" in proposal and "intervention effectiveness" in proposal
    assert "POST /api/v1/courier/verify" in proposal
    assert "Presentation.create" in builder
