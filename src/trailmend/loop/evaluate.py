from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.data.qtemplates import template
from trailmend.data.questions import Question
from trailmend.errors import ErrorCode
from trailmend.graph.client import HydraClient
from trailmend.search.answer import AnswerRefused, answer
from trailmend.search.seed import EntityIndex, SeedFound, seed_entity


class Verdict(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"
    UNREACHABLE = "unreachable"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class Judged:
    question_id: str
    template: str
    seed_entity_id: int
    verdict: Verdict
    refusal: ErrorCode | None
    answer_ids: tuple[int, ...]
    gold: tuple[int, ...]
    paths: tuple[tuple[EdgeKey, ...], ...]

    @property
    def hit(self) -> bool:
        return self.verdict is Verdict.CORRECT

    def set_f1(self) -> float:
        if not self.answer_ids or not self.gold:
            return 0.0
        overlap = len(set(self.answer_ids) & set(self.gold))
        if overlap == 0:
            return 0.0
        precision = overlap / len(set(self.answer_ids))
        recall = overlap / len(set(self.gold))
        return 2 * precision * recall / (precision + recall)


def _refused(question: Question, code: ErrorCode) -> Judged:
    verdict = Verdict.UNREACHABLE if code is ErrorCode.UNREACHABLE else Verdict.REFUSED
    return Judged(question.id, question.template, question.seed_entity_id, verdict, code, (), question.gold, ())


def judge(client: HydraClient, index: EntityIndex, question: Question, config: SearchConfig) -> Judged:
    spec = template(question.template)
    found = seed_entity(index, question.text)
    if not isinstance(found, SeedFound):
        return _refused(question, found.code)
    outcome = answer(
        client,
        found.entity_id,
        spec.search_types,
        question.answer_label,
        config,
        multi_answer=not spec.single_answer,
    )
    if isinstance(outcome, AnswerRefused):
        return _refused(question, outcome.code)
    verdict = Verdict.CORRECT if set(outcome.answer_ids) == set(question.gold) else Verdict.WRONG
    return Judged(
        question.id,
        question.template,
        found.entity_id,
        verdict,
        None,
        outcome.answer_ids,
        question.gold,
        outcome.paths,
    )


def judge_all(
    client: HydraClient, index: EntityIndex, questions: Sequence[Question], config: SearchConfig
) -> tuple[Judged, ...]:
    return tuple(judge(client, index, question, config) for question in questions)


@dataclass(frozen=True, slots=True)
class Score:
    n: int
    correct: int
    accuracy: float
    set_f1: float
    unreachable: int
    refused: int
    wrong: int


def score(judged: Sequence[Judged]) -> Score:
    total = len(judged)
    if total == 0:
        raise ValueError("cannot score an empty question set")
    correct = sum(j.hit for j in judged)
    return Score(
        total,
        correct,
        correct / total,
        sum(j.set_f1() for j in judged) / total,
        sum(j.verdict is Verdict.UNREACHABLE for j in judged),
        sum(j.verdict is Verdict.REFUSED for j in judged),
        sum(j.verdict is Verdict.WRONG for j in judged),
    )
