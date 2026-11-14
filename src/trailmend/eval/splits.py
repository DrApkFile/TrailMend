import json
from collections import defaultdict
from dataclasses import dataclass
from random import Random

from trailmend.data.questions import Question, QuestionSet

TRAIN_SHARE = 0.6


@dataclass(frozen=True, slots=True)
class TrainQuestion:
    question: Question


@dataclass(frozen=True, slots=True)
class HeldOutQuestion:
    question: Question


@dataclass(frozen=True, slots=True)
class Split:
    seed: int
    train_share: float
    train: tuple[TrainQuestion, ...]
    held_out: tuple[HeldOutQuestion, ...]

    @property
    def train_ids(self) -> frozenset[str]:
        return frozenset(t.question.id for t in self.train)

    @property
    def held_out_ids(self) -> frozenset[str]:
        return frozenset(h.question.id for h in self.held_out)

    def stratum_counts(self) -> dict[tuple[str, int], tuple[int, int]]:
        counts: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
        for item in self.train:
            counts[(item.question.template, item.question.hops)][0] += 1
        for item in self.held_out:
            counts[(item.question.template, item.question.hops)][1] += 1
        return {key: (value[0], value[1]) for key, value in counts.items()}


def _strata(questions: QuestionSet) -> dict[tuple[str, int], list[Question]]:
    grouped: dict[tuple[str, int], list[Question]] = defaultdict(list)
    for question in questions.questions:
        grouped[(question.template, question.hops)].append(question)
    return {key: sorted(items, key=lambda q: q.id) for key, items in sorted(grouped.items())}


def make_split(questions: QuestionSet, train_share: float = TRAIN_SHARE) -> Split:
    if not 0 < train_share < 1:
        raise ValueError("train_share must be strictly between 0 and 1")
    rng = Random(questions.seed * 104_729 + 3)
    train: list[TrainQuestion] = []
    held_out: list[HeldOutQuestion] = []
    for _, items in _strata(questions).items():
        order = list(items)
        rng.shuffle(order)
        cut = round(len(order) * train_share)
        train.extend(TrainQuestion(q) for q in sorted(order[:cut], key=lambda q: q.id))
        held_out.extend(HeldOutQuestion(q) for q in sorted(order[cut:], key=lambda q: q.id))
    split = Split(questions.seed, train_share, tuple(train), tuple(held_out))
    if split.train_ids & split.held_out_ids:
        raise ValueError("a question landed in both splits")
    if len(split.train) + len(split.held_out) != len(questions.questions):
        raise ValueError("the split lost or duplicated questions")
    return split


def to_json(split: Split) -> str:
    payload = {
        "seed": split.seed,
        "train_share": split.train_share,
        "train": sorted(split.train_ids),
        "held_out": sorted(split.held_out_ids),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
