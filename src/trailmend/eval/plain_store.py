import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from trailmend.data.documents import Document
from trailmend.data.model import Node
from trailmend.data.qtemplates import template
from trailmend.data.questions import Question
from trailmend.errors import ErrorCode
from trailmend.graph.schema import NodeLabel
from trailmend.loop.evaluate import Judged, Verdict
from trailmend.search.seed import tokenise

K1 = 1.5
B = 0.75
TOP_K = 15


@dataclass(frozen=True, slots=True)
class PlainStore:
    postings: Mapping[str, tuple[tuple[int, int], ...]]
    lengths: Mapping[int, int]
    mentions: Mapping[int, tuple[int, ...]]
    labels: Mapping[int, NodeLabel]
    mean_length: float

    @property
    def size(self) -> int:
        return len(self.lengths)


def build_store(documents: Sequence[Document], nodes: Sequence[Node]) -> PlainStore:
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    lengths: dict[int, int] = {}
    mentions: dict[int, tuple[int, ...]] = {}
    for document in documents:
        tokens = tokenise(document.text)
        counts: dict[str, int] = defaultdict(int)
        for token in tokens:
            counts[token] += 1
        for token, count in sorted(counts.items()):
            postings[token].append((document.id, count))
        lengths[document.id] = len(tokens)
        mentions[document.id] = document.mentions
    if not lengths:
        raise ValueError("a plain store needs at least one document")
    return PlainStore(
        {token: tuple(items) for token, items in sorted(postings.items())},
        lengths,
        mentions,
        {node.id: node.label for node in nodes},
        sum(lengths.values()) / len(lengths),
    )


def bm25(store: PlainStore, query: str) -> tuple[tuple[int, float], ...]:
    scores: dict[int, float] = defaultdict(float)
    for token in dict.fromkeys(tokenise(query)):
        posting = store.postings.get(token)
        if not posting:
            continue
        idf = math.log(1 + (store.size - len(posting) + 0.5) / (len(posting) + 0.5))
        for document_id, count in posting:
            norm = K1 * (1 - B + B * store.lengths[document_id] / store.mean_length)
            scores[document_id] += idf * count * (K1 + 1) / (count + norm)
    return tuple(sorted(scores.items(), key=lambda pair: (-pair[1], pair[0])))


def _tally(store: PlainStore, documents: Sequence[int], expected: NodeLabel) -> dict[int, int]:
    counts: dict[int, int] = defaultdict(int)
    for document_id in documents:
        for entity in store.mentions[document_id]:
            if store.labels.get(entity) is expected:
                counts[entity] += 1
    return counts


def judge_plain(store: PlainStore, question: Question, top_k: int = TOP_K) -> Judged:
    spec = template(question.template)
    ranked = [document_id for document_id, _ in bm25(store, question.text)[:top_k]]
    counts = _tally(store, ranked, spec.answer_label)
    if not counts:
        return Judged(
            question.id,
            question.template,
            question.seed_entity_id,
            Verdict.UNREACHABLE,
            ErrorCode.UNREACHABLE,
            (),
            question.gold,
            (),
        )
    best = max(counts.values())
    winners = tuple(sorted(entity for entity, count in counts.items() if count == best))
    if len(winners) > 1 and spec.single_answer:
        return Judged(
            question.id,
            question.template,
            question.seed_entity_id,
            Verdict.REFUSED,
            ErrorCode.AMBIGUOUS_ANSWER,
            (),
            question.gold,
            (),
        )
    verdict = Verdict.CORRECT if set(winners) == set(question.gold) else Verdict.WRONG
    return Judged(question.id, question.template, question.seed_entity_id, verdict, None, winners, question.gold, ())


def judge_all_plain(store: PlainStore, questions: Sequence[Question], top_k: int = TOP_K) -> tuple[Judged, ...]:
    return tuple(judge_plain(store, question, top_k) for question in questions)
