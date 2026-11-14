import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from trailmend.data.model import Node
from trailmend.errors import ErrorCode

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class SeedFound:
    entity_id: int
    matched: str
    how: str


@dataclass(frozen=True, slots=True)
class SeedRefused:
    code: ErrorCode
    candidates: tuple[int, ...]


type SeedOutcome = SeedFound | SeedRefused


def tokenise(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(text.lower()))


def _boundary(label: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(label)}(?![a-z0-9])")


@dataclass(frozen=True, slots=True)
class EntityIndex:
    by_token: Mapping[str, tuple[int, ...]]
    texts: Mapping[int, tuple[str, ...]]
    patterns: Mapping[str, re.Pattern[str]]

    def candidates(self, tokens: Sequence[str]) -> tuple[int, ...]:
        found: list[int] = []
        for token in dict.fromkeys(tokens):
            found.extend(self.by_token.get(token, ()))
        return tuple(dict.fromkeys(found))


def build_index(nodes: Sequence[Node]) -> EntityIndex:
    by_token: dict[str, list[int]] = defaultdict(list)
    texts: dict[int, tuple[str, ...]] = {}
    patterns: dict[str, re.Pattern[str]] = {}
    for node in nodes:
        labels = tuple(dict.fromkeys(text.lower() for text in (node.name, *node.aliases)))
        texts[node.id] = labels
        for label in labels:
            patterns.setdefault(label, _boundary(label))
            for token in dict.fromkeys(tokenise(label)):
                if node.id not in by_token[token]:
                    by_token[token].append(node.id)
    return EntityIndex({token: tuple(ids) for token, ids in by_token.items()}, texts, patterns)


def _exact_matches(index: EntityIndex, question: str) -> list[tuple[str, int]]:
    lowered = question.lower()
    found: list[tuple[str, int]] = []
    for entity in index.candidates(tokenise(question)):
        for label in index.texts[entity]:
            if index.patterns[label].search(lowered):
                found.append((label, entity))
    return found


def _token_scores(index: EntityIndex, question: str) -> dict[int, float]:
    scores: dict[int, float] = defaultdict(float)
    for token in dict.fromkeys(tokenise(question)):
        owners = index.by_token.get(token, ())
        if not owners:
            continue
        weight = 1.0 / len(owners)
        for entity in owners:
            scores[entity] += weight
    return scores


def _top(scores: Mapping[int, float]) -> tuple[float, tuple[int, ...]]:
    if not scores:
        return 0.0, ()
    best = max(scores.values())
    return best, tuple(sorted(entity for entity, score in scores.items() if score == best))


def seed_entity(index: EntityIndex, question: str) -> SeedOutcome:
    exact = _exact_matches(index, question)
    if exact:
        longest = max(len(label) for label, _ in exact)
        best = [(label, entity) for label, entity in exact if len(label) == longest]
        winners = tuple(dict.fromkeys(entity for _, entity in best))
        if len(winners) == 1:
            return SeedFound(winners[0], best[0][0], "exact")
        return SeedRefused(ErrorCode.AMBIGUOUS_SEED, tuple(sorted(winners)))
    score, winners = _top(_token_scores(index, question))
    if not winners or score <= 0:
        return SeedRefused(ErrorCode.NO_SEED, ())
    if len(winners) > 1:
        return SeedRefused(ErrorCode.AMBIGUOUS_SEED, winners)
    return SeedFound(winners[0], question, "token")
