from collections.abc import Sequence
from dataclasses import dataclass

from trailmend.core.model import Credit, EdgeKey, Signal

type EdgePath = Sequence[EdgeKey]


@dataclass(frozen=True, slots=True)
class Correct:
    question_id: str
    chosen: EdgePath


@dataclass(frozen=True, slots=True)
class Wrong:
    question_id: str
    chosen: EdgePath
    best_gold: EdgePath | None


@dataclass(frozen=True, slots=True)
class Unreachable:
    question_id: str
    seed_id: int
    expected_label: str
    template: str


@dataclass(frozen=True, slots=True)
class SetJudged:
    question_id: str
    correct_paths: tuple[EdgePath, ...]
    wrong_paths: tuple[EdgePath, ...]
    missed_gold_paths: tuple[EdgePath, ...]


@dataclass(frozen=True, slots=True)
class Refused:
    question_id: str
    reason: str


type Outcome = Correct | Wrong | SetJudged | Unreachable | Refused


def _credit_paths(
    question_id: str,
    correct_paths: Sequence[EdgePath],
    wrong_paths: Sequence[EdgePath],
    missed_gold_paths: Sequence[EdgePath],
) -> tuple[Credit, ...]:
    confirmed = tuple(dict.fromkeys(edge for path in (*correct_paths, *missed_gold_paths) for edge in path))
    chosen_wrong = tuple(dict.fromkeys(edge for path in wrong_paths for edge in path))
    blamed = tuple(edge for edge in chosen_wrong if edge not in confirmed)
    return tuple(Credit(e, Signal.BLAME, question_id) for e in blamed) + tuple(
        Credit(e, Signal.CONFIRM, question_id) for e in confirmed
    )


def confirmed_paths(outcome: Outcome) -> tuple[EdgePath, ...]:
    match outcome:
        case Correct(chosen=chosen):
            return (chosen,)
        case Wrong(best_gold=gold):
            return (gold,) if gold else ()
        case SetJudged(correct_paths=good, missed_gold_paths=missed):
            return (*good, *missed)
        case Unreachable() | Refused():
            return ()


def assign_credit(outcome: Outcome) -> tuple[Credit, ...]:
    match outcome:
        case Correct(question_id=qid, chosen=chosen):
            return _credit_paths(qid, (chosen,), (), ())
        case Wrong(question_id=qid, chosen=chosen, best_gold=gold):
            return _credit_paths(qid, (), (chosen,), (gold,) if gold else ())
        case SetJudged(question_id=qid, correct_paths=good, wrong_paths=bad, missed_gold_paths=missed):
            return _credit_paths(qid, good, bad, missed)
        case Unreachable() | Refused():
            return ()
