from pathlib import Path

import pytest

from trailmend.core.config import V1_RULE, V2_RULE, load_mend_config
from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus, Signal
from trailmend.core.update import apply_signal
from trailmend.eval.run import RUN2_ARMS
from trailmend.loop.policy import MendPolicy, rules

CONFIG = Path("config/mend.toml")
KEY = EdgeKey(1, "OWNED_BY", 2)


def _state(cost: float) -> EdgeState:
    return EdgeState(KEY, cost, EdgeStatus.ACTIVE)


def test_the_run_two_rule_moves_a_confirmed_edge_less_than_a_blamed_one() -> None:
    cfg = load_mend_config(CONFIG, V2_RULE)
    confirmed = apply_signal(_state(1.0), Signal.CONFIRM, cfg)
    blamed = apply_signal(_state(1.0), Signal.BLAME, cfg)
    assert 1.0 - confirmed.cost < blamed.cost - 1.0


def test_the_run_one_rule_moves_them_by_the_same_factor() -> None:
    cfg = load_mend_config(CONFIG, V1_RULE)
    assert cfg.eta_confirm is None
    confirmed = apply_signal(_state(1.0), Signal.CONFIRM, cfg)
    blamed = apply_signal(_state(1.0), Signal.BLAME, cfg)
    assert round(confirmed.cost * blamed.cost, 12) == 1.0


def test_both_rules_keep_cost_inside_their_own_bounds() -> None:
    for rule in (V1_RULE, V2_RULE):
        cfg = load_mend_config(CONFIG, rule)
        state = _state(1.0)
        for _ in range(50):
            state = apply_signal(state, Signal.CONFIRM, cfg)
            assert cfg.cost_floor <= state.cost <= cfg.cost_ceiling
        for _ in range(100):
            state = apply_signal(state, Signal.BLAME, cfg)
            assert cfg.cost_floor <= state.cost <= cfg.cost_ceiling


def test_the_run_two_floor_leaves_the_ranking_room_to_discriminate() -> None:
    cfg = load_mend_config(CONFIG, V2_RULE)
    assert cfg.cost_floor > load_mend_config(CONFIG, V1_RULE).cost_floor


def test_an_unknown_update_rule_is_refused_rather_than_guessed() -> None:
    with pytest.raises(ValueError, match="unknown update rule"):
        load_mend_config(CONFIG, "v3")


def test_each_random_control_plans_under_the_same_update_rule_as_the_arm_it_attacks() -> None:
    wanted = rules(MendPolicy.FULL_V2).update
    for arm in (MendPolicy.RANDOM_REWEIGHT, MendPolicy.RANDOM_QUARANTINE):
        assert arm in RUN2_ARMS
        assert rules(arm).update == wanted


def test_the_run_two_arm_set_is_the_one_that_was_preregistered() -> None:
    assert [arm.value for arm in RUN2_ARMS] == [
        "full_v2",
        "frozen",
        "full_v1_rule",
        "gapfill_wide_only",
        "random_reweight",
        "random_quarantine",
    ]
