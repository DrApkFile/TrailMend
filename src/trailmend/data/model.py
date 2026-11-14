import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
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


def make_node(label: NodeLabel, slug: str, name: str, aliases: Sequence[str] = ()) -> Node:
    natural_key = f"{NATURAL_KEY_KIND[label]}:{slug}"
    return Node(entity_id(natural_key), label, name, tuple(aliases), natural_key)


def make_edge(src: Node, rel_type: RelType, dst: Node) -> Edge:
    expected_src, expected_dst = ENDPOINTS[rel_type]
    if src.label is not expected_src or dst.label is not expected_dst:
        raise ValueError(f"{rel_type} must go {expected_src}->{expected_dst}, got {src.label}->{dst.label}")
    natural_key = f"edge:{rel_type.value.lower()}-{src.id}-{dst.id}"
    return Edge(entity_id(natural_key), src.id, rel_type, dst.id)


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
