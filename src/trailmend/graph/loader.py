import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from trailmend.data.model import Edge, Node, TruthGraph
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient, ParamValue
from trailmend.graph.schema import ENDPOINTS, NodeLabel, RelType

INITIAL_COST = 1.0
MAX_BATCH = 1000

type Row = Mapping[str, int | float | str | bool]


@dataclass(frozen=True, slots=True)
class LoadReport:
    seed: int
    nodes_written: int
    edges_written: int
    batches: int
    node_counts: Mapping[str, int]
    edge_counts: Mapping[str, int]
    seconds: float


def _chunks[T](items: Sequence[T], size: int) -> list[Sequence[T]]:
    return [items[start : start + size] for start in range(0, len(items), size)]


def _node_rows(nodes: Sequence[Node]) -> list[Row]:
    return [{"id": n.id, "name": n.name} for n in nodes]


def _edge_rows(edges: Sequence[Edge]) -> list[Row]:
    return [
        {"src": e.src, "dst": e.dst, "eid": e.id, "cost": INITIAL_COST, "confirms": 0, "blames": 0, "recent": ""}
        for e in edges
    ]


def _grouped_nodes(graph: TruthGraph) -> dict[NodeLabel, list[Node]]:
    grouped: dict[NodeLabel, list[Node]] = defaultdict(list)
    for node in graph.nodes:
        grouped[node.label].append(node)
    return grouped


def _grouped_edges(graph: TruthGraph) -> dict[RelType, list[Edge]]:
    grouped: dict[RelType, list[Edge]] = defaultdict(list)
    for edge in graph.edges:
        grouped[edge.rel_type].append(edge)
    return grouped


def _read_count(client: HydraClient, query: q.NamedQuery) -> int:
    rows = client.run(query).rows
    if len(rows) != 1 or not isinstance(rows[0][0], int):
        raise ValueError(f"{query.name} did not return one integer, got {rows!r}")
    return rows[0][0]


def count_graph(client: HydraClient, graph: TruthGraph) -> tuple[dict[str, int], dict[str, int]]:
    nodes = {label.value: _read_count(client, q.count_nodes(label.value)) for label in sorted(_grouped_nodes(graph))}
    edges = {
        rel_type.value: _read_count(client, q.count_edges(rel_type.value)) for rel_type in sorted(_grouped_edges(graph))
    }
    return nodes, edges


def load(
    client: HydraClient,
    graph: TruthGraph,
    batch_size: int = MAX_BATCH,
    clock: Callable[[], float] = time.monotonic,
) -> LoadReport:
    if not 1 <= batch_size <= MAX_BATCH:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH}")
    started = clock()
    batches = 0
    for label, nodes in sorted(_grouped_nodes(graph).items()):
        for chunk in _chunks(nodes, batch_size):
            params: dict[str, ParamValue] = {"rows": _node_rows(chunk)}
            client.run(q.upsert_nodes(label.value), params)
            batches += 1
    for rel_type, edges in sorted(_grouped_edges(graph).items()):
        source, target = ENDPOINTS[rel_type]
        for chunk in _chunks(edges, batch_size):
            params = {"rows": _edge_rows(chunk)}
            client.run(q.upsert_edges(source.value, rel_type.value, target.value), params)
            batches += 1
    seconds = clock() - started
    node_counts, edge_counts = count_graph(client, graph)
    return LoadReport(graph.seed, len(graph.nodes), len(graph.edges), batches, node_counts, edge_counts, seconds)
