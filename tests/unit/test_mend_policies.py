from random import Random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.conftest import edge
from trailmend.core.model import Change, Quarantine, Reweight, Signal
from trailmend.loop.policy import (
    CONTROL_OF,
    RANDOM_QUESTION_PREFIX,
    MendPolicy,
    profile,
    shape,
)

POOL = [edge(n) for n in range(100, 400)]


def _plan(reweights: int, quarantines: int) -> tuple[Change, ...]:
    planned: list[Change] = [
        Reweight(edge(i), (Signal.BLAME,) * (1 + i % 3), (f"q{i}",) * (1 + i % 3)) for i in range(reweights)
    ]
    planned.extend(Quarantine(edge(i), (f"q{i}",)) for i in range(quarantines))
    return tuple(planned)


def test_full_applies_the_plan_unchanged() -> None:
    planned = _plan(4, 2)
    assert shape(MendPolicy.FULL, planned, POOL, Random(1)) == planned


def test_frozen_changes_nothing() -> None:
    assert shape(MendPolicy.FROZEN, _plan(4, 2), POOL, Random(1)) == ()


def test_reweight_only_keeps_the_cost_changes_and_drops_the_quarantines() -> None:
    chosen = shape(MendPolicy.REWEIGHT_ONLY, _plan(4, 2), POOL, Random(1))
    assert profile(chosen).quarantines == 0
    assert profile(chosen).reweights == 4


def test_quarantine_only_keeps_the_quarantines_and_drops_the_cost_changes() -> None:
    chosen = shape(MendPolicy.QUARANTINE_ONLY, _plan(4, 2), POOL, Random(1))
    assert profile(chosen).reweights == 0
    assert profile(chosen).quarantines == 2


@pytest.mark.parametrize("arm", sorted(CONTROL_OF))
def test_inv6_a_random_arm_makes_the_same_number_and_magnitude_of_changes_as_its_control(arm: MendPolicy) -> None:
    planned = _plan(5, 3)
    rng = Random(11)
    assert profile(shape(arm, planned, POOL, rng)) == profile(shape(CONTROL_OF[arm], planned, POOL, rng))


@settings(max_examples=60, deadline=None)
@given(
    reweights=st.integers(min_value=0, max_value=30),
    quarantines=st.integers(min_value=0, max_value=30),
    seed=st.integers(min_value=0, max_value=10_000),
)
def test_inv6_holds_for_every_plan_shape(reweights: int, quarantines: int, seed: int) -> None:
    planned = _plan(reweights, quarantines)
    for arm, control in CONTROL_OF.items():
        mirrored = profile(shape(arm, planned, POOL, Random(seed)))
        assert mirrored == profile(shape(control, planned, POOL, Random(seed)))


def test_a_random_arm_moves_the_changes_onto_other_edges() -> None:
    planned = _plan(8, 0)
    chosen = shape(MendPolicy.RANDOM_REWEIGHT, planned, POOL, Random(3))
    assert {c.edge for c in chosen} != {c.edge for c in planned}
    assert {c.edge for c in chosen} <= set(POOL)


def test_a_random_arm_marks_its_changes_so_receipts_cannot_claim_real_credit() -> None:
    chosen = shape(MendPolicy.RANDOM_REWEIGHT, _plan(3, 0), POOL, Random(3))
    assert all(q.startswith(RANDOM_QUESTION_PREFIX) for c in chosen if isinstance(c, Reweight) for q in c.question_ids)


def test_the_same_seed_picks_the_same_edges_and_another_seed_does_not() -> None:
    planned = _plan(6, 4)
    for arm in CONTROL_OF:
        same = shape(arm, planned, POOL, Random(7))
        assert same == shape(arm, planned, POOL, Random(7))
        assert same != shape(arm, planned, POOL, Random(8))


def test_a_pool_too_small_to_mirror_the_plan_is_refused_rather_than_shrunk() -> None:
    with pytest.raises(ValueError, match="needs 5 distinct edges"):
        shape(MendPolicy.RANDOM_REWEIGHT, _plan(5, 0), POOL[:4], Random(1))
