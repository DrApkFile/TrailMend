from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from random import Random

from trailmend.core.model import Change, EdgeKey, Quarantine, Reweight, Signal


class MendPolicy(StrEnum):
    FULL = "full"
    FROZEN_V4 = "frozen_v4"
    FULL_V4_NO_GATE = "full_v4_no_gate"
    FULL_V2_ABSTAIN = "full_v2_abstain"
    FROZEN_ABSTAIN = "frozen_abstain"
    FULL_V2 = "full_v2"
    FULL_V1_RULE = "full_v1_rule"
    FULL_UNWEIGHTED = "full_unweighted"
    GAPFILL_WIDE_ONLY = "gapfill_wide_only"
    REWEIGHT_ONLY = "reweight_only"
    QUARANTINE_ONLY = "quarantine_only"
    PROMOTE_ONLY = "promote_only"
    GAPFILL_ONLY = "gapfill_only"
    FROZEN = "frozen"
    RANDOM_REWEIGHT = "random_reweight"
    RANDOM_QUARANTINE = "random_quarantine"


CONTROL_OF: dict[MendPolicy, MendPolicy] = {
    MendPolicy.RANDOM_REWEIGHT: MendPolicy.REWEIGHT_ONLY,
    MendPolicy.RANDOM_QUARANTINE: MendPolicy.QUARANTINE_ONLY,
}

RANDOM_QUESTION_PREFIX = "random:"


@dataclass(frozen=True, slots=True)
class Mechanisms:
    reweight: bool
    quarantine: bool
    promote: bool
    gapfill: bool


MECHANISMS: Mapping[MendPolicy, Mechanisms] = {
    MendPolicy.FULL: Mechanisms(True, True, True, True),
    MendPolicy.FROZEN_V4: Mechanisms(False, False, False, False),
    MendPolicy.FULL_V4_NO_GATE: Mechanisms(True, True, True, True),
    MendPolicy.FULL_V2_ABSTAIN: Mechanisms(True, True, True, True),
    MendPolicy.FROZEN_ABSTAIN: Mechanisms(False, False, False, False),
    MendPolicy.FULL_V2: Mechanisms(True, True, True, True),
    MendPolicy.FULL_V1_RULE: Mechanisms(True, True, True, True),
    MendPolicy.FULL_UNWEIGHTED: Mechanisms(True, True, True, True),
    MendPolicy.GAPFILL_WIDE_ONLY: Mechanisms(False, False, False, True),
    MendPolicy.REWEIGHT_ONLY: Mechanisms(True, False, False, False),
    MendPolicy.QUARANTINE_ONLY: Mechanisms(False, True, False, False),
    MendPolicy.PROMOTE_ONLY: Mechanisms(False, False, True, False),
    MendPolicy.GAPFILL_ONLY: Mechanisms(False, False, False, True),
    MendPolicy.FROZEN: Mechanisms(False, False, False, False),
    MendPolicy.RANDOM_REWEIGHT: Mechanisms(True, False, False, False),
    MendPolicy.RANDOM_QUARANTINE: Mechanisms(False, True, False, False),
}


def mechanisms(policy: MendPolicy) -> Mechanisms:
    found = MECHANISMS.get(policy)
    if found is None:
        raise KeyError(f"{policy} declares no mechanisms")
    return found


UPDATE_V1 = "v1"
UPDATE_V2 = "v2"
GAPFILL_NARROW = "narrow"
GAPFILL_WIDE = "wide"


@dataclass(frozen=True, slots=True)
class Rules:
    update: str
    gapfill: str


RULES: Mapping[MendPolicy, Rules] = {
    MendPolicy.FULL: Rules(UPDATE_V1, GAPFILL_NARROW),
    MendPolicy.FROZEN_V4: Rules(UPDATE_V2, GAPFILL_WIDE),
    MendPolicy.FULL_V4_NO_GATE: Rules(UPDATE_V2, GAPFILL_WIDE),
    MendPolicy.FULL_V2_ABSTAIN: Rules(UPDATE_V2, GAPFILL_WIDE),
    MendPolicy.FROZEN_ABSTAIN: Rules(UPDATE_V2, GAPFILL_WIDE),
    MendPolicy.FULL_V2: Rules(UPDATE_V2, GAPFILL_WIDE),
    MendPolicy.FULL_V1_RULE: Rules(UPDATE_V1, GAPFILL_NARROW),
    MendPolicy.FULL_UNWEIGHTED: Rules(UPDATE_V2, GAPFILL_WIDE),
    MendPolicy.GAPFILL_WIDE_ONLY: Rules(UPDATE_V2, GAPFILL_WIDE),
    MendPolicy.REWEIGHT_ONLY: Rules(UPDATE_V1, GAPFILL_NARROW),
    MendPolicy.QUARANTINE_ONLY: Rules(UPDATE_V1, GAPFILL_NARROW),
    MendPolicy.PROMOTE_ONLY: Rules(UPDATE_V1, GAPFILL_NARROW),
    MendPolicy.GAPFILL_ONLY: Rules(UPDATE_V1, GAPFILL_NARROW),
    MendPolicy.FROZEN: Rules(UPDATE_V1, GAPFILL_NARROW),
    MendPolicy.RANDOM_REWEIGHT: Rules(UPDATE_V2, GAPFILL_NARROW),
    MendPolicy.RANDOM_QUARANTINE: Rules(UPDATE_V2, GAPFILL_NARROW),
}


def rules(policy: MendPolicy) -> Rules:
    found = RULES.get(policy)
    if found is None:
        raise KeyError(f"{policy} declares no update and gap-fill rules")
    return found


@dataclass(frozen=True, slots=True)
class ChangeProfile:
    reweights: int
    reweight_signals: tuple[tuple[Signal, ...], ...]
    quarantines: int


UNWEIGHTED_SEARCH: frozenset[MendPolicy] = frozenset({MendPolicy.FULL_UNWEIGHTED})


def searches_on_cost(policy: MendPolicy) -> bool:
    return policy not in UNWEIGHTED_SEARCH


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
        case (
            MendPolicy.FULL
            | MendPolicy.FULL_V4_NO_GATE
            | MendPolicy.FULL_V2
            | MendPolicy.FULL_V2_ABSTAIN
            | MendPolicy.FULL_V1_RULE
            | MendPolicy.FULL_UNWEIGHTED
        ):
            return tuple(planned)
        case MendPolicy.REWEIGHT_ONLY:
            return tuple(c for c in planned if isinstance(c, Reweight))
        case MendPolicy.QUARANTINE_ONLY:
            return tuple(c for c in planned if isinstance(c, Quarantine))
        case (
            MendPolicy.PROMOTE_ONLY
            | MendPolicy.GAPFILL_ONLY
            | MendPolicy.GAPFILL_WIDE_ONLY
            | MendPolicy.FROZEN
            | MendPolicy.FROZEN_ABSTAIN
            | MendPolicy.FROZEN_V4
        ):
            return ()
        case MendPolicy.RANDOM_REWEIGHT:
            return _mirror_reweights(planned, candidates, rng)
        case MendPolicy.RANDOM_QUARANTINE:
            return _mirror_quarantines(planned, candidates, rng)
