import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import replace

from trailmend.core.model import (
    Change,
    Credit,
    EdgeKey,
    EdgeState,
    EdgeStatus,
    Fill,
    MendConfig,
    Promote,
    Quarantine,
    Restore,
    Retire,
    Reweight,
    Signal,
)


def _clamp(value: float, cfg: MendConfig) -> float:
    return min(cfg.cost_ceiling, max(cfg.cost_floor, value))


def apply_signal(state: EdgeState, signal: Signal, cfg: MendConfig) -> EdgeState:
    step = -cfg.confirm_step if signal is Signal.CONFIRM else cfg.eta
    return replace(
        state,
        cost=_clamp(state.cost * math.exp(step), cfg),
        confirms=state.confirms + (signal is Signal.CONFIRM),
        blames=state.blames + (signal is Signal.BLAME),
        recent=(*state.recent, signal)[-cfg.window :],
    )


def apply_change(state: EdgeState, change: Change, cfg: MendConfig) -> EdgeState:
    if change.edge != state.key:
        raise ValueError(f"change for {change.edge} applied to {state.key}")
    match change:
        case Reweight(signals=signals):
            for signal in signals:
                state = apply_signal(state, signal, cfg)
            return state
        case Quarantine():
            return replace(state, status=EdgeStatus.QUARANTINED)
        case Promote(cost=cost) | Fill(cost=cost):
            if state.status is not EdgeStatus.ABSENT:
                raise ValueError(f"{state.key} already exists, so it cannot be added")
            return replace(state, status=EdgeStatus.ACTIVE, cost=_clamp(cost, cfg))
        case Retire():
            if state.status is EdgeStatus.ABSENT:
                raise ValueError(f"{state.key} is already gone, so it cannot be retired")
            return replace(state, status=EdgeStatus.ABSENT)
        case Restore(state=prior):
            return prior


def should_quarantine(state: EdgeState, cfg: MendConfig, *, confirmed_this_round: bool) -> bool:
    if state.status is not EdgeStatus.ACTIVE or confirmed_this_round:
        return False
    recent_blames = sum(s is Signal.BLAME for s in state.recent)
    return (
        recent_blames >= cfg.quarantine_min_blames
        and recent_blames / len(state.recent) >= cfg.quarantine_blame_share
        and state.confirms <= cfg.quarantine_confirm_ceiling
    )


def plan_round(states: Mapping[EdgeKey, EdgeState], credits: Iterable[Credit], cfg: MendConfig) -> tuple[Change, ...]:
    grouped: dict[EdgeKey, list[Credit]] = defaultdict(list)
    for credit in credits:
        if credit.edge not in states:
            raise KeyError(f"credit for unknown edge {credit.edge}")
        grouped[credit.edge].append(credit)
    changes: list[Change] = []
    for edge in sorted(grouped):
        state = states[edge]
        if state.status is not EdgeStatus.ACTIVE:
            continue
        ordered = sorted(grouped[edge], key=lambda c: (c.question_id, c.signal.value))
        reweight = Reweight(edge, tuple(c.signal for c in ordered), tuple(c.question_id for c in ordered))
        changes.append(reweight)
        after = apply_change(state, reweight, cfg)
        confirmed = any(c.signal is Signal.CONFIRM for c in ordered)
        if should_quarantine(after, cfg, confirmed_this_round=confirmed):
            changes.append(Quarantine(edge, reweight.question_ids))
    return tuple(changes)
