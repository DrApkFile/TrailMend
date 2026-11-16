from collections.abc import Sequence
from dataclasses import dataclass

from trailmend.core.model import EdgeKey, SearchConfig
from trailmend.errors import ErrorCode
from trailmend.graph import queries as q
from trailmend.graph.client import HydraClient
from trailmend.graph.schema import NodeLabel, endpoints_of, is_shortcut
from trailmend.graph.values import PathValue
from trailmend.search.confidence import uses_unconfirmed


@dataclass(frozen=True, slots=True)
class ScoredPath:
    cost: float
    terminal: int
    terminal_label: NodeLabel
    edges: tuple[EdgeKey, ...]


@dataclass(frozen=True, slots=True)
class AnswerFound:
    answer_ids: tuple[int, ...]
    cost: float
    paths: tuple[tuple[EdgeKey, ...], ...]

    @property
    def answer_id(self) -> int:
        if len(self.answer_ids) != 1:
            raise ValueError(f"this answer holds {len(self.answer_ids)} entities, not one")
        return self.answer_ids[0]

    @property
    def path(self) -> tuple[EdgeKey, ...]:
        if len(self.paths) != 1:
            raise ValueError(f"this answer holds {len(self.paths)} paths, not one")
        return self.paths[0]


@dataclass(frozen=True, slots=True)
class AnswerRefused:
    code: ErrorCode
    candidates: tuple[int, ...] = ()


COST_PLACES = 9

type AnswerOutcome = AnswerFound | AnswerRefused


def _terminal_label(path: PathValue) -> NodeLabel | None:
    if not path.rels:
        return None
    last = path.rels[-1]
    if is_shortcut(last.rel_type):
        declared = last.props.get("target_label")
        if not isinstance(declared, str):
            raise ValueError(f"shortcut {last.rel_type} {last.src}->{last.dst} carries no target_label")
        return NodeLabel(declared)
    try:
        return endpoints_of(last.rel_type)[1]
    except (KeyError, ValueError):
        return None


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


def pick_answer(paths: Sequence[ScoredPath], expected: NodeLabel, *, multi_answer: bool = False) -> AnswerOutcome:
    matching = [p for p in paths if p.terminal_label is expected]
    if not matching:
        return AnswerRefused(ErrorCode.UNREACHABLE)
    cheapest: dict[int, ScoredPath] = {}
    for path in matching:
        held = cheapest.get(path.terminal)
        if held is None or round(path.cost, COST_PLACES) < round(held.cost, COST_PLACES):
            cheapest[path.terminal] = path
    best = min(round(path.cost, COST_PLACES) for path in cheapest.values())
    winners = sorted(
        (path for path in cheapest.values() if round(path.cost, COST_PLACES) == best), key=lambda p: p.terminal
    )
    if len(winners) > 1 and not multi_answer:
        return AnswerRefused(ErrorCode.AMBIGUOUS_ANSWER, tuple(path.terminal for path in winners))
    return AnswerFound(tuple(path.terminal for path in winners), best, tuple(path.edges for path in winners))


def answer(
    client: HydraClient,
    seed_id: int,
    rel_types: Sequence[str],
    expected: NodeLabel,
    config: SearchConfig,
    *,
    multi_answer: bool = False,
) -> AnswerOutcome:
    result = client.run(
        q.weighted_paths_from(rel_types, config.max_len, config.result_limit, weighted=config.weighted),
        {"src": seed_id},
    )
    if len(result.rows) >= config.result_limit:
        return AnswerRefused(ErrorCode.BUDGET_EXCEEDED)
    chosen = pick_answer(score_paths(result.rows), expected, multi_answer=multi_answer)
    if isinstance(chosen, AnswerFound):
        if config.max_answer_cost is not None and chosen.cost > config.max_answer_cost:
            return AnswerRefused(ErrorCode.LOW_CONFIDENCE)
        if config.gapfill_edges and uses_unconfirmed(client, chosen.paths, config.gapfill_edges):
            return AnswerRefused(ErrorCode.LOW_CONFIDENCE)
    return chosen
