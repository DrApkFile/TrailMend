from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from trailmend.graph.schema import NodeLabel
from trailmend.metaqa.kb import KnowledgeBase
from trailmend.metaqa.questions import DEV, TEST, RawQuestion, read_split
from trailmend.metaqa.world import World

PERSON_RELATIONS: frozenset[str] = frozenset({"directed_by", "written_by", "starred_actors"})


@dataclass(frozen=True, slots=True)
class SamplePlan:
    region_movies: int
    train: int
    held_out: int

    def __post_init__(self) -> None:
        if self.region_movies < 1 or self.train < 1 or self.held_out < 1:
            raise ValueError("region and sample sizes must be positive")


@dataclass(frozen=True, slots=True)
class MqQuestion:
    id: str
    qtype: str
    hop: int
    text: str
    topic_id: int
    topic_name: str
    rel_path: tuple[str, ...]
    answer_label: NodeLabel
    gold: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Region:
    start: str
    movies: frozenset[str]
    people: frozenset[str]

    def holds(self, question: RawQuestion) -> bool:
        if question.topic_label is NodeLabel.MQ_MOVIE:
            return question.topic in self.movies
        return question.topic_label is NodeLabel.MQ_PERSON and question.topic in self.people


@dataclass(frozen=True, slots=True)
class Workload:
    region: Region
    eligible_train: int
    eligible_held_out: int
    dropped_shared_pairs: int
    train: tuple[MqQuestion, ...]
    held_out: tuple[MqQuestion, ...]


def _people_links(kb: KnowledgeBase) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    cast: dict[str, list[str]] = defaultdict(list)
    films: dict[str, list[str]] = defaultdict(list)
    for triple in sorted(kb.triples):
        if triple.relation in PERSON_RELATIONS:
            cast[triple.subject].append(triple.obj)
            films[triple.obj].append(triple.subject)
    return cast, films


def grow_region(kb: KnowledgeBase, rng: Random, cap: int) -> Region:
    cast, films = _people_links(kb)
    movies = sorted(cast)
    for _ in range(50):
        start = rng.choice(movies)
        order = [start]
        seen = {start}
        cursor = 0
        while cursor < len(order) and len(order) < cap:
            for person in cast[order[cursor]]:
                for movie in films[person]:
                    if movie not in seen and len(order) < cap:
                        seen.add(movie)
                        order.append(movie)
            cursor += 1
        if len(order) == cap:
            people = frozenset(person for movie in order for person in cast[movie])
            return Region(start, frozenset(order), people)
    raise ValueError(f"no start movie grew a region of {cap} movies")


def stratified(rng: Random, questions: Sequence[RawQuestion], size: int) -> tuple[RawQuestion, ...]:
    if len(questions) < size:
        raise ValueError(f"asked for {size} questions, only {len(questions)} are eligible")
    strata: dict[tuple[int, str], list[RawQuestion]] = defaultdict(list)
    for question in questions:
        strata[(question.hop, question.qtype)].append(question)
    exact = {key: size * len(items) / len(questions) for key, items in strata.items()}
    taken = {key: int(share) for key, share in exact.items()}
    by_remainder = sorted(strata, key=lambda key: (-(exact[key] - taken[key]), key))
    for key in by_remainder[: size - sum(taken.values())]:
        taken[key] += 1
    picked: list[RawQuestion] = []
    for key in sorted(strata):
        picked.extend(rng.sample(sorted(strata[key], key=lambda q: q.id), taken[key]))
    return tuple(sorted(picked, key=lambda q: q.id))


def _resolve(world: World, question: RawQuestion) -> MqQuestion:
    return MqQuestion(
        question.id,
        question.qtype,
        question.hop,
        question.text,
        world.node(question.topic_label, question.topic),
        question.topic,
        tuple(rel.value for rel in question.rel_path),
        question.answer_label,
        tuple(sorted(world.node(question.answer_label, name) for name in dict.fromkeys(question.answers))),
    )


def build_workload(kb: KnowledgeBase, world: World, plan: SamplePlan) -> Workload:
    rng = Random(world.seed * 7_919 + 5)
    region = grow_region(kb, rng, plan.region_movies)
    dev = [q for q in read_split(DEV) if region.holds(q)]
    test = [q for q in read_split(TEST) if region.holds(q)]
    train = stratified(rng, dev, plan.train)
    asked = {(q.topic_label, q.topic, q.qtype) for q in train}
    fresh = [q for q in test if (q.topic_label, q.topic, q.qtype) not in asked]
    held_out = stratified(rng, fresh, plan.held_out)
    return Workload(
        region,
        len(dev),
        len(test),
        len(test) - len(fresh),
        tuple(_resolve(world, q) for q in train),
        tuple(_resolve(world, q) for q in held_out),
    )
