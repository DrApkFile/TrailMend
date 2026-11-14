from collections.abc import Sequence
from dataclasses import dataclass

from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.errors import ErrorCode
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.schema import ENDPOINTS, NodeLabel, RelType
from trailmend.graph.values import PathValue


@dataclass(frozen=True, slots=True)
class ScoredPath:
    cost: float
    terminal: int
    terminal_label: NodeLabel
    edges: tuple[EdgeKey, ...]


@dataclass(frozen=True, slots=True)
class AnswerFound:
    answer_id: int
    cost: float
    path: tuple[EdgeKey, ...]


@dataclass(frozen=True, slots=True)
class AnswerRefused:
    code: ErrorCode
    candidates: tuple[int, ...] = ()


type AnswerOutcome = AnswerFound | AnswerRefused


def _terminal_label(path: PathValue) -> NodeLabel | None:
    if not path.rels:
        return None
    try:
        rel_type = RelType(path.rels[-1].rel_type)
    except ValueError:
        return None
    return ENDPOINTS[rel_type][1]


def _as_cost(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise TypeError(f"pathWeight must be a number, got {raw!r}")
    return float(raw)


def score_paths(rows: Sequence[Sequence[object]]) -> tuple[ScoredPath, ...]:
    scored: list[ScoredPath] = []
    for row in rows:
        path, weight = row[0], row[1]
        if not isinstance(path, PathValue):
            raise TypeError(f"expected a path, got {type(path).__name__}")
        label = _terminal_label(path)
        if label is None:
            continue
        edges = tuple(EdgeKey(rel.src, rel.rel_type, rel.dst) for rel in path.rels)
        scored.append(ScoredPath(_as_cost(weight), path.node_ids[-1], label, edges))
    return tuple(scored)


def pick_answer(paths: Sequence[ScoredPath], expected: NodeLabel) -> AnswerOutcome:
    matching = [p for p in paths if p.terminal_label is expected]
    if not matching:
        return AnswerRefused(ErrorCode.UNREACHABLE)
    cheapest: dict[int, ScoredPath] = {}
    for path in matching:
        held = cheapest.get(path.terminal)
        if held is None or path.cost < held.cost:
            cheapest[path.terminal] = path
    best = min(path.cost for path in cheapest.values())
    winners = sorted((path for path in cheapest.values() if path.cost == best), key=lambda p: p.terminal)
    if len(winners) > 1:
        return AnswerRefused(ErrorCode.AMBIGUOUS_ANSWER, tuple(path.terminal for path in winners))
    chosen = winners[0]
    return AnswerFound(chosen.terminal, chosen.cost, chosen.edges)


def answer(
    client: HydraClient,
    seed_id: int,
    rel_types: Sequence[str],
    expected: NodeLabel,
    config: SearchConfig,
) -> AnswerOutcome:
    result = client.run(q.weighted_paths_from(rel_types, config.max_len, config.result_limit), {"src": seed_id})
    if len(result.rows) >= config.result_limit:
        return AnswerRefused(ErrorCode.BUDGET_EXCEEDED)
    return pick_answer(score_paths(result.rows), expected)
