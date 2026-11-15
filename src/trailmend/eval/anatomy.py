from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from trailmend.core.model import EdgeKey
from trailmend.data.faultmodel import EdgeDelta, FaultSet
from trailmend.data.questions import Question
from trailmend.errors import ErrorCode
from trailmend.graph.schema import RelType
from trailmend.loop.evaluate import Judged, Verdict

PLANTED_WRONG_EDGE = "planted_wrong_edge"
MISSING_EDGE = "missing_edge"
ALIAS_DUPLICATE = "alias_duplicate"
CONFLATED_ENTITY = "conflated_entity"
TIE = "tie"
OTHER = "other"
CAUSES: tuple[str, ...] = (PLANTED_WRONG_EDGE, MISSING_EDGE, ALIAS_DUPLICATE, CONFLATED_ENTITY, TIE, OTHER)


def _keys(deltas: Sequence[EdgeDelta], *, added: bool) -> frozenset[EdgeKey]:
    edges = [e for delta in deltas for e in (delta.added if added else delta.removed)]
    return frozenset(EdgeKey(e.src, e.rel_type.value, e.dst) for e in edges)


@dataclass(frozen=True, slots=True)
class FaultIndex:
    wrong_added: frozenset[EdgeKey]
    wrong_removed: frozenset[EdgeKey]
    withheld: frozenset[EdgeKey]
    alias_added: frozenset[EdgeKey]
    alias_removed: frozenset[EdgeKey]
    conflation_added: frozenset[EdgeKey]
    conflation_removed: frozenset[EdgeKey]
    duplicate_ids: frozenset[int]
    absorbed_ids: frozenset[int]


def index_of(faults: FaultSet) -> FaultIndex:
    return FaultIndex(
        _keys([f.delta for f in faults.wrong_edges], added=True),
        _keys([f.delta for f in faults.wrong_edges], added=False),
        _keys([f.delta for f in faults.missing_edges], added=False),
        _keys([f.delta for f in faults.alias_duplicates], added=True),
        _keys([f.delta for f in faults.alias_duplicates], added=False),
        _keys([f.delta for f in faults.conflations], added=True),
        _keys([f.delta for f in faults.conflations], added=False),
        frozenset(f.duplicate_id for f in faults.alias_duplicates),
        frozenset(f.absorbed_id for f in faults.conflations),
    )


def truth_path_edges(
    question: Question, rel_path: Sequence[RelType], adjacency: Mapping[tuple[int, RelType], tuple[int, ...]]
) -> frozenset[EdgeKey]:
    layers: list[set[int]] = [{question.seed_entity_id}]
    for rel_type in rel_path:
        layers.append({dst for src in layers[-1] for dst in adjacency.get((src, rel_type), ())})
    keep = layers[-1] & set(question.gold)
    chosen: set[EdgeKey] = set()
    for step in range(len(rel_path) - 1, -1, -1):
        rel_type = rel_path[step]
        previous: set[int] = set()
        for src in layers[step]:
            for dst in adjacency.get((src, rel_type), ()):
                if dst in keep:
                    chosen.add(EdgeKey(src, rel_type.value, dst))
                    previous.add(src)
        keep = previous
    return frozenset(chosen)


@dataclass(frozen=True, slots=True)
class Anatomy:
    question_id: str
    template: str
    verdict: str
    refusal: str | None
    cause: str
    also: tuple[str, ...]
    wrong_edge_on_chosen_path: bool
    true_edge_replaced: bool


def _causes_present(judged: Judged, truth_edges: frozenset[EdgeKey], facts: FaultIndex) -> tuple[str, ...]:
    chosen = {edge for path in judged.paths for edge in path}
    present: list[str] = []
    if chosen & facts.wrong_added or truth_edges & facts.wrong_removed:
        present.append(PLANTED_WRONG_EDGE)
    if truth_edges & facts.withheld:
        present.append(MISSING_EDGE)
    if truth_edges & facts.alias_removed or chosen & facts.alias_added:
        present.append(ALIAS_DUPLICATE)
    if truth_edges & facts.conflation_removed or set(judged.gold) & facts.absorbed_ids:
        present.append(CONFLATED_ENTITY)
    if judged.refusal is ErrorCode.AMBIGUOUS_ANSWER:
        present.append(TIE)
    return tuple(present)


def anatomy_of(judged: Judged, truth_edges: frozenset[EdgeKey], facts: FaultIndex) -> Anatomy:
    present = _causes_present(judged, truth_edges, facts)
    chosen = {edge for path in judged.paths for edge in path}
    return Anatomy(
        judged.question_id,
        judged.template,
        judged.verdict.value,
        judged.refusal.value if judged.refusal is not None else None,
        present[0] if present else OTHER,
        present[1:],
        bool(chosen & facts.wrong_added),
        bool(truth_edges & facts.wrong_removed),
    )


def failing(judged: Sequence[Judged]) -> tuple[Judged, ...]:
    return tuple(j for j in judged if j.verdict is not Verdict.CORRECT)
