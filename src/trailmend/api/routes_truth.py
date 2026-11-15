import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import cast

from fastapi import APIRouter, Request

from trailmend.api.models import Hop, ReceiptSummary, TruthEdge, TruthFault, TruthResponse
from trailmend.api.state import Live
from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus
from trailmend.data.faultmodel import EdgeDelta, WrongEdge, WrongKind
from trailmend.data.model import Edge
from trailmend.graph.state import read_states

router = APIRouter()

STILL_WRONG = "still_wrong"
QUARANTINED = "quarantined"
CORRECTED = "corrected"
RESTORED = "restored_by_gapfill"
ABSENT = EdgeStatus.ABSENT.value
REPAIR: Mapping[str, str] = {
    WrongKind.CONTRADICTED.value: "reweighting: the true link is in the graph, priced above the stale one",
    WrongKind.RECOVERABLE.value: "gap-fill: the true link is in a document that has not been ingested",
    WrongKind.DESTROYED.value: "nothing: the true link is in no document, so the most it can become is a refusal",
    "missing_edge": "gap-fill: the link is in a document that has not been ingested",
    "alias_duplicate": "nothing yet: merging duplicate entities is on the roadmap, not built",
    "conflation": "nothing yet: splitting a conflated entity is on the roadmap, not built",
}


def _key(edge: Edge) -> EdgeKey:
    return EdgeKey(edge.src, edge.rel_type.value, edge.dst)


def _names(live: Live) -> dict[int, str]:
    return {node.id: node.name for node in live.built.truth.nodes} | live.names


def _edge(names: Mapping[int, str], states: Mapping[EdgeKey, EdgeState], key: EdgeKey) -> TruthEdge:
    state = states.get(key)
    return TruthEdge(
        hop=Hop(
            src=key.src,
            src_name=names.get(key.src, str(key.src)),
            rel_type=key.rel_type,
            dst=key.dst,
            dst_name=names.get(key.dst, str(key.dst)),
            cost=state.cost if state else 0.0,
        ),
        status=state.status.value if state else ABSENT,
    )


def wrong_status(kind: WrongKind, wrong: EdgeState | None, true: EdgeState | None) -> str:
    if wrong is None or wrong.status is EdgeStatus.QUARANTINED:
        return QUARANTINED if wrong is not None else CORRECTED
    if true is None or true.status is not EdgeStatus.ACTIVE:
        return STILL_WRONG
    if kind is WrongKind.RECOVERABLE:
        return RESTORED
    return CORRECTED if true.cost < wrong.cost else STILL_WRONG


def added_status(delta: EdgeDelta, states: Mapping[EdgeKey, EdgeState]) -> str:
    found = [states.get(_key(edge)) for edge in delta.added]
    live_edges = [state for state in found if state is not None and state.status is EdgeStatus.ACTIVE]
    return STILL_WRONG if live_edges or not found else QUARANTINED


def _receipts(rows: Sequence[Mapping[str, object]], edges: frozenset[EdgeKey]) -> tuple[ReceiptSummary, ...]:
    found: list[ReceiptSummary] = []
    for row in rows:
        change = row.get("change")
        raw = cast("dict[str, object]", change).get("edge") if isinstance(change, dict) else None
        if not isinstance(raw, dict):
            continue
        parts = cast("dict[str, object]", raw)
        key = EdgeKey(int(str(parts["src"])), str(parts["rel_type"]), int(str(parts["dst"])))
        if key not in edges:
            continue
        found.append(
            ReceiptSummary(
                receipt_id=str(row["receipt_id"]),
                run_id=str(row["run_id"]),
                round=int(str(row["round"])),
                sequence=int(str(row["sequence"])),
                kind=str(row["kind"]),
                edge=None,
                digest=str(row["digest"]),
            )
        )
    return tuple(found)


