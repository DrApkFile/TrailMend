from dataclasses import dataclass

from trailmend.core.model import Change, EdgeState, EdgeStatus, Fill, MendConfig, Promote, Restore
from trailmend.core.receipts import Receipt, make_receipt
from trailmend.core.update import apply_change as compute_after
from trailmend.graph.client import HydraClient
from trailmend.graph.ids import edge_id
from trailmend.graph.state import read_state, write_state
from trailmend.loop.journal import Journal


@dataclass(frozen=True, slots=True)
class Applied:
    receipt: Receipt
    before: EdgeState
    after: EdgeState


def apply(
    client: HydraClient,
    journal: Journal,
    run_id: str,
    round_index: int,
    sequence: int,
    change: Change,
    config: MendConfig,
    origin: str = "shortcut",
) -> Applied:
    before = read_state(client, change.edge)
    if before is None:
        match change:
            case Promote(via_path=via_path):
                before = EdgeState(change.edge, 0.0, EdgeStatus.ABSENT, via_path=via_path)
            case Fill():
                before = EdgeState(change.edge, 0.0, EdgeStatus.ABSENT)
            case _:
                raise KeyError(f"{change.edge} is not in the graph, so it cannot be changed")
    after = compute_after(before, change, config)
    receipt = make_receipt(run_id, round_index, sequence, change, before, after)
    journal.append(receipt)
    write_state(client, before, after, edge_id(before.key.rel_type, before.key.src, before.key.dst), origin)
    return Applied(receipt, before, after)


def rollback_to(
    client: HydraClient,
    journal: Journal,
    run_id: str,
    round_index: int,
    sequence: int,
    before: EdgeState,
    config: MendConfig,
) -> Applied:
    undo = Restore(before.key, before)
    current = read_state(client, undo.edge)
    if current is None:
        current = EdgeState(undo.edge, 0.0, EdgeStatus.ABSENT, via_path=before.via_path)
    after = compute_after(current, undo, config)
    written = make_receipt(run_id, round_index, sequence, undo, current, after)
    journal.append(written)
    write_state(client, current, after, edge_id(current.key.rel_type, current.key.src, current.key.dst))
    return Applied(written, current, after)


def rollback(client: HydraClient, journal: Journal, receipt: Receipt, sequence: int, config: MendConfig) -> Applied:
    return rollback_to(client, journal, receipt.run_id, receipt.round_index, sequence, receipt.before, config)
