import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

from trailmend.core.ingest import ingest_cost
from trailmend.core.model import EdgeKey
from trailmend.data.faultmodel import WrongKind
from trailmend.data.faults import FaultPlan, wrong_kinds
from trailmend.data.support import CONTRADICTED_SUPPORT, SupportPlan, draw, draw_stale
from trailmend.graph.ids import entity_id
from trailmend.graph.schema import NodeLabel
from trailmend.metaqa.kb import KnowledgeBase, Triple, node_id, reverse_of

HALF_SHARE = 0.5
KB_ORIGIN = "kb"
PLANTED_ORIGIN = "planted"


@dataclass(frozen=True, slots=True)
class Fact:
    triple: Triple
    support: int
    origin: str = KB_ORIGIN

    @property
    def cost(self) -> float:
        return ingest_cost(self.support)


@dataclass(frozen=True, slots=True)
class WrongFact:
    kind: WrongKind
    true: Triple
    wrong: Triple


@dataclass(frozen=True, slots=True)
class World:
    seed: int
    kb_lines: int
    kb_triples: int
    ingested: tuple[Fact, ...]
    pool: tuple[Fact, ...]
    faults: tuple[WrongFact, ...]
    names: Mapping[NodeLabel, tuple[str, ...]]

    @property
    def scope(self) -> str:
        return f"s{self.seed}"

    def node(self, label: NodeLabel, name: str) -> int:
        return node_id(self.scope, label, name)

    def edges_of(self, triple: Triple) -> tuple[EdgeKey, EdgeKey]:
        subject = self.node(NodeLabel.MQ_MOVIE, triple.subject)
        obj = self.node(triple.object_label, triple.obj)
        forward = triple.rel_type
        return EdgeKey(subject, forward.value, obj), EdgeKey(obj, reverse_of(forward).value, subject)

    def faults_of_kind(self, kind: WrongKind) -> tuple[WrongFact, ...]:
        return tuple(f for f in self.faults if f.kind is kind)


def _wrong_object(rng: Random, triple: Triple, candidates: Sequence[str], true_objects: frozenset[str]) -> str:
    for _ in range(1000):
        picked = rng.choice(candidates)
        if picked not in true_objects:
            return picked
    raise ValueError(f"no wrong object found for {triple}")


def build_world(
    kb: KnowledgeBase, seed: int, plan: FaultPlan | None = None, support: SupportPlan | None = None
) -> World:
    faults_plan = plan or FaultPlan()
    support_plan = support or SupportPlan()
    rng = Random(seed * 1_000_003 + 23)
    ordered = sorted(kb.triples)
    kept = frozenset(rng.sample(range(len(ordered)), round(len(ordered) * HALF_SHARE)))
    half = [t for i, t in enumerate(ordered) if i in kept]
    withheld = [t for i, t in enumerate(ordered) if i not in kept]
    names = {label: kb.names_of(label) for label in NodeLabel if label.value.startswith("Mq")}
    true_objects: dict[tuple[str, str], set[str]] = defaultdict(set)
    for triple in ordered:
        true_objects[(triple.subject, triple.relation)].add(triple.obj)

    chosen = sorted(rng.sample(half, max(1, round(len(half) * faults_plan.wrong_edge_share))))
    kinds = wrong_kinds(rng, len(chosen), faults_plan)
    faults: list[WrongFact] = []
    for triple, kind in zip(chosen, kinds, strict=True):
        wrong_obj = _wrong_object(
            rng, triple, names[triple.object_label], frozenset(true_objects[(triple.subject, triple.relation)])
        )
        true_objects[(triple.subject, triple.relation)].add(wrong_obj)
        faults.append(WrongFact(kind, triple, Triple(triple.subject, triple.relation, wrong_obj)))

    removed = {f.true for f in faults if f.kind is not WrongKind.CONTRADICTED}
    current = {f.true for f in faults if f.kind is WrongKind.CONTRADICTED}
    stale = {f.wrong for f in faults if f.kind is WrongKind.CONTRADICTED}
    recovered = sorted(f.true for f in faults if f.kind is WrongKind.RECOVERABLE)

    ingested: list[Fact] = []
    for triple in half:
        if triple in removed:
            continue
        count = CONTRADICTED_SUPPORT if triple in current else draw(rng, support_plan)
        ingested.append(Fact(triple, count))
    for fault in faults:
        count = draw_stale(rng, support_plan) if fault.wrong in stale else draw(rng, support_plan)
        ingested.append(Fact(fault.wrong, count, PLANTED_ORIGIN))
    pool = [Fact(triple, draw(rng, support_plan)) for triple in sorted([*withheld, *recovered])]
    return World(seed, kb.lines, len(ordered), tuple(ingested), tuple(pool), tuple(faults), names)


def faults_json(world: World) -> str:
    def row(triple: Triple) -> list[str]:
        return [triple.subject, triple.relation, triple.obj]

    payload = {
        "dataset": "metaqa",
        "seed": world.seed,
        "rule": "v2",
        "counts": {kind.value: len(world.faults_of_kind(kind)) for kind in WrongKind},
        "wrong_edges": [{"kind": f.kind.value, "true": row(f.true), "wrong": row(f.wrong)} for f in world.faults],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def document_ids(world: World, fact: Fact) -> tuple[int, ...]:
    forward, _ = world.edges_of(fact.triple)
    return tuple(
        entity_id(f"doc:{world.scope}-{forward.rel_type.lower()}-{forward.src}-{forward.dst}-c{copy}")
        for copy in range(fact.support)
    )
