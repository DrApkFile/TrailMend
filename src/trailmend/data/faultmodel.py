import json
from dataclasses import dataclass
from enum import StrEnum

from trailmend.data.model import Edge, Node, TruthGraph
from trailmend.graph.schema import RelType

V1 = "v1"
V2 = "v2"
DATA_VERSIONS: tuple[str, ...] = (V1, V2)


class WrongKind(StrEnum):
    CONTRADICTED = "contradicted"
    RECOVERABLE = "recoverable"
    DESTROYED = "destroyed"


@dataclass(frozen=True, slots=True)
class EdgeDelta:
    removed: tuple[Edge, ...] = ()
    added: tuple[Edge, ...] = ()


@dataclass(frozen=True, slots=True)
class WrongEdge:
    rel_type: RelType
    src: int
    true_dst: int
    wrong_dst: int
    delta: EdgeDelta
    kind: WrongKind = WrongKind.DESTROYED

    @property
    def wrong_key(self) -> tuple[int, RelType, int]:
        return (self.src, self.rel_type, self.wrong_dst)

    @property
    def true_key(self) -> tuple[int, RelType, int]:
        return (self.src, self.rel_type, self.true_dst)


@dataclass(frozen=True, slots=True)
class MissingEdge:
    rel_type: RelType
    src: int
    dst: int
    delta: EdgeDelta


@dataclass(frozen=True, slots=True)
class AliasDuplicate:
    original_id: int
    duplicate_id: int
    duplicate_name: str
    delta: EdgeDelta


@dataclass(frozen=True, slots=True)
class ConflatedPerson:
    kept_id: int
    absorbed_id: int
    kept_name: str
    absorbed_name: str
    delta: EdgeDelta


@dataclass(frozen=True, slots=True)
class FaultSet:
    seed: int
    wrong_edges: tuple[WrongEdge, ...]
    missing_edges: tuple[MissingEdge, ...]
    alias_duplicates: tuple[AliasDuplicate, ...]
    conflations: tuple[ConflatedPerson, ...]
    data_version: str = V1

    def __post_init__(self) -> None:
        if self.data_version not in DATA_VERSIONS:
            raise ValueError(f"unknown data_version {self.data_version!r}")

    def wrong_of_kind(self, kind: WrongKind) -> tuple[WrongEdge, ...]:
        return tuple(f for f in self.wrong_edges if f.kind is kind)

    @property
    def deltas(self) -> tuple[EdgeDelta, ...]:
        return (
            tuple(f.delta for f in self.wrong_edges)
            + tuple(f.delta for f in self.missing_edges)
            + tuple(f.delta for f in self.alias_duplicates)
            + tuple(f.delta for f in self.conflations)
        )

    def removed_edges(self) -> tuple[Edge, ...]:
        return tuple(e for delta in self.deltas for e in delta.removed)

    def added_edges(self) -> tuple[Edge, ...]:
        return tuple(e for delta in self.deltas for e in delta.added)


@dataclass(frozen=True, slots=True)
class Ingested:
    graph: TruthGraph
    pool: tuple[Edge, ...]
    faults: FaultSet
    added_nodes: tuple[Node, ...]
    removed_nodes: tuple[Node, ...]


def replay(truth: TruthGraph, faults: FaultSet) -> tuple[Edge, ...]:
    edges = {(e.src, e.rel_type, e.dst): e for e in truth.edges}
    for delta in faults.deltas:
        for edge in delta.removed:
            key = (edge.src, edge.rel_type, edge.dst)
            if key not in edges:
                raise KeyError(f"declared removal of an edge that is not there: {key}")
            del edges[key]
        for edge in delta.added:
            edges[(edge.src, edge.rel_type, edge.dst)] = edge
    return tuple(edges.values())


def _edge_rows(edges: tuple[Edge, ...]) -> list[dict[str, object]]:
    return [{"id": e.id, "src": e.src, "rel_type": e.rel_type.value, "dst": e.dst} for e in edges]


def _delta_row(delta: EdgeDelta) -> dict[str, object]:
    return {"removed": _edge_rows(delta.removed), "added": _edge_rows(delta.added)}


def _wrong_row(fault: WrongEdge, data_version: str) -> dict[str, object]:
    row: dict[str, object] = {
        "rel_type": fault.rel_type.value,
        "src": fault.src,
        "true_dst": fault.true_dst,
        "wrong_dst": fault.wrong_dst,
        "delta": _delta_row(fault.delta),
    }
    if data_version != V1:
        row["kind"] = fault.kind.value
    return row


def to_json(faults: FaultSet) -> str:
    payload: dict[str, object] = {
        "seed": faults.seed,
        "wrong_edges": [_wrong_row(f, faults.data_version) for f in faults.wrong_edges],
        "missing_edges": [
            {"rel_type": f.rel_type.value, "src": f.src, "dst": f.dst, "delta": _delta_row(f.delta)}
            for f in faults.missing_edges
        ],
        "alias_duplicates": [
            {
                "original_id": f.original_id,
                "duplicate_id": f.duplicate_id,
                "duplicate_name": f.duplicate_name,
                "delta": _delta_row(f.delta),
            }
            for f in faults.alias_duplicates
        ],
        "conflations": [
            {
                "kept_id": f.kept_id,
                "absorbed_id": f.absorbed_id,
                "kept_name": f.kept_name,
                "absorbed_name": f.absorbed_name,
                "delta": _delta_row(f.delta),
            }
            for f in faults.conflations
        ],
    }
    if faults.data_version != V1:
        payload["data_version"] = faults.data_version
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
