from pathlib import Path

import pytest

from trailmend.core.config import load_mend_config
from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus, MendConfig, Quarantine, Reweight, Signal
from trailmend.data import dataset
from trailmend.data.northwind import Sizes
from trailmend.graph.client import HydraClient
from trailmend.graph.loader import load
from trailmend.graph.schema import RelType
from trailmend.graph.state import read_state
from trailmend.loop.apply import apply, rollback
from trailmend.loop.journal import Journal

pytestmark = pytest.mark.hydra

SEED = 5_152
SMALL = Sizes(people=24, teams=4, services=8, alerts=12, customers=5, incidents=3, runbooks=5, repos=3)


@pytest.fixture(scope="module")
def config() -> MendConfig:
    return load_mend_config(Path("config/mend.toml"))


@pytest.fixture
def loaded(hydra: HydraClient) -> dataset.Dataset:
    built = dataset.build(SEED, SMALL)
    load(hydra, built.graph)
    return built


@pytest.fixture
def journal(tmp_path: Path) -> Journal:
    return Journal.for_run("test-run", tmp_path)


def _a_key(built: dataset.Dataset, rel_type: RelType = RelType.ON_CALL) -> EdgeKey:
    edge = built.graph.edges_of_type(rel_type)[0]
    return EdgeKey(edge.src, rel_type.value, edge.dst)


def test_d1_the_current_edge_state_is_read_back_from_the_graph(hydra: HydraClient, loaded: dataset.Dataset) -> None:
    state = read_state(hydra, _a_key(loaded))
    assert state is not None
    assert state.cost == 1.0
    assert state.status is EdgeStatus.ACTIVE
    assert state.recent == ()


def test_d1_a_receipt_is_written_before_the_graph_changes(
    hydra: HydraClient, loaded: dataset.Dataset, journal: Journal, config: MendConfig
) -> None:
    key = _a_key(loaded)
    change = Reweight(key, (Signal.BLAME,), ("q-1",))
    applied = apply(hydra, journal, "test-run", 0, 0, change, config)
    assert journal.lines()
    assert applied.receipt.receipt_id in journal.lines()[0]
    after = read_state(hydra, key)
    assert after == applied.after
    assert after is not None
    assert after.cost > applied.before.cost


def test_inv3_apply_then_rollback_leaves_the_edge_exactly_as_it_was(
    hydra: HydraClient, loaded: dataset.Dataset, journal: Journal, config: MendConfig
) -> None:
    key = _a_key(loaded)
    before = read_state(hydra, key)
    assert before is not None
    applied = apply(hydra, journal, "test-run", 0, 0, Reweight(key, (Signal.BLAME,) * 3, ("a", "b", "c")), config)
    assert read_state(hydra, key) != before
    rollback(hydra, journal, applied.receipt, 1, config)
    assert read_state(hydra, key) == before


def test_inv3_a_quarantine_rolls_back_to_the_same_active_edge(
    hydra: HydraClient, loaded: dataset.Dataset, journal: Journal, config: MendConfig
) -> None:
    key = _a_key(loaded, RelType.OWNED_BY)
    before = read_state(hydra, key)
    assert before is not None
    assert before.status is EdgeStatus.ACTIVE
    applied = apply(hydra, journal, "test-run", 1, 0, Quarantine(key, ("a", "b", "c")), config)
    quarantined = read_state(hydra, key)
    assert quarantined is not None
    assert quarantined.status is EdgeStatus.QUARANTINED
    rollback(hydra, journal, applied.receipt, 1, config)
    assert read_state(hydra, key) == before


def test_d1_the_journal_only_ever_grows(
    hydra: HydraClient, loaded: dataset.Dataset, journal: Journal, config: MendConfig
) -> None:
    key = _a_key(loaded)
    first = apply(hydra, journal, "test-run", 0, 0, Reweight(key, (Signal.CONFIRM,), ("a",)), config)
    after_one = journal.lines()
    apply(hydra, journal, "test-run", 0, 1, Reweight(key, (Signal.BLAME,), ("b",)), config)
    after_two = journal.lines()
    assert after_two[: len(after_one)] == after_one
    assert len(after_two) == len(after_one) + 1
    assert first.receipt.receipt_id in after_two[0]


def test_d1_changing_an_edge_the_graph_does_not_have_is_refused(
    hydra: HydraClient, journal: Journal, config: MendConfig
) -> None:
    missing = EdgeKey(404, RelType.ON_CALL.value, 405)
    with pytest.raises(KeyError, match="is not in the graph"):
        apply(hydra, journal, "test-run", 0, 0, Reweight(missing, (Signal.BLAME,), ("a",)), config)


def test_d1_the_recent_signal_window_survives_a_round_trip_through_the_graph(
    hydra: HydraClient, loaded: dataset.Dataset, journal: Journal, config: MendConfig
) -> None:
    key = _a_key(loaded, RelType.ALERTS_ON)
    signals = (Signal.BLAME, Signal.CONFIRM, Signal.BLAME)
    applied = apply(hydra, journal, "test-run", 0, 0, Reweight(key, signals, ("a", "b", "c")), config)
    reread = read_state(hydra, key)
    assert reread is not None
    assert reread.recent == applied.after.recent
    assert reread.recent == signals


def test_d1_a_run_id_that_could_escape_the_evidence_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="run_id must be a simple name"):
        Journal.for_run("../escape", tmp_path)


def test_d1_a_rolled_back_edge_can_be_changed_again(
    hydra: HydraClient, loaded: dataset.Dataset, journal: Journal, config: MendConfig
) -> None:
    key = _a_key(loaded, RelType.MEMBER_OF)
    start = read_state(hydra, key)
    assert start is not None
    applied = apply(hydra, journal, "test-run", 0, 0, Reweight(key, (Signal.BLAME,), ("a",)), config)
    rollback(hydra, journal, applied.receipt, 1, config)
    again = apply(hydra, journal, "test-run", 0, 2, Reweight(key, (Signal.CONFIRM,), ("b",)), config)
    assert again.before == start
    assert again.after.cost < start.cost


def test_d1_an_edge_state_is_a_frozen_value(loaded: dataset.Dataset) -> None:
    state = EdgeState(_a_key(loaded), 1.0)
    with pytest.raises(AttributeError):
        state.cost = 2.0  # pyright: ignore[reportAttributeAccessIssue]
