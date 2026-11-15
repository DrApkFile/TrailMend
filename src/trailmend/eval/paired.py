from dataclasses import dataclass
from math import comb
from pathlib import Path

from trailmend.loop.journal import RUNS_DIR
from trailmend.loop.tape import Tape

CORRECT = "correct"


@dataclass(frozen=True, slots=True)
class Paired:
    n: int
    both_correct: int
    only_first: int
    only_second: int
    neither: int
    p_value: float

    @property
    def delta_points(self) -> float:
        return 100.0 * (self.only_first - self.only_second) / self.n


def mcnemar_exact(only_first: int, only_second: int) -> float:
    if only_first < 0 or only_second < 0:
        raise ValueError("discordant counts cannot be negative")
    discordant = only_first + only_second
    if discordant == 0:
        return 1.0
    smaller = min(only_first, only_second)
    tail = sum(comb(discordant, k) for k in range(smaller + 1)) / 2**discordant
    return min(1.0, 2.0 * tail)


def correct_at(run_id: str, round_index: int, root: Path = RUNS_DIR) -> dict[str, bool]:
    path = root / run_id / "heldout.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"no held-out tape for {run_id} at {path}")
    answers = {a.question_id: a.verdict == CORRECT for a in Tape(path).rounds() if a.round_index == round_index}
    if not answers:
        raise ValueError(f"the tape for {run_id} recorded no answers at round {round_index}")
    return answers


def compare(first: dict[str, bool], second: dict[str, bool]) -> Paired:
    if set(first) != set(second):
        raise ValueError("a paired test needs the same held-out questions on both sides")
    both = sum(first[q] and second[q] for q in first)
    only_first = sum(first[q] and not second[q] for q in first)
    only_second = sum(second[q] and not first[q] for q in first)
    neither = len(first) - both - only_first - only_second
    return Paired(len(first), both, only_first, only_second, neither, mcnemar_exact(only_first, only_second))


def against(run_id: str, seed: int, arm: str, reference: str, round_index: int, root: Path = RUNS_DIR) -> Paired:
    first = correct_at(f"{run_id}-s{seed}-{arm}", round_index, root)
    second = correct_at(f"{run_id}-s{seed}-{reference}", round_index, root)
    return compare(first, second)


def row(run_id: str, seed: int, arm: str, reference: str, round_index: int, root: Path = RUNS_DIR) -> dict[str, object]:
    result = against(run_id, seed, arm, reference, round_index, root)
    return {
        "seed": seed,
        "arm": arm,
        "reference": reference,
        "round": round_index,
        "n": result.n,
        "both_correct": result.both_correct,
        "only_arm_correct": result.only_first,
        "only_reference_correct": result.only_second,
        "neither_correct": result.neither,
        "delta_points": round(result.delta_points, 4),
        "p_value": round(result.p_value, 6),
    }
