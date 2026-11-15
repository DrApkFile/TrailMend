from collections.abc import Callable, Sequence
from dataclasses import dataclass

from trailmend.core.ingest import MIN_SUPPORT, ingest_cost
from trailmend.core.model import EdgeKey, EdgeState, EdgeStatus
from trailmend.data.dataset import Dataset
from trailmend.data.faultmodel import EdgeDelta, WrongKind
from trailmend.data.model import Node
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient, ParamValue
from trailmend.graph.ids import edge_id
from trailmend.graph.state import read_state, write_state

INGEST = "ingest"


def _key(src: int, rel_type: str, dst: int) -> EdgeKey:
    return EdgeKey(src, rel_type, dst)


def _quarantine(client: HydraClient, key: EdgeKey) -> bool:
    before = read_state(client, key)
    if before is None or before.status is not EdgeStatus.ACTIVE:
        return False
    after = EdgeState(key, before.cost, EdgeStatus.QUARANTINED, before.confirms, before.blames, before.recent)
    write_state(client, before, after, edge_id(key.rel_type, key.src, key.dst))
    return True


def ingest_cost_of(built: Dataset, key: EdgeKey) -> float:
    return ingest_cost(built.documents.pool_support.get(edge_id(key.rel_type, key.src, key.dst), MIN_SUPPORT))


def _add(client: HydraClient, key: EdgeKey, cost: float) -> bool:
    if read_state(client, key) is not None:
        return False
    before = EdgeState(key, 0.0, EdgeStatus.ABSENT)
    after = EdgeState(key, cost, EdgeStatus.ACTIVE)
    write_state(client, before, after, edge_id(key.rel_type, key.src, key.dst), INGEST)
    return True


def _drop(client: HydraClient, key: EdgeKey) -> bool:
    before = read_state(client, key)
    if before is None:
        return False
    write_state(client, before, EdgeState(key, before.cost, EdgeStatus.ABSENT), edge_id(key.rel_type, key.src, key.dst))
    return True


def _add_node(client: HydraClient, node: Node) -> None:
    params: dict[str, ParamValue] = {"rows": [{"id": node.id, "name": node.name}]}
    client.run(q.upsert_nodes(node.label.value), params)


def _undo(client: HydraClient, built: Dataset, deltas: Sequence[EdgeDelta]) -> tuple[int, int]:
    dropped = sum(_drop(client, _key(e.src, e.rel_type.value, e.dst)) for delta in deltas for e in delta.added)
    added = 0
    for delta in deltas:
        for edge in delta.removed:
            key = _key(edge.src, edge.rel_type.value, edge.dst)
            added += _add(client, key, ingest_cost_of(built, key))
    return dropped, added


def quarantine_contradicted_wrong_edges(client: HydraClient, built: Dataset) -> dict[str, object]:
    faults = built.ingested.faults.wrong_of_kind(WrongKind.CONTRADICTED)
    done = sum(_quarantine(client, _key(f.src, f.rel_type.value, f.wrong_dst)) for f in faults)
    return {"contradicted_wrong_edges": len(faults), "quarantined": done}


def quarantine_planted_wrong_edges(client: HydraClient, built: Dataset) -> dict[str, object]:
    done = sum(
        _quarantine(client, _key(f.src, f.rel_type.value, f.wrong_dst)) for f in built.ingested.faults.wrong_edges
    )
    return {"planted_wrong_edges": len(built.ingested.faults.wrong_edges), "quarantined": done}


def ingest_withheld_edges(client: HydraClient, built: Dataset) -> dict[str, object]:
    done = 0
    for edge in built.ingested.pool:
        key = _key(edge.src, edge.rel_type.value, edge.dst)
        done += _add(client, key, ingest_cost_of(built, key))
    return {"pool_edges": len(built.ingested.pool), "ingested": done}


def merge_alias_duplicates(client: HydraClient, built: Dataset) -> dict[str, object]:
    dropped, added = _undo(client, built, [f.delta for f in built.ingested.faults.alias_duplicates])
    return {"duplicates": len(built.ingested.faults.alias_duplicates), "edges_moved_back": added, "dropped": dropped}


def split_conflated_people(client: HydraClient, built: Dataset) -> dict[str, object]:
    for node in built.ingested.removed_nodes:
        _add_node(client, node)
    dropped, added = _undo(client, built, [f.delta for f in built.ingested.faults.conflations])
    return {
        "conflations": len(built.ingested.faults.conflations),
        "people_restored": len(built.ingested.removed_nodes),
        "edges_restored": added,
        "dropped": dropped,
    }


@dataclass(frozen=True, slots=True)
class Stage:
    name: str
    claim: str
    repair: Callable[[HydraClient, Dataset], dict[str, object]] | None
    nodes_known: str


LADDER: tuple[Stage, ...] = (
    Stage("g0", "the ingested graph, no repair at all: this is round 0 of every arm", None, "ingested"),
    Stage(
        "quarantine_contradicted_wrong_edges",
        "every stale edge that still has its true rival in the graph quarantined, which is the most reweight alone "
        "could ever achieve",
        quarantine_contradicted_wrong_edges,
        "ingested",
    ),
    Stage(
        "quarantine_planted_wrong_edges",
        "every planted wrong edge quarantined, which is the most the quarantine mechanism could ever achieve",
        quarantine_planted_wrong_edges,
        "ingested",
    ),
    Stage(
        "and_ingest_withheld_edges",
        "and every withheld edge ingested, which is the most gap-fill could ever achieve",
        ingest_withheld_edges,
        "ingested",
    ),
    Stage(
        "and_merge_alias_duplicates",
        "and every duplicated service merged back, which no mechanism in this build can do",
        merge_alias_duplicates,
        "ingested",
    ),
    Stage(
        "and_split_conflated_people",
        "and every conflated person split again: the graph is now the truth graph, so this is the data's ceiling",
        split_conflated_people,
        "truth",
    ),
)


def nodes_for(stage: Stage, built: Dataset) -> tuple[Node, ...]:
    return built.truth.nodes if stage.nodes_known == "truth" else built.graph.nodes
