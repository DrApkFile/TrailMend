import random

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.conftest import edge, fresh
from trailmend.core.credit import Correct, Refused, Unreachable, Wrong, assign_credit
from trailmend.core.model import Credit, EdgeStatus, MendConfig, Quarantine, Reweight, Signal
from trailmend.core.receipts import inverse, make_receipt
from trailmend.core.update import apply_change, apply_signal, plan_round

signals = st.lists(st.sampled_from(list(Signal)), min_size=1, max_size=40)


def test_inv1_one_confirmation_never_outweighs_repeated_blame(cfg: MendConfig) -> None:
    state = fresh(1)
    for _ in range(cfg.quarantine_min_blames):
        state = apply_signal(state, Signal.BLAME, cfg)
    state = apply_signal(state, Signal.CONFIRM, cfg)
    assert state.cost > 1.0


def test_inv2_quarantine_never_fires_on_an_edge_confirmed_in_the_same_round(cfg: MendConfig) -> None:
    target = edge(1)
    states = {target: fresh(1)}
    credits = [Credit(target, Signal.BLAME, f"q{i}") for i in range(5)] + [Credit(target, Signal.CONFIRM, "q9")]
    changes = plan_round(states, credits, cfg)
    assert not any(isinstance(c, Quarantine) for c in changes)


def test_repeated_blame_across_rounds_quarantines_the_edge(cfg: MendConfig) -> None:
    target = edge(1)
    state = fresh(1)
    quarantined_at = None
    for round_index in range(5):
        changes = plan_round({target: state}, [Credit(target, Signal.BLAME, f"r{round_index}")], cfg)
        for change in changes:
            state = apply_change(state, change, cfg)
        if state.status is EdgeStatus.QUARANTINED:
            quarantined_at = round_index
            break
    assert quarantined_at == cfg.quarantine_min_blames - 1


def test_a_quarantined_edge_receives_no_further_changes(cfg: MendConfig) -> None:
    target = edge(1)
    state = apply_change(fresh(1), Quarantine(target, ("q1",)), cfg)
    assert plan_round({target: state}, [Credit(target, Signal.CONFIRM, "q2")], cfg) == ()


@given(signals)
def test_cost_always_stays_within_bounds(seq: list[Signal]) -> None:
    cfg = MendConfig(0.35, 0.05, 20.0, 6, 3, 0.8, 1, 3)
    state = fresh(1)
    for s in seq:
        state = apply_signal(state, s, cfg)
        assert cfg.cost_floor <= state.cost <= cfg.cost_ceiling


@settings(max_examples=300)
@given(signals, st.integers(min_value=0, max_value=50))
def test_inv3_rollback_restores_the_exact_prior_edge_state(seq: list[Signal], warmup: int) -> None:
    cfg = MendConfig(0.35, 0.05, 20.0, 6, 3, 0.8, 1, 3)
    before = fresh(1)
    for _ in range(warmup % 7):
        before = apply_signal(before, Signal.CONFIRM, cfg)
    change = Reweight(before.key, tuple(seq), tuple(f"q{i}" for i in range(len(seq))))
    after = apply_change(before, change, cfg)
    receipt = make_receipt("run-test", 1, 0, change, before, after)
    assert apply_change(after, inverse(receipt), cfg) == before


@given(st.lists(st.tuples(st.integers(0, 5), st.sampled_from(list(Signal))), min_size=1, max_size=60), st.integers())
def test_plan_round_is_independent_of_credit_order(raw: list[tuple[int, Signal]], seed: int) -> None:
    cfg = MendConfig(0.35, 0.05, 20.0, 6, 3, 0.8, 1, 3)
    credits = [Credit(edge(n), s, f"q{i}") for i, (n, s) in enumerate(raw)]
    states = {edge(n): fresh(n) for n in range(6)}
    shuffled = credits[:]
    random.Random(seed).shuffle(shuffled)
    assert plan_round(states, credits, cfg) == plan_round(states, shuffled, cfg)


def test_receipt_digest_changes_when_any_field_changes(cfg: MendConfig) -> None:
    before = fresh(1)
    change = Reweight(before.key, (Signal.BLAME,), ("q1",))
    after = apply_change(before, change, cfg)
    a = make_receipt("run-a", 1, 0, change, before, after)
    b = make_receipt("run-a", 1, 1, change, before, after)
    assert a.digest != b.digest
    assert a.receipt_id != b.receipt_id


def test_correct_answer_confirms_each_chosen_edge_once() -> None:
    path = [edge(1), edge(2), edge(1)]
    credits = assign_credit(Correct("q1", path))
    assert [(c.edge, c.signal) for c in credits] == [(edge(1), Signal.CONFIRM), (edge(2), Signal.CONFIRM)]


def test_wrong_answer_blames_only_edges_off_the_gold_path_and_confirms_the_gold_path() -> None:
    shared, wrong_hop, gold_hop = edge(1), edge(2), edge(3)
    credits = assign_credit(Wrong("q1", [shared, wrong_hop], [shared, gold_hop]))
    assert {(c.edge, c.signal) for c in credits} == {
        (wrong_hop, Signal.BLAME),
        (shared, Signal.CONFIRM),
        (gold_hop, Signal.CONFIRM),
    }


def test_unreachable_and_refused_outcomes_change_nothing() -> None:
    assert assign_credit(Unreachable("q1", 7, "Person", "page_owner")) == ()
    assert assign_credit(Refused("q2", "ambiguous_answer")) == ()
