import json
from collections import defaultdict
from collections.abc import Container, Mapping, Sequence
from dataclasses import dataclass

from trailmend.graph.ids import entity_id
from trailmend.graph.schema import ENDPOINTS, NATURAL_KEY_KIND, NodeLabel, RelType


@dataclass(frozen=True, slots=True)
class Node:
    id: int
    label: NodeLabel
    name: str
    aliases: tuple[str, ...] = ()
    natural_key: str = ""


@dataclass(frozen=True, slots=True)
class Edge:
    id: int
    src: int
    rel_type: RelType
    dst: int


@dataclass(frozen=True, slots=True)
class TruthGraph:
    seed: int
    company: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

    def node(self, node_id: int) -> Node:
        found = self.by_id.get(node_id)
        if found is None:
            raise KeyError(f"no node with id {node_id}")
        return found

    @property
    def by_id(self) -> Mapping[int, Node]:
        return {n.id: n for n in self.nodes}

    def nodes_with_label(self, label: NodeLabel) -> tuple[Node, ...]:
        return tuple(n for n in self.nodes if n.label is label)

    def edges_of_type(self, rel_type: RelType) -> tuple[Edge, ...]:
        return tuple(e for e in self.edges if e.rel_type is rel_type)

    def out_edges(self) -> Mapping[int, tuple[Edge, ...]]:
        grouped: dict[int, list[Edge]] = defaultdict(list)
        for edge in self.edges:
            grouped[edge.src].append(edge)
        return {src: tuple(items) for src, items in grouped.items()}


@dataclass(frozen=True, slots=True)
class NodeFactory:
    seed: int

    def node(self, label: NodeLabel, slug: str, name: str, aliases: Sequence[str] = ()) -> Node:
        natural_key = f"{NATURAL_KEY_KIND[label]}:s{self.seed}-{slug}"
        return Node(entity_id(natural_key), label, name, tuple(aliases), natural_key)


def make_edge(src: Node, rel_type: RelType, dst: Node) -> Edge:
    expected_src, expected_dst = ENDPOINTS[rel_type]
    if src.label is not expected_src or dst.label is not expected_dst:
        raise ValueError(f"{rel_type} must go {expected_src}->{expected_dst}, got {src.label}->{dst.label}")
    natural_key = f"edge:{rel_type.value.lower()}-{src.id}-{dst.id}"
    return Edge(entity_id(natural_key), src.id, rel_type, dst.id)


def require_consistent(nodes: Sequence[Node], edges: Sequence[Edge]) -> None:
    node_ids = [n.id for n in nodes]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("node ids collided")
    edge_ids = [e.id for e in edges]
    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError("edge ids collided")
    labels: list[str] = [n.name for n in nodes] + [a for n in nodes for a in n.aliases]
    if len(set(labels)) != len(labels):
        raise ValueError("node names and aliases must be unique so a question can name one entity")
    known = {n.id for n in nodes}
    for edge in edges:
        if edge.src not in known or edge.dst not in known:
            raise ValueError(f"edge {edge.rel_type} points outside the graph")


def first_unused_name(candidates: Sequence[str], taken: Container[str]) -> str:
    for candidate in candidates:
        if candidate not in taken:
            return candidate
    raise ValueError(f"every candidate name is taken: {list(candidates)}")


def to_json(graph: TruthGraph) -> str:
    payload = {
        "seed": graph.seed,
        "company": graph.company,
        "nodes": [
            {
                "id": n.id,
                "label": n.label.value,
                "name": n.name,
                "aliases": list(n.aliases),
                "natural_key": n.natural_key,
            }
            for n in graph.nodes
        ],
        "edges": [{"id": e.id, "src": e.src, "rel_type": e.rel_type.value, "dst": e.dst} for e in graph.edges],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
