import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from random import Random

from trailmend.data.model import TruthGraph
from trailmend.data.qtemplates import TEMPLATES, QuestionTemplate
from trailmend.graph.schema import NodeLabel, RelType

type Adjacency = Mapping[tuple[int, RelType], tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    template: str
    text: str
    seed_entity_id: int
    seed_entity_name: str
    answer_label: NodeLabel
    hops: int
    gold: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class QuestionSet:
    seed: int
    questions: tuple[Question, ...]

    def of_template(self, name: str) -> tuple[Question, ...]:
        return tuple(q for q in self.questions if q.template == name)


def adjacency(graph: TruthGraph) -> Adjacency:
    grouped: dict[tuple[int, RelType], list[int]] = defaultdict(list)
    for edge in graph.edges:
        grouped[(edge.src, edge.rel_type)].append(edge.dst)
    return {key: tuple(sorted(targets)) for key, targets in grouped.items()}


def follow(links: Adjacency, start: int, rel_path: tuple[RelType, ...]) -> tuple[int, ...]:
    frontier = (start,)
    for rel_type in rel_path:
        nxt: list[int] = []
        for node_id in frontier:
            nxt.extend(links.get((node_id, rel_type), ()))
        frontier = tuple(dict.fromkeys(nxt))
        if not frontier:
            return ()
    return tuple(sorted(frontier))


def _questions_for(rng: Random, truth: TruthGraph, links: Adjacency, spec: QuestionTemplate) -> tuple[Question, ...]:
    seeds = sorted(truth.nodes_with_label(spec.seed_label), key=lambda n: n.id)
    rng.shuffle(seeds)
    built: list[Question] = []
    for node in seeds:
        if len(built) == spec.cap:
            break
        gold = follow(links, node.id, spec.rel_path)
        if not gold or (spec.single_answer and len(gold) != 1):
            continue
        built.append(
            Question(
                f"q-{spec.name}-{node.id}",
                spec.name,
                spec.text.format(seed=node.name),
                node.id,
                node.name,
                spec.answer_label,
                spec.hops,
                gold,
            )
        )
    return tuple(sorted(built, key=lambda q: q.id))


def build(truth: TruthGraph) -> QuestionSet:
    rng = Random(truth.seed * 31_337 + 7)
    links = adjacency(truth)
    questions: list[Question] = []
    for spec in TEMPLATES:
        questions.extend(_questions_for(rng, truth, links, spec))
    ids = [q.id for q in questions]
    if len(set(ids)) != len(ids):
        raise ValueError("question ids collided")
    by_id = truth.by_id
    for question in questions:
        for answer in question.gold:
            if by_id[answer].label is not question.answer_label:
                raise ValueError(f"{question.id} has a gold answer of the wrong label")
    return QuestionSet(truth.seed, tuple(questions))


def to_json(questions: QuestionSet) -> str:
    payload = {
        "seed": questions.seed,
        "questions": [
            {
                "id": q.id,
                "template": q.template,
                "text": q.text,
                "seed_entity_id": q.seed_entity_id,
                "seed_entity_name": q.seed_entity_name,
                "answer_label": q.answer_label.value,
                "hops": q.hops,
                "gold": list(q.gold),
            }
            for q in questions.questions
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
