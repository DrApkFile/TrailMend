from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from random import Random

from trailmend.core.model import Change, EdgeKey, Quarantine, Reweight, Signal


class MendPolicy(StrEnum):
    FULL = "full"
    REWEIGHT_ONLY = "reweight_only"
    QUARANTINE_ONLY = "quarantine_only"
    FROZEN = "frozen"
    RANDOM_REWEIGHT = "random_reweight"
    RANDOM_QUARANTINE = "random_quarantine"


CONTROL_OF: dict[MendPolicy, MendPolicy] = {
    MendPolicy.RANDOM_REWEIGHT: MendPolicy.REWEIGHT_ONLY,
    MendPolicy.RANDOM_QUARANTINE: MendPolicy.QUARANTINE_ONLY,
}

RANDOM_QUESTION_PREFIX = "random:"


@dataclass(frozen=True, slots=True)
class ChangeProfile:
    reweights: int
    reweight_signals: tuple[tuple[Signal, ...], ...]
    quarantines: int


def profile(changes: Sequence[Change]) -> ChangeProfile:
    signals = tuple(sorted(c.signals for c in changes if isinstance(c, Reweight)))
    return ChangeProfile(len(signals), signals, sum(isinstance(c, Quarantine) for c in changes))


def _targets(count: int, candidates: Sequence[EdgeKey], rng: Random) -> tuple[EdgeKey, ...]:
    pool = sorted(set(candidates))
    if len(pool) < count:
        raise ValueError(f"mirroring the plan needs {count} distinct edges, the pool offers {len(pool)}")
    return tuple(rng.sample(pool, count))


def _mirror_reweights(planned: Sequence[Change], candidates: Sequence[EdgeKey], rng: Random) -> tuple[Change, ...]:
    reweights = [c for c in planned if isinstance(c, Reweight)]
    targets = _targets(len(reweights), candidates, rng)
    return tuple(
        Reweight(target, change.signals, tuple(RANDOM_QUESTION_PREFIX + q for q in change.question_ids))
        for target, change in zip(targets, reweights, strict=True)
    )


def _mirror_quarantines(planned: Sequence[Change], candidates: Sequence[EdgeKey], rng: Random) -> tuple[Change, ...]:
    quarantines = [c for c in planned if isinstance(c, Quarantine)]
    targets = _targets(len(quarantines), candidates, rng)
    return tuple(
        Quarantine(target, tuple(RANDOM_QUESTION_PREFIX + q for q in change.question_ids))
        for target, change in zip(targets, quarantines, strict=True)
    )


def shape(
    policy: MendPolicy, planned: Sequence[Change], candidates: Sequence[EdgeKey], rng: Random
) -> tuple[Change, ...]:
    match policy:
        case MendPolicy.FULL:
            return tuple(planned)
        case MendPolicy.REWEIGHT_ONLY:
            return tuple(c for c in planned if isinstance(c, Reweight))
        case MendPolicy.QUARANTINE_ONLY:
            return tuple(c for c in planned if isinstance(c, Quarantine))
        case MendPolicy.FROZEN:
            return ()
        case MendPolicy.RANDOM_REWEIGHT:
            return _mirror_reweights(planned, candidates, rng)
        case MendPolicy.RANDOM_QUARANTINE:
            return _mirror_quarantines(planned, candidates, rng)
