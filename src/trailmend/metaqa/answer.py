from collections.abc import Sequence
from dataclasses import dataclass

from trailmend.core.model import EdgeKey
from trailmend.errors import ErrorCode
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.values import PathValue
from trailmend.loop.evaluate import Verdict
from trailmend.metaqa.sample import MqQuestion
from trailmend.search.answer import COST_PLACES

type Path = tuple[EdgeKey, ...]


@dataclass(frozen=True, slots=True)
class Ranked:
    terminal: int
    cost: float
    path: Path


@dataclass(frozen=True, slots=True)
class MqJudged:
    question_id: str
    qtype: str
    hop: int
    topic_id: int
    verdict: Verdict
    refusal: ErrorCode | None
    answers: tuple[int, ...]
    gold: tuple[int, ...]
    chosen: Path
    best_gold: Path | None

    @property
    def hit(self) -> bool:
        return self.verdict is Verdict.CORRECT

    @property
    def top(self) -> int | None:
        return self.answers[0] if self.answers else None

    @property
    def exact(self) -> bool:
        return bool(self.answers) and set(self.answers) == set(self.gold)


def _as_cost(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise TypeError(f"pathWeight must be a number, got {raw!r}")
    return float(raw)


def rank(rows: Sequence[Sequence[object]], rel_path: tuple[str, ...]) -> tuple[Ranked, ...]:
    cheapest: dict[int, Ranked] = {}
    for row in rows:
        path, weight = row[0], row[1]
        if not isinstance(path, PathValue):
            raise TypeError(f"expected a path, got {type(path).__name__}")
        if tuple(rel.rel_type for rel in path.rels) != rel_path:
            continue
        if len(set(path.node_ids)) != len(path.node_ids):
            continue
        cost = round(_as_cost(weight), COST_PLACES)
        terminal = path.node_ids[-1]
        held = cheapest.get(terminal)
        if held is None or cost < held.cost:
            cheapest[terminal] = Ranked(terminal, cost, tuple(EdgeKey(r.src, r.rel_type, r.dst) for r in path.rels))
    return tuple(sorted(cheapest.values(), key=lambda r: (r.cost, r.terminal)))


def judge_ranked(question: MqQuestion, ranked: Sequence[Ranked]) -> MqJudged:
    answers = tuple(r.terminal for r in ranked)
    if not ranked:
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
    gold = set(question.gold)
    best_gold = next((r.path for r in ranked if r.terminal in gold), None)
    verdict = Verdict.CORRECT if ranked[0].terminal in gold else Verdict.WRONG
    return MqJudged(
        question.id,
        question.qtype,
        question.hop,
        question.topic_id,
        verdict,
        None,
        answers,
        question.gold,
        ranked[0].path,
        best_gold,
    )


def judge(client: HydraClient, question: MqQuestion, result_limit: int) -> MqJudged:
    types = sorted(set(question.rel_path))
    result = client.run(q.weighted_paths_from(types, question.hop, result_limit), {"src": question.topic_id})
    if len(result.rows) >= result_limit:
        return MqJudged(
            question.id,
            question.qtype,
            question.hop,
            question.topic_id,
            Verdict.REFUSED,
            ErrorCode.BUDGET_EXCEEDED,
            (),
            question.gold,
            (),
            None,
        )
    return judge_ranked(question, rank(result.rows, question.rel_path))


def judge_all(client: HydraClient, questions: Sequence[MqQuestion], result_limit: int) -> tuple[MqJudged, ...]:
    return tuple(judge(client, question, result_limit) for question in questions)


@dataclass(frozen=True, slots=True)
class MqScore:
    n: int
    hits: int
    hits_at_1: float
    exact: int
    exact_set: float
    wrong: int
    wrong_rate: float
    unreachable: int
    refused: int


def score(judged: Sequence[MqJudged]) -> MqScore:
    total = len(judged)
    if total == 0:
        raise ValueError("cannot score an empty question set")
    hits = sum(j.hit for j in judged)
    exact = sum(j.exact for j in judged)
    wrong = sum(j.verdict is Verdict.WRONG for j in judged)
    return MqScore(
        total,
        hits,
        hits / total,
        exact,
        exact / total,
        wrong,
        wrong / total,
        sum(j.verdict is Verdict.UNREACHABLE for j in judged),
        sum(j.verdict is Verdict.REFUSED for j in judged),
    )
