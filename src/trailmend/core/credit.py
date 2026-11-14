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
class Refused:
    question_id: str
    reason: str


type Outcome = Correct | Wrong | Unreachable | Refused


def assign_credit(outcome: Outcome) -> tuple[Credit, ...]:
    match outcome:
        case Correct(question_id=qid, chosen=chosen):
            return tuple(Credit(e, Signal.CONFIRM, qid) for e in dict.fromkeys(chosen))
        case Wrong(question_id=qid, chosen=chosen, best_gold=gold):
            gold_edges = tuple(dict.fromkeys(gold or ()))
            blamed = tuple(e for e in dict.fromkeys(chosen) if e not in gold_edges)
            return tuple(Credit(e, Signal.BLAME, qid) for e in blamed) + tuple(
                Credit(e, Signal.CONFIRM, qid) for e in gold_edges
            )
        case Unreachable() | Refused():
            return ()
