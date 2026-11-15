from bisect import bisect
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate
from random import Random

DEFAULT_WEIGHTS: tuple[tuple[int, float], ...] = ((1, 0.55), (2, 0.25), (3, 0.20))
STALE_SUPPORT: tuple[int, ...] = (3,)
CONTRADICTED_SUPPORT = 1


@dataclass(frozen=True, slots=True)
class SupportPlan:
    weights: tuple[tuple[int, float], ...] = DEFAULT_WEIGHTS
    stale: tuple[int, ...] = STALE_SUPPORT

    def __post_init__(self) -> None:
        if not self.weights:
            raise ValueError("support weights must not be empty")
        if any(count < 1 for count, _ in self.weights):
            raise ValueError("support counts must be at least 1")
        if any(weight <= 0 for _, weight in self.weights):
            raise ValueError("support weights must be positive")
        if not self.stale or any(count < 1 for count in self.stale):
            raise ValueError("stale support counts must be at least 1")
        if set(self.stale) - {count for count, _ in self.weights}:
            raise ValueError("stale support must be drawn from the same distribution as every other edge")

    @property
    def counts(self) -> tuple[int, ...]:
        return tuple(count for count, _ in self.weights)

    def share_at_least(self, support: int) -> float:
        total = sum(weight for _, weight in self.weights)
        return sum(weight for count, weight in self.weights if count >= support) / total


def _pick(rng: Random, counts: Sequence[int], weights: Sequence[float]) -> int:
    thresholds = list(accumulate(weights))
    return counts[bisect(thresholds, rng.random() * thresholds[-1])]


def draw(rng: Random, plan: SupportPlan) -> int:
    return _pick(rng, plan.counts, [weight for _, weight in plan.weights])


def draw_stale(rng: Random, plan: SupportPlan) -> int:
    weights = dict(plan.weights)
    return _pick(rng, plan.stale, [weights[count] for count in plan.stale])
