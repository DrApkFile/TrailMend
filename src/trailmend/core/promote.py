from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from trailmend.core.model import SHORTCUT_PREFIX, EdgeKey, MendConfig, Promote, Retire

MIN_COMPRESSIBLE_HOPS = 2


@dataclass(frozen=True, slots=True)
class Confirmation:
    question_id: str
    shortcut_type: str
    path: tuple[EdgeKey, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    key: EdgeKey
    via_path: tuple[EdgeKey, ...]
    question_ids: tuple[str, ...]


def is_shortcut_edge(edge: EdgeKey) -> bool:
    return edge.rel_type.startswith(SHORTCUT_PREFIX)


def compressible_runs(path: Sequence[EdgeKey]) -> tuple[tuple[EdgeKey, ...], ...]:
    if any(is_shortcut_edge(hop) for hop in path):
        return ()
    return tuple(
        tuple(path[start:end])
        for start in range(len(path))
        for end in range(start + MIN_COMPRESSIBLE_HOPS, len(path) + 1)
    )


def shortcut_key(shortcut_type: str, path: Sequence[EdgeKey]) -> EdgeKey:
    if not path:
        raise ValueError("a shortcut needs a path to compress")
    return EdgeKey(path[0].src, shortcut_type, path[-1].dst)


def candidates(
    confirmations: Sequence[Confirmation], existing: Collection[EdgeKey], cfg: MendConfig
) -> tuple[Candidate, ...]:
    asked: dict[tuple[str, tuple[EdgeKey, ...]], list[str]] = {}
    for confirmation in confirmations:
        for run in compressible_runs(confirmation.path):
            asked.setdefault((confirmation.shortcut_type, run), []).append(confirmation.question_id)
    found: list[Candidate] = []
    for (shortcut_type, path), question_ids in sorted(asked.items()):
        distinct = tuple(dict.fromkeys(question_ids))
        key = shortcut_key(shortcut_type, path)
        if len(distinct) >= cfg.promote_min_questions and key not in existing:
            found.append(Candidate(key, path, distinct))
    return tuple(found)


def promotions(found: Sequence[Candidate], hop_costs: Mapping[EdgeKey, float]) -> tuple[Promote, ...]:
    return tuple(
        Promote(c.key, c.via_path, c.question_ids, sum(hop_costs[hop] for hop in c.via_path))
        for c in found
        if all(hop in hop_costs for hop in c.via_path)
    )


def retirements(
    shortcuts: Mapping[EdgeKey, tuple[EdgeKey, ...]], quarantined: Collection[EdgeKey]
) -> tuple[Retire, ...]:
    return tuple(
        Retire(key, via_path)
        for key, via_path in sorted(shortcuts.items())
        if any(hop in quarantined for hop in via_path)
    )
