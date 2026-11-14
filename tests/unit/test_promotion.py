import pytest

from trailmend.core.model import Credit, EdgeKey, EdgeState, EdgeStatus, MendConfig, Promote, Retire, Signal
from trailmend.core.promote import Confirmation, candidates, promotions, retirements, shortcut_key
from trailmend.core.receipts import inverse, make_receipt
from trailmend.core.update import apply_change, plan_round, should_quarantine

SC = "SC_PAGE_OWNER"
HOP1 = EdgeKey(1, "ALERTS_ON", 2)
HOP2 = EdgeKey(2, "OWNED_BY", 3)
HOP3 = EdgeKey(3, "ON_CALL", 4)
PATH = (HOP1, HOP2, HOP3)
COSTS = {HOP1: 1.0, HOP2: 0.5, HOP3: 0.25}


def _confirmed(path: tuple[EdgeKey, ...], question_ids: tuple[str, ...]) -> list[Confirmation]:
    return [Confirmation(q, SC, path) for q in question_ids]


def test_a_path_confirmed_by_enough_distinct_questions_is_promotable(cfg: MendConfig) -> None:
    found = candidates(_confirmed(PATH, ("q1", "q2", "q3")), (), cfg)
    assert shortcut_key(SC, PATH) in {c.key for c in found}


def test_a_confirmed_sub_path_is_promotable_on_its_own(cfg: MendConfig) -> None:
    found = candidates(_confirmed(PATH, ("q1", "q2", "q3")), (), cfg)
    assert {c.via_path for c in found} == {(HOP1, HOP2), (HOP2, HOP3), PATH}


def test_too_few_distinct_questions_promote_nothing(cfg: MendConfig) -> None:
    assert candidates(_confirmed(PATH, ("q1", "q2")), (), cfg) == ()


def test_the_same_question_confirmed_twice_counts_once(cfg: MendConfig) -> None:
    assert candidates(_confirmed(PATH, ("q1", "q1", "q1", "q1")), (), cfg) == ()


def test_a_single_hop_is_never_compressed(cfg: MendConfig) -> None:
    assert candidates(_confirmed((HOP1,), ("q1", "q2", "q3")), (), cfg) == ()


def test_a_path_already_holding_a_shortcut_is_never_compressed_again(cfg: MendConfig) -> None:
    nested = (EdgeKey(1, SC, 3), HOP3)
    assert candidates(_confirmed(nested, ("q1", "q2", "q3")), (), cfg) == ()


def test_an_existing_shortcut_is_not_promoted_twice(cfg: MendConfig) -> None:
    found = candidates(_confirmed(PATH, ("q1", "q2", "q3")), [shortcut_key(SC, PATH)], cfg)
    assert shortcut_key(SC, PATH) not in {c.key for c in found}


def test_a_shortcut_starts_at_the_cost_of_the_path_it_compresses(cfg: MendConfig) -> None:
    found = [c for c in candidates(_confirmed(PATH, ("q1", "q2", "q3")), (), cfg) if c.via_path == PATH]
    assert [p.cost for p in promotions(found, COSTS)] == [1.75]


def test_a_path_with_a_hop_that_has_no_live_cost_is_left_alone(cfg: MendConfig) -> None:
    found = [c for c in candidates(_confirmed(PATH, ("q1", "q2", "q3")), (), cfg) if c.via_path == PATH]
    assert promotions(found, {HOP1: 1.0, HOP3: 1.0}) == ()


def test_inv5_a_shortcut_is_retired_when_one_of_its_hops_is_quarantined() -> None:
    key = shortcut_key(SC, PATH)
    assert retirements({key: PATH}, {HOP2}) == (Retire(key, PATH),)


def test_inv5_a_shortcut_whose_hops_are_all_live_is_kept() -> None:
    assert retirements({shortcut_key(SC, PATH): PATH}, {EdgeKey(9, "ON_CALL", 10)}) == ()


def test_promoting_brings_an_absent_edge_to_life(cfg: MendConfig) -> None:
    key = shortcut_key(SC, PATH)
    absent = EdgeState(key, 0.0, EdgeStatus.ABSENT, via_path=PATH)
    live = apply_change(absent, Promote(key, PATH, ("q1", "q2", "q3"), 1.75), cfg)
    assert live.status is EdgeStatus.ACTIVE
    assert live.cost == 1.75
    assert live.via_path == PATH


def test_a_shortcut_cannot_be_promoted_over_an_edge_that_already_exists(cfg: MendConfig) -> None:
    key = shortcut_key(SC, PATH)
    with pytest.raises(ValueError, match="already exists"):
        apply_change(EdgeState(key, 1.0, via_path=PATH), Promote(key, PATH, ("q1",), 1.0), cfg)


def test_an_absent_edge_cannot_be_retired(cfg: MendConfig) -> None:
    key = shortcut_key(SC, PATH)
    with pytest.raises(ValueError, match="already gone"):
        apply_change(EdgeState(key, 0.0, EdgeStatus.ABSENT, via_path=PATH), Retire(key, PATH), cfg)


def test_inv3_rolling_back_a_promotion_leaves_the_shortcut_absent(cfg: MendConfig) -> None:
    key = shortcut_key(SC, PATH)
    absent = EdgeState(key, 0.0, EdgeStatus.ABSENT, via_path=PATH)
    change = Promote(key, PATH, ("q1", "q2", "q3"), 1.75)
    live = apply_change(absent, change, cfg)
    receipt = make_receipt("run", 1, 0, change, absent, live)
    assert apply_change(live, inverse(receipt), cfg) == absent


def test_inv3_rolling_back_a_retirement_brings_the_shortcut_back_whole(cfg: MendConfig) -> None:
    key = shortcut_key(SC, PATH)
    live = EdgeState(key, 1.75, EdgeStatus.ACTIVE, confirms=4, blames=1, via_path=PATH)
    change = Retire(key, PATH)
    gone = apply_change(live, change, cfg)
    receipt = make_receipt("run", 1, 0, change, live, gone)
    assert apply_change(gone, inverse(receipt), cfg) == live


def test_a_retired_shortcut_receives_no_further_changes(cfg: MendConfig) -> None:
    key = shortcut_key(SC, PATH)
    gone = EdgeState(key, 1.75, EdgeStatus.ABSENT, blames=9, recent=(Signal.BLAME,) * cfg.window, via_path=PATH)
    assert not should_quarantine(gone, cfg, confirmed_this_round=False)
    assert plan_round({key: gone}, [Credit(key, Signal.BLAME, "q1")], cfg) == ()