def _wrong(
    fault: WrongEdge,
    names: Mapping[int, str],
    states: Mapping[EdgeKey, EdgeState],
    rows: Sequence[Mapping[str, object]],
) -> TruthFault:
    wrong = EdgeKey(fault.src, fault.rel_type.value, fault.wrong_dst)
    true = EdgeKey(fault.src, fault.rel_type.value, fault.true_dst)
    return TruthFault(
        fault_id=f"wrong-{fault.rel_type.value.lower()}-{fault.src}-{fault.wrong_dst}",
        kind=fault.kind.value,
        status=wrong_status(fault.kind, states.get(wrong), states.get(true)),
        repairable_by=REPAIR[fault.kind.value],
        planted=_edge(names, states, wrong),
        truth=_edge(names, states, true),
        other_edges=0,
        receipts=_receipts(rows, frozenset({wrong, true})),
    )


def fault_edges(live: Live) -> tuple[EdgeKey, ...]:
    faults = live.built.ingested.faults
    keys: list[EdgeKey] = []
    for fault in faults.wrong_edges:
        keys.append(EdgeKey(fault.src, fault.rel_type.value, fault.wrong_dst))
        keys.append(EdgeKey(fault.src, fault.rel_type.value, fault.true_dst))
    keys.extend(EdgeKey(f.src, f.rel_type.value, f.dst) for f in faults.missing_edges)
    for delta in (*(f.delta for f in faults.alias_duplicates), *(f.delta for f in faults.conflations)):
        keys.extend(_key(edge) for edge in (*delta.added, *delta.removed))
    return tuple(sorted(dict.fromkeys(keys)))


def build_truth(live: Live) -> TruthResponse:
    faults = live.built.ingested.faults
    names = _names(live)
    states = read_states(live.client, fault_edges(live))
    rows = tuple(cast("dict[str, object]", json.loads(line)) for line in live.journal.lines())
    found: list[TruthFault] = [_wrong(fault, names, states, rows) for fault in faults.wrong_edges]
    for missing in faults.missing_edges:
        key = EdgeKey(missing.src, missing.rel_type.value, missing.dst)
        state = states.get(key)
        found.append(
            TruthFault(
                fault_id=f"missing-{missing.rel_type.value.lower()}-{missing.src}-{missing.dst}",
                kind="missing_edge",
                status=RESTORED if state is not None and state.status is EdgeStatus.ACTIVE else STILL_WRONG,
                repairable_by=REPAIR["missing_edge"],
                planted=None,
                truth=_edge(names, states, key),
                other_edges=0,
                receipts=_receipts(rows, frozenset({key})),
            )
        )
    structural = (
        *(("alias_duplicate", f"alias-{f.duplicate_id}", f.delta) for f in faults.alias_duplicates),
        *(("conflation", f"conflation-{f.kept_id}-{f.absorbed_id}", f.delta) for f in faults.conflations),
    )
    for kind, fault_id, delta in structural:
        added = [_key(edge) for edge in delta.added]
        removed = [_key(edge) for edge in delta.removed]
        found.append(
            TruthFault(
                fault_id=fault_id,
                kind=kind,
                status=added_status(delta, states),
                repairable_by=REPAIR[kind],
                planted=_edge(names, states, added[0]) if added else None,
                truth=_edge(names, states, removed[0]) if removed else None,
                other_edges=max(0, len(added) - 1) + max(0, len(removed) - 1),
                receipts=_receipts(rows, frozenset((*added, *removed))),
            )
        )
    return TruthResponse(
        dataset="northwind_generated",
        seed=live.settings.demo_seed,
        data_version=live.built.data_version,
        counts=dict(sorted(Counter(fault.status for fault in found).items())),
        receipts_recorded=len(rows),
        faults=tuple(found),
    )


@router.get("/v1/truth", response_model=TruthResponse)
def truth(request: Request) -> TruthResponse:
    live: Live = request.app.state.live
    return build_truth(live)
