import json
from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from trailmend.data.doctemplates import templates_for
from trailmend.data.faultmodel import Ingested
from trailmend.data.model import Edge, TruthGraph
from trailmend.graph.ids import entity_id


@dataclass(frozen=True, slots=True)
class Document:
    id: int
    kind: str
    text: str
    mentions: tuple[int, ...]
    edge_id: int


@dataclass(frozen=True, slots=True)
class DocumentSet:
    seed: int
    ingested: tuple[Document, ...]
    pool: tuple[Document, ...]

    @property
    def all(self) -> tuple[Document, ...]:
        return self.ingested + self.pool

    def mentioning(self, entity_id_: int, *, pool_only: bool = False) -> tuple[Document, ...]:
        source = self.pool if pool_only else self.all
        return tuple(d for d in source if entity_id_ in d.mentions)


def _render(rng: Random, edge: Edge, by_id: dict[int, str]) -> Document:
    template = rng.choice(templates_for(edge.rel_type))
    text = template.text.format(src=by_id[edge.src], dst=by_id[edge.dst])
    return Document(entity_id(f"doc:{edge.id}"), template.kind, text, (edge.src, edge.dst), edge.id)


def _render_all(rng: Random, edges: Sequence[Edge], by_id: dict[int, str]) -> tuple[Document, ...]:
    return tuple(_render(rng, edge, by_id) for edge in edges)


def render(ingested: Ingested, truth: TruthGraph) -> DocumentSet:
    rng = Random(ingested.graph.seed * 7_919 + 101)
    by_id = {n.id: n.name for n in ingested.graph.nodes}
    for node in truth.nodes:
        by_id.setdefault(node.id, node.name)
    documents = _render_all(rng, ingested.graph.edges, by_id)
    pool = _render_all(rng, ingested.pool, by_id)
    ids = [d.id for d in documents + pool]
    if len(set(ids)) != len(ids):
        raise ValueError("document ids collided")
    return DocumentSet(ingested.graph.seed, documents, pool)


def to_json(documents: DocumentSet) -> str:
    def rows(items: tuple[Document, ...]) -> list[dict[str, object]]:
        return [
            {"id": d.id, "kind": d.kind, "text": d.text, "mentions": list(d.mentions), "edge_id": d.edge_id}
            for d in items
        ]

    payload = {"seed": documents.seed, "ingested": rows(documents.ingested), "pool": rows(documents.pool)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
