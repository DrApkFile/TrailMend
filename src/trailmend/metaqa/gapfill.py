from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from trailmend.core.model import EdgeKey, EdgeState, Fill, MendConfig
from trailmend.core.receipts import Receipt
from trailmend.graph.client import HydraClient
from trailmend.loop.apply import apply
from trailmend.loop.evaluate import Verdict
from trailmend.loop.journal import Journal
from trailmend.metaqa.answer import MqJudged
from trailmend.metaqa.kb import Triple
from trailmend.metaqa.sample import MqQuestion
from trailmend.metaqa.world import Fact, World, document_ids

GAPFILL_ORIGIN = "gapfill"


@dataclass(slots=True)
class LiveGraph:
    world: World
    out: dict[tuple[int, str], set[int]] = field(default_factory=lambda: defaultdict(set))
    pool: dict[tuple[int, str], list[tuple[int, Fact]]] = field(default_factory=lambda: defaultdict(list))
    filled: set[Triple] = field(default_factory=set[Triple])
    first_before: dict[EdgeKey, EdgeState] = field(default_factory=dict[EdgeKey, EdgeState])

    @classmethod
    def of(cls, world: World) -> "LiveGraph":
        live = cls(world)
        for fact in world.ingested:
            for key in world.edges_of(fact.triple):
                live.out[(key.src, key.rel_type)].add(key.dst)
        for fact in world.pool:
            for key in world.edges_of(fact.triple):
                live.pool[(key.src, key.rel_type)].append((key.dst, fact))
        return live

    def remember(self, before: EdgeState) -> None:
        self.first_before.setdefault(before.key, before)

    def path_edges(self, question: MqQuestion) -> set[EdgeKey]:
        found: set[EdgeKey] = set()

        def walk(node: int, hop: int, seen: tuple[int, ...], trail: tuple[EdgeKey, ...]) -> None:
            if hop == len(question.rel_path):
                found.update(trail)
                return
            rel_type = question.rel_path[hop]
            for target in sorted(self.out.get((node, rel_type), ())):
                if target not in seen:
                    walk(target, hop + 1, (*seen, target), (*trail, EdgeKey(node, rel_type, target)))

        walk(question.topic_id, 0, (question.topic_id,), ())
        return found


def facts_along(live: LiveGraph, question: MqQuestion) -> tuple[Fact, ...]:
    chosen: dict[Triple, Fact] = {}
    frontier: set[int] = {question.topic_id}
    for rel_type in question.rel_path:
        reached: set[int] = set()
        for node in sorted(frontier):
            reached.update(live.out.get((node, rel_type), ()))
            for target, fact in live.pool.get((node, rel_type), ()):
                reached.add(target)
                if fact.triple not in live.filled:
                    chosen.setdefault(fact.triple, fact)
        frontier = reached - {question.topic_id}
        if not frontier:
            break
    return tuple(chosen[triple] for triple in sorted(chosen))


def is_gap(judged: MqJudged) -> bool:
    return judged.verdict in (Verdict.WRONG, Verdict.UNREACHABLE)


@dataclass(frozen=True, slots=True)
class Filled:
    gaps: int
    facts: tuple[Fact, ...]
    receipts: tuple[Receipt, ...]


def run_gapfill(
    client: HydraClient,
    journal: Journal,
    run_id: str,
    round_index: int,
    first_sequence: int,
    live: LiveGraph,
    questions: Sequence[MqQuestion],
    judged: Sequence[MqJudged],
    config: MendConfig,
) -> Filled:
    gaps = [question for question, verdict in zip(questions, judged, strict=True) if is_gap(verdict)]
    wanted: dict[Triple, Fact] = {}
    for question in gaps:
        for fact in facts_along(live, question):
            wanted.setdefault(fact.triple, fact)
    receipts: list[Receipt] = []
    for triple in sorted(wanted):
        fact = wanted[triple]
        documents = document_ids(live.world, fact)
        for key in live.world.edges_of(triple):
            done = apply(
                client,
                journal,
                run_id,
                round_index,
                first_sequence + len(receipts),
                Fill(key, documents, fact.cost),
                config,
                GAPFILL_ORIGIN,
            )
            live.remember(done.before)
            live.out[(key.src, key.rel_type)].add(key.dst)
            receipts.append(done.receipt)
        live.filled.add(triple)
    return Filled(len(gaps), tuple(wanted[triple] for triple in sorted(wanted)), tuple(receipts))
