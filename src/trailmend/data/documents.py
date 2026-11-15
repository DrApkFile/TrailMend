import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

from trailmend.data.doctemplates import Template, templates_for
from trailmend.data.faultmodel import V1, FaultSet, Ingested, WrongKind
from trailmend.data.model import Edge, TruthGraph
from trailmend.data.support import CONTRADICTED_SUPPORT, SupportPlan, draw, draw_stale
from trailmend.graph.ids import edge_id, entity_id


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

    @property
    def ingested_support(self) -> Mapping[int, int]:
        return support_of(self.ingested)

    @property
    def pool_support(self) -> Mapping[int, int]:
        return support_of(self.pool)


def support_of(documents: Sequence[Document]) -> Mapping[int, int]:
    return Counter(d.edge_id for d in documents)


def _as(template: Template, edge: Edge, by_id: dict[int, str], copy: int) -> Document:
    slug = f"doc:{edge.id}" if copy == 0 else f"doc:{edge.id}-c{copy}"
    text = template.text.format(src=by_id[edge.src], dst=by_id[edge.dst])
    return Document(entity_id(slug), template.kind, text, (edge.src, edge.dst), edge.id)


def _render(rng: Random, edge: Edge, by_id: dict[int, str]) -> Document:
    return _as(rng.choice(templates_for(edge.rel_type)), edge, by_id, 0)


def _render_all(rng: Random, edges: Sequence[Edge], by_id: dict[int, str]) -> tuple[Document, ...]:
    return tuple(_render(rng, edge, by_id) for edge in edges)


def _stale_and_current(faults: FaultSet) -> tuple[frozenset[int], frozenset[int]]:
    contradicted = faults.wrong_of_kind(WrongKind.CONTRADICTED)
    stale = {edge_id(f.rel_type.value, f.src, f.wrong_dst) for f in contradicted}
    current = {edge_id(f.rel_type.value, f.src, f.true_dst) for f in contradicted}
    return frozenset(stale), frozenset(current)


def _support(
    rng: Random, edges: Sequence[Edge], plan: SupportPlan, stale: frozenset[int], current: frozenset[int]
) -> dict[int, int]:
    counts: dict[int, int] = {}
    for edge in edges:
        if edge.id in stale:
            counts[edge.id] = draw_stale(rng, plan)
        elif edge.id in current:
            counts[edge.id] = CONTRADICTED_SUPPORT
        else:
            counts[edge.id] = draw(rng, plan)
    return counts


def _render_supported(
    rng: Random, edges: Sequence[Edge], by_id: dict[int, str], support: Mapping[int, int]
) -> tuple[Document, ...]:
    rendered: list[Document] = []
    for edge in edges:
        choices = templates_for(edge.rel_type)
        wanted = support[edge.id]
        if wanted > len(choices):
            raise ValueError(f"{edge.rel_type} has {len(choices)} templates, cannot support {wanted} documents")
        for copy, template in enumerate(rng.sample(choices, wanted)):
            rendered.append(_as(template, edge, by_id, copy))
    return tuple(rendered)


def render(ingested: Ingested, truth: TruthGraph, plan: SupportPlan | None = None) -> DocumentSet:
    rng = Random(ingested.graph.seed * 7_919 + 101)
    by_id = {n.id: n.name for n in ingested.graph.nodes}
    for node in truth.nodes:
        by_id.setdefault(node.id, node.name)
    if ingested.faults.data_version == V1:
        documents = _render_all(rng, ingested.graph.edges, by_id)
        pool = _render_all(rng, ingested.pool, by_id)
    else:
        settings = plan or SupportPlan()
        stale, current = _stale_and_current(ingested.faults)
        graph_support = _support(rng, ingested.graph.edges, settings, stale, current)
        pool_support = _support(rng, ingested.pool, settings, frozenset(), frozenset())
        documents = _render_supported(rng, ingested.graph.edges, by_id, graph_support)
        pool = _render_supported(rng, ingested.pool, by_id, pool_support)
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
