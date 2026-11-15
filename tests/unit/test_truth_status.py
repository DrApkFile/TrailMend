from trailmend.api.routes_truth import CORRECTED, QUARANTINED, RESTORED, STILL_WRONG, added_status, wrong_status
from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus
from trailmend.data.faultmodel import EdgeDelta, WrongKind
from trailmend.data.model import Edge
from trailmend.graph.schema import RelType

WRONG = EdgeKey(1, "OWNED_BY", 3)
TRUE = EdgeKey(1, "OWNED_BY", 2)


def _state(key: EdgeKey, cost: float, status: EdgeStatus = EdgeStatus.ACTIVE) -> EdgeState:
    return EdgeState(key, cost, status)


def test_a_contradicted_fault_is_still_wrong_until_the_true_link_is_the_cheaper_one() -> None:
    kind = WrongKind.CONTRADICTED
    assert wrong_status(kind, _state(WRONG, 0.477), _state(TRUE, 1.0)) == STILL_WRONG
    assert wrong_status(kind, _state(WRONG, 1.36), _state(TRUE, 0.9)) == CORRECTED


def test_a_quarantined_wrong_link_reads_as_quarantined_whatever_the_true_link_costs() -> None:
    quarantined = _state(WRONG, 0.477, EdgeStatus.QUARANTINED)
    assert wrong_status(WrongKind.CONTRADICTED, quarantined, _state(TRUE, 1.0)) == QUARANTINED
    assert wrong_status(WrongKind.DESTROYED, quarantined, None) == QUARANTINED


def test_a_recoverable_fault_is_restored_once_gap_fill_has_put_the_true_link_in_the_graph() -> None:
    kind = WrongKind.RECOVERABLE
    assert wrong_status(kind, _state(WRONG, 1.0), None) == STILL_WRONG
    assert wrong_status(kind, _state(WRONG, 1.0), _state(TRUE, 1.0)) == RESTORED


def test_a_destroyed_fault_can_only_stay_wrong_or_be_quarantined() -> None:
    assert wrong_status(WrongKind.DESTROYED, _state(WRONG, 1.0), None) == STILL_WRONG


def test_a_structural_fault_is_quarantined_only_when_every_edge_it_added_is() -> None:
    first = Edge(10, 1, RelType.ALERTS_ON, 2)
    second = Edge(11, 3, RelType.ALERTS_ON, 2)
    delta = EdgeDelta(added=(first, second))
    one, two = EdgeKey(1, "ALERTS_ON", 2), EdgeKey(3, "ALERTS_ON", 2)
    mixed = {one: _state(one, 1.0, EdgeStatus.QUARANTINED), two: _state(two, 1.0)}
    assert added_status(delta, mixed) == STILL_WRONG
    every = {one: _state(one, 1.0, EdgeStatus.QUARANTINED), two: _state(two, 1.0, EdgeStatus.QUARANTINED)}
    assert added_status(delta, every) == QUARANTINED
