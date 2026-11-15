from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from trailmend.core.model import EdgeKey
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient, ParamValue
from trailmend.graph.ids import edge_id
from trailmend.graph.schema import ENDPOINTS, RelType
from trailmend.metaqa.world import Fact, World

MAX_BATCH = 1000

type Row = Mapping[str, int | float | str | bool]


@dataclass(frozen=True, slots=True)
class Loaded:
    nodes: int
    edges: int
    batches: int


def edge_row(key: EdgeKey, cost: float) -> Row:
    return {
        "src": key.src,
        "dst": key.dst,
        "eid": edge_id(key.rel_type, key.src, key.dst),
        "cost": cost,
        "confirms": 0,
        "blames": 0,
        "recent": "",
    }


def _chunks[T](items: Sequence[T], size: int = MAX_BATCH) -> list[Sequence[T]]:
    return [items[start : start + size] for start in range(0, len(items), size)]


def load_nodes(client: HydraClient, world: World) -> tuple[int, int]:
    written = 0
    batches = 0
    for label, names in sorted(world.names.items()):
        rows: list[Row] = [{"id": world.node(label, name), "name": name} for name in names]
        for chunk in _chunks(rows):
            params: dict[str, ParamValue] = {"rows": list(chunk)}
            client.run(q.upsert_nodes(label.value), params)
            batches += 1
        written += len(rows)
    return written, batches


def load_facts(client: HydraClient, world: World, facts: Sequence[Fact]) -> tuple[int, int]:
    grouped: dict[str, list[Row]] = defaultdict(list)
    for fact in facts:
        for key in world.edges_of(fact.triple):
            grouped[key.rel_type].append(edge_row(key, fact.cost))
    batches = 0
    for rel_type, rows in sorted(grouped.items()):
        source, target = ENDPOINTS[RelType(rel_type)]
        for chunk in _chunks(rows):
            params: dict[str, ParamValue] = {"rows": list(chunk)}
            client.run(q.upsert_edges(source.value, rel_type, target.value), params)
            batches += 1
    return sum(len(rows) for rows in grouped.values()), batches


def load_world(client: HydraClient, world: World) -> Loaded:
    nodes, node_batches = load_nodes(client, world)
    edges, edge_batches = load_facts(client, world, world.ingested)
    return Loaded(nodes, edges, node_batches + edge_batches)
