from collections.abc import Mapping, Sequence
from random import Random

from trailmend.data.documents import Document
from trailmend.data.model import Node
from trailmend.errors import ErrorCode
from trailmend.eval.plain_store import PlainStore, bm25, build_store
from trailmend.graph.schema import NodeLabel
from trailmend.loop.evaluate import Verdict
from trailmend.metaqa.answer import MqJudged
from trailmend.metaqa.sample import MqQuestion
from trailmend.metaqa.world import World, document_ids

SENTENCES: Mapping[str, tuple[str, str, str]] = {
    "directed_by": ("{m} was directed by {o}.", "{o} directed the film {m}.", "Director of {m}: {o}."),
    "written_by": ("{m} was written by {o}.", "{o} wrote the film {m}.", "Writer of {m}: {o}."),
    "starred_actors": ("{o} starred in {m}.", "{m} stars {o}.", "{o} acted in the film {m}."),
    "release_year": ("{m} was released in {o}.", "{m} came out in the year {o}.", "Release year of {m}: {o}."),
    "in_language": ("{m} is in {o}.", "The language of {m} is {o}.", "{m} was filmed in the {o} language."),
    "has_tags": ("{m} is tagged {o}.", "{o} is a tag on {m}.", "Tags of {m} include {o}."),
    "has_genre": ("{m} is a {o} film.", "The genre of {m} is {o}.", "{m} belongs to the genre {o}."),
    "has_imdb_votes": ("{m} is {o} by IMDb votes.", "IMDb votes for {m}: {o}.", "By votes, {m} is {o}."),
    "has_imdb_rating": ("{m} is rated {o} on IMDb.", "IMDb rating of {m}: {o}.", "On IMDb, {m} rates {o}."),
}


def render(world: World) -> tuple[Document, ...]:
    rng = Random(world.seed * 7_919 + 101)
    documents: list[Document] = []
    for fact in world.ingested:
        forward, _ = world.edges_of(fact.triple)
        templates = rng.sample(SENTENCES[fact.triple.relation], fact.support)
        for doc_id, template in zip(document_ids(world, fact), templates, strict=True):
            text = template.format(m=fact.triple.subject, o=fact.triple.obj)
            documents.append(Document(doc_id, "fact", text, (forward.src, forward.dst), 0))
    return tuple(documents)


def nodes_of(world: World) -> tuple[Node, ...]:
    return tuple(Node(world.node(label, name), label, name) for label, names in world.names.items() for name in names)


def store_of(world: World) -> PlainStore:
    return build_store(render(world), nodes_of(world))


def rankings(store: PlainStore, questions: Sequence[MqQuestion], deepest: int) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(doc for doc, _ in bm25(store, q.text)[:deepest]) for q in questions)


def _tally(store: PlainStore, documents: Sequence[int], expected: NodeLabel, topic: int) -> dict[int, int]:
    counts: dict[int, int] = {}
    for document_id in documents:
        for entity in store.mentions[document_id]:
            if entity != topic and store.labels.get(entity) is expected:
                counts[entity] = counts.get(entity, 0) + 1
    return counts


def judge_plain(store: PlainStore, question: MqQuestion, ranked: Sequence[int], top_k: int) -> MqJudged:
    counts = _tally(store, ranked[:top_k], question.answer_label, question.topic_id)
    if not counts:
        return MqJudged(
            question.id,
            question.qtype,
            question.hop,
            question.topic_id,
            Verdict.UNREACHABLE,
            ErrorCode.UNREACHABLE,
            (),
            question.gold,
            (),
            None,
        )
    answers = tuple(sorted(counts, key=lambda entity: (-counts[entity], entity)))
    verdict = Verdict.CORRECT if answers[0] in set(question.gold) else Verdict.WRONG
    return MqJudged(
        question.id, question.qtype, question.hop, question.topic_id, verdict, None, answers, question.gold, (), None
    )


def judge_all_plain(
    store: PlainStore, questions: Sequence[MqQuestion], ranked: Sequence[Sequence[int]], top_k: int
) -> tuple[MqJudged, ...]:
    return tuple(judge_plain(store, q, docs, top_k) for q, docs in zip(questions, ranked, strict=True))
